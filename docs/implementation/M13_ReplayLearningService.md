# M13 — ReplayLearningService (Implementation Record)

**Version:** 1.0
**Backend path:** `backend/src/grid_unlocked/learning/`
**Status:** Implemented (MVP — buffer construction, retrain, eval, promotion gate; synchronous in-request execution, no MLflow/scheduler)
**Spec reference:** [IMPLEMENTATION_MODULES.md § M13](../IMPLEMENTATION_MODULES.md)

---

## Purpose

M13 builds **80% recent-closed + 20% stratified historical anchor** replay
buffers, retrains M03's closure classifier (LightGBM) and ICT survival model
(Cox PH), evaluates against a **94% accuracy gate** plus an **anti-
catastrophic-forgetting anchor-regression check**, and stages/promotes model
versions. It is the missing piece M14's `promotion_checklist()` always
returned `complete=False` for — that stub now reads real eval data produced
by this module.

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/learning/retrain` | Build buffer, retrain, evaluate — `{ trigger: scheduled\|drift\|manual }` |
| GET | `/learning/buffer/manifest/{job_id}` | 80/20 composition, stratification breakdown, reject-reason signal |
| GET | `/learning/eval/{job_id}` | Accuracy, anchor accuracy, gate/stability result |
| POST | `/learning/promote/{model_version}` | Promote a staged model — `{ operator_id }`, 403 if gates failed |

---

## Core behavior

### Reusing existing training logic instead of reinventing it

`backend/scripts/train_impact_models.py` already implemented the exact
feature engineering + LightGBM/Cox PH training M03's registry artifacts
need — it just only ever read the static `data/astram_events.csv` (8,170
rows) and wrote to `models/v1/`. That logic was extracted, unchanged in
behavior, into `learning/training_core.py` (verified bit-for-bit identical
`feature_importance.json` output before/after the extraction). The CLI
script now imports from this shared module instead of defining the
functions inline; `scripts/evaluate_models.py` was updated the same way.

### Buffer construction (`learning/buffer.py::build_buffer`)

```
buffer = 0.8 x recent_closed(N weeks) U 0.2 x anchor_sample(stratified)
strata = corridor x cause x peak_flag x is_planned
```

- **Recent pool**: `NormalizedEventRow` rows where `status == "closed"` and
  `closed_datetime` falls within the rolling window
  (`settings.learning_recent_window_weeks`, default 4). Converted through the
  *same* per-row feature engineering as the CSV anchor pool
  (`training_core.build_feature_rows`) — corridor×cause priors and the
  hour-of-day reporting-bias weights are recomputed from whatever rows are
  actually in the combined buffer, not inherited from the static CSV's
  aggregates. This is what makes a buffer-based retrain meaningfully
  different from just re-running the CLI script.
- **Anchor pool**: a stratified sample of the full ASTraM CSV corpus — the
  fixed historical sample the spec calls for (already comfortably above the
  1,500-record floor; the full corpus is 8,170 rows). Sampling uses a
  largest-remainder proportional allocation per stratum (no per-stratum
  minimum-of-1 floor), so the total lands on the target count exactly even
  when there are hundreds of corridor×cause×peak×planned strata — a real bug
  found and fixed during implementation (the naive `max(1, round(...))`
  per-group approach overshot by 8x on small targets).
- **Anchor-only fallback**: if zero incidents have closed through the live
  system yet (realistic for a fresh deployment/demo), the buffer falls back
  to 100% anchor and the manifest reports `status="anchor_only"` rather than
  failing — there's nothing to retrain on beyond the static corpus, but the
  endpoint must still succeed.
- **Timezone normalization**: SQLite (aiosqlite) round-trips `start_datetime`
  as tz-naive while the CSV loader produces tz-aware (`UTC`) timestamps —
  concatenating both pools without normalizing crashed `sort_values` with
  `TypeError: Cannot compare tz-naive and tz-aware timestamps`. Fixed by
  coercing the recent pool's timestamps to UTC-aware in `_load_recent_pool`.

### Training (`training_core.train_closure_model(..., temporal_split=True)`)

- LightGBM with `scale_pos_weight=11`, same hyperparameters as the original
  script.
- `temporal_split=True` (M13's retrain path): sorts by `start`, trailing 20%
  is the validation slice — spec: *"temporal CV (no shuffle)"*.
  `temporal_split=False` (CLI script, unchanged): today's stratified random
  `train_test_split`. Both paths share one function.
- Cox PH (`train_cox_model`): missing `closed_datetime` (censored) rows have
  `duration_h` filled from `duration_prior_h` rather than dropped — spec:
  *"censored ICT records included via survival loss, not dropped."*

### Evaluation (`learning/evaluation.py::evaluate`)

- `accuracy`: `accuracy_score` on the temporal validation slice (the
  "governance-approved operational validation slice" for MVP), thresholded
  at `settings.closure_alert_threshold`.
- `anchor_accuracy`: same metric restricted to `pool == "anchor"` rows.
- `gate_passed = accuracy >= settings.learning_accuracy_gate` (0.94 default).
- `anchor_stable = (incumbent.anchor_accuracy - anchor_accuracy) <= settings.learning_anchor_epsilon`
  (0.02 default) — directly implements the spec's literal example ("recent
  95% but anchor dropped 3% → reject", since 0.03 > 0.02). `anchor_stable`
  is trivially `True` if there is no incumbent production model yet.

### Promotion (`learning/service.py::LearningService.promote`)

- 404 if the model doesn't exist; 409 if it isn't `stage="staged"`.
- 403 if `accuracy_gate_94pct` failed; 403 if `anchor_slice_stable` failed —
  this is M13's own promotion *recommendation* gate (spec: *"M13...
  promotion recommendation. M14 executes promotion gate"*), distinct from
  M14's `POST /governance/promotion/approve` human sign-off layered on top.
- On success: retires the current production row, flips the new row to
  `stage="production"`, calls `impact.registry.registry.reload(models_dir=...)`.

### Versioned artifacts — `models/v1/` is never overwritten

Each promotion writes to a **new** directory —
`{settings.models_dir.parent}/v{n}/` where `n` is one past the highest
existing `model_registry.model_version` — joblib + `metadata.json`, the same
shape `models/v1/` already has. `ModelRegistryRow.artifact_dir` is the single
source of truth for "which directory is currently live"; `ModelRegistry`
(M03) gained a `reload(models_dir=...)` method that repoints itself and
re-loads. Every promotion is fully reversible — the prior production
artifacts sit untouched on disk.

### Tier-aware degradation

| Tier | `POST /learning/retrain` | `POST /learning/promote/{v}` |
|---|---|---|
| 1 | Full retrain + eval | Allowed if gates pass |
| 2 | Full retrain + eval | **Always 403** — "eval only, no promotion" per spec |
| 3 | **503** — frozen model | N/A |

Reads tier via the same `get_governance()` every other module already uses
(`recommendations/governance.py`) — zero new governance plumbing.

---

## Status machine (model lifecycle)

```
staged --[promote(), gates pass]--> production --[next promotion]--> retired
staged --[promote(), gates fail]--> staged (403, stays staged for retry/inspection)
```

---

## Integration

| Module | Usage |
|---|---|
| M01 | `EventClosed` outcomes — recent pool sourced from `NormalizedEventRow.status == "closed"` |
| M02 | Feature definitions — `training_core.build_feature_rows` mirrors M02's engineered columns |
| M03 | `impact.registry.registry.reload()` — new hook, called on every promotion |
| M09 | `approval_records` (reject `reason_code`) surfaced read-only in the buffer manifest as the spec's "override codes feeding learning governance" signal — **no M09 changes**, no new table |
| M14 | `governance/service.py::promotion_checklist()` rewritten to query `model_registry`/`learning_jobs` for real `accuracy_gate_94pct`/`anchor_slice_stable` results; `shadow_mode_stability` stays M14-owned and stubbed (not M13's contract) |

---

## Source files

| File | Responsibility |
|---|---|
| `training_core.py` | Shared feature engineering + LightGBM/Cox PH training (extracted from `scripts/train_impact_models.py`, behavior-preserving) |
| `buffer.py` | 80/20 buffer construction, stratified anchor sampling, anchor-only fallback, reject-reason signal |
| `evaluation.py` | Accuracy/anchor-accuracy computation, gate + anchor-stability checks |
| `repository.py` | `replay_buffer_manifests` / `model_registry` / `learning_jobs` persistence |
| `service.py` | `LearningService` — retrain/manifest/eval/promote orchestration |
| `schemas.py` | `RetrainRequest/Response`, `BufferManifestResponse`, `EvalResponse`, `PromoteRequest/Response` |
| `router.py` | FastAPI routes |

---

## Database

### `replay_buffer_manifests`

| Column | Notes |
|---|---|
| `job_id` | PK |
| `recent_count`, `anchor_count`, `recent_pct`, `anchor_pct` | |
| `strata_json` | corridor×cause×peak×planned breakdown |
| `window_weeks`, `status` | `building` / `ready` / `anchor_only` / `failed` |

### `model_registry`

| Column | Notes |
|---|---|
| `model_version` | PK (`v2`, `v3`, ...) |
| `job_id` | Indexed — which retrain produced this |
| `closure_version`, `ict_version` | e.g. `lgbm-v2`, `cox-ph-v2` |
| `stage` | `staged` / `production` / `retired` — indexed |
| `accuracy`, `anchor_accuracy` | |
| `artifact_dir` | Source of truth for `ModelRegistry.reload()` |
| `promoted_at` | nullable |

### `learning_jobs`

| Column | Notes |
|---|---|
| `job_id` | PK |
| `trigger` | `scheduled` / `drift` / `manual` |
| `status` | `pending` / `running` / `eval_complete` / `promoted` / `failed` |
| `model_version`, `error_detail` | nullable |

No `override_feedback` table — `approval_records` (already written by M09's
`reject()`) is read directly; no schema change, no M09 changes.

---

## Tests

| File | Count | Coverage |
|---|---|---|
| `test_learning.py` | 17 | 80/20 manifest tolerance (small + at-scale), anchor-only fallback, stratification covers multiple corridors, promotion blocked on anchor regression (spec's literal 95%/anchor-3% example), promotion succeeds end-to-end (synthetic buffer), censored recent-pool Cox training doesn't crash, drift/scheduled trigger accepted+recorded (not auto-fired), Tier 3 blocks retrain, Tier 2 allows retrain but blocks promotion, governance checklist reflects real eval data, governance checklist for unknown model version, 404s (manifest/eval/promote unknown), 409 on re-promoting an already-production model |
| `test_integration.py` | +1 | M13 → M03 end-to-end through the live HTTP surface: retrain → eval → promote → a *subsequent* `/impact/score` call reports the newly-promoted `model_versions.closure` — not just `registry.reload()` called directly |

**The 94% accuracy gate and real ASTraM data**: with the real corpus's 8.3%
closure rate, a dummy "always predict no closure" baseline already scores
91.7% `accuracy_score` — the actual trained model scores *below* that
(91.5–90.6% depending on buffer composition), exactly as the root readme's
own ML research section documents ("accuracy is misleading... must not be
used for model selection"). Production code keeps the spec-literal
`accuracy_score >= 0.94` gate unchanged — it is not loosened or
reinterpreted. The "promotion succeeds" and "anchor regression blocks
promotion" tests use a small monkeypatched synthetic buffer with a clearly
separable closure signal (`corridor_cause_closure_rate` deterministically
correlated with `closure`) specifically to exercise the promotion plumbing
without misrepresenting what real data can achieve. Every other test (buffer
construction, stratification, censoring, tier gating) uses the real,
unmodified CSV corpus.

---

## Known limitations (MVP, deliberate scope reductions)

- `D-M13-01` — No MLflow. Artifacts are joblib + `metadata.json`, the same
  convention M03 already used. New versions land in `models/v2`, `v3`, ...;
  `v1` is never overwritten.
- `D-M13-02` — `POST /learning/retrain` runs buffer→train→eval **synchronously
  in-request**, not an async job/DAG. No task queue exists anywhere in the
  repo; building one would be disproportionate to a single module. Measured
  at ~3.3s for a full 8,170-row retrain — well within request timeouts.
- `D-M13-03` — `trigger: scheduled|drift` is accepted and recorded on the job
  row (satisfies the schema and audit trail), but only an explicit API call
  actually executes a retrain. No scheduler or drift-monitor exists — same
  precedent as M14's on-demand-only cascade drills.
- `shadow_mode_stability` (the checklist's third item) is intentionally
  **not** populated by M13 — per spec it's M14's own contract ("Tertiary:
  shadow mode stability (M14) passing"), not something this module produces.
- With real ASTraM data, the literal 94% `accuracy_score` gate is
  effectively unreachable given the dataset's 8.3% closure rate (see Tests
  section above) — this is a property of the metric choice on imbalanced
  data, not a bug in the gate logic itself.

---

## Next

- **M13 Phase 2** (per spec): monsoon-season specialized anchor stratum.
- Replace `accuracy_score` with a metric better suited to the imbalanced
  closure-rate distribution (PR-AUC/F1-macro, as the root readme's own ML
  research summary already recommends) if the 94% literal gate proves too
  blunt in practice — would require a spec amendment, not a silent code change.
- **Phase 1.5**: real async job queue + MLflow once volume justifies it;
  drift monitor (KS-test on `hour_ist` distribution per spec) to actually
  auto-fire `trigger=drift` retrains.
- M14's `shadow_mode_stability` checklist item, once M14 implements shadow
  agreement-rate tracking independently.
