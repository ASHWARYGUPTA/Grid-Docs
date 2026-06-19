# M03 — ImpactEngine (Implementation Record)

**Version:** 0.3  
**Backend path:** `backend/src/grid_unlocked/impact/`  
**Status:** Implemented (MVP)  
**Spec reference:** [IMPLEMENTATION_MODULES.md § M03](../IMPLEMENTATION_MODULES.md) · [ML_MODELS_PRD.md](../ML_MODELS_PRD.md)

---

## Purpose

M03 scores every normalized incident with **closure probability**, **ICT time bands** (P20/P50/P80), and a composite **Road Congestion Index (RCI)** with severity bands. It consumes leakage-safe `FeatureVector` outputs from M02 and logs every score for M13 replay learning.

When ML artifacts are absent, the engine degrades to **Tier 2 rule-based priors** without blocking the ingest path.

---

## What is implemented

### API endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/impact/score` | Score single event by `event_id` |
| POST | `/impact/score/batch` | Batch score (up to 50 event IDs; skips missing) |
| GET | `/impact/explain/{event_id}` | Top-5 feature importances |
| GET | `/models/versions` | Active closure + ICT model versions |

### ImpactScore outputs

| Field | Description |
|---|---|
| `p_closure` | Calibrated closure probability (LightGBM or corridor×cause prior) |
| `ict_p20_h` / `ict_p50_h` / `ict_p80_h` | ICT quantile bands in hours |
| `rci` | Composite impact score [0, 1] |
| `severity_band` | Green / Yellow / Orange / Red |
| `priority_structural` | `is_named_corridor` flag (not raw ASTraM priority) |
| `staging_recommended` | `p_closure > 0.35` |
| `model_versions` | Closure + ICT version + source (`ml` or `rule_fallback`) |
| `latency_ms` | Inference timing |

### Severity bands

| Band | RCI range |
|---|---|
| Green | &lt; 0.35 |
| Yellow | 0.35 – 0.55 |
| Orange | 0.55 – 0.75 |
| Red | ≥ 0.75 |

Evening bias multiplier (14–18 IST): RCI × `reporting_bias_weight` (capped at 3×).

---

## Algorithms

### RCI aggregation

```
RCI = 0.20·norm(log(duration_prior_h))
    + 0.18·betweenness_norm
    + 0.22·cascade_seed        # defaults to p_closure at score time
    + 0.25·p_closure_live
    + 0.10·veh_complexity
    + 0.05·norm(simultaneous_events_2km)
```

### Closure classifier (Tier 1)

- **Model:** LightGBM binary classifier, `scale_pos_weight=11`
- **Calibration:** Isotonic regression on validation fold
- **Features:** 18-column matrix from M02 + `is_planned` + cause/corridor encodings
- **Hard rules:** `is_planned` → min P(closure) 0.36; `vip_movement` → min 0.80

### ICT survival (Tier 1)

- **Model:** Cox Proportional Hazards (lifelines)
- **Censoring:** 61.6% of ASTraM records without `closed_datetime` handled via partial likelihood
- **Output:** Survival curve inversion → P20/P50/P80 hours

### Rule fallback (Tier 2)

When `backend/models/v1/metadata.json` is missing:

- `p_closure` = M02 `corridor_cause_closure_rate` (+ planned/VIP floors)
- ICT bands = 0.8× / 1.0× / 1.5× of `duration_prior_h`
- Source stamped `rule_fallback`, versions `rule-v1`

---

## Source files

| File | Responsibility |
|---|---|
| `router.py` | FastAPI routes (`/impact/*`, `/models/versions`) |
| `service.py` | Orchestration: fetch features → score → persist log |
| `registry.py` | Model load, ML inference, rule fallback |
| `rci.py` | RCI formula + severity band mapping |
| `feature_matrix.py` | FeatureVector → model input row |
| `repository.py` | Append-only `impact_scores` log |
| `schemas.py` | Pydantic models |

**Training script:** `backend/scripts/train_impact_models.py`  
**Artifacts directory:** `backend/models/v1/` (not committed; train locally)

---

## Database

### `impact_scores` (append-only)

| Column | Type | Notes |
|---|---|---|
| `event_id` | string | FK to normalized event |
| `p_closure`, `ict_p20/p50/p80_h`, `rci` | float | Score outputs |
| `severity_band`, `source` | string | Band + `ml` / `rule_fallback` |
| `closure_model_version`, `ict_model_version` | string | Version stamp |
| `staging_recommended` | bool | Alert flag |
| `scored_at` | timestamp | UTC |

---

## Integration flow

```
M01 ingest → EventNormalized → M02 materialize features
                                      ↓
POST /impact/score ← FeatureVector + event metadata
                                      ↓
                         impact_scores log (append-only)
                                      ↓
                               M04 GCDH (next)
```

Models are warmed on API startup via `registry.load()` in `main.py` lifespan.

---

## Train models locally

```bash
cd backend
uv sync
uv run python scripts/train_impact_models.py
# Artifacts → backend/models/v1/
uv run uvicorn grid_unlocked.main:app --reload
```

After training, `/models/versions` returns `lgbm-v1` / `cox-ph-v1` with `source: ml`.

---

## Tests

`backend/tests/test_impact.py` — 6 tests:

- Score after ingest (rule fallback path)
- VIP movement closure floor ≥ 0.80
- Explain endpoint returns top features
- Model versions endpoint
- Batch scoring skips missing IDs
- RCI severity band unit tests

Run: `cd backend && uv run pytest`

---

## Deferred (not blocking MVP)

| Item | Target |
|---|---|
| SHAP per-prediction values | Phase 2 (global importances only for now) |
| MLflow registry + M13 promotion | M13 ReplayLearningService |
| Async score on `EventNormalized` | On-demand API sufficient for hackathon |
| Weather-conditioned priors | Phase 2 |
| AFT secondary model | Phase 2 if Cox PH anchor regression fails |
| Tier 3 static SOP templates | M14 governance flags |

---

## Version history

| Version | Change |
|---|---|
| 0.3.0 | M03 ImpactEngine — score/batch/explain/versions, RCI, rule fallback, training script |

**Next module:** M04 PropagationEngine — GCDH ripple from `ImpactScore.rci` seed.
