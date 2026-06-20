# M14 — GovernanceConsole (Implementation Record)

**Version:** 1.0
**Backend path:** `backend/src/grid_unlocked/governance/`
**Status:** Implemented (MVP — tiers, shadow mode, health rollup, auto-transition, drills; promotion checklist honestly incomplete pending M13)
**Spec reference:** [IMPLEMENTATION_MODULES.md § M14](../IMPLEMENTATION_MODULES.md)

---

## Purpose

M14 owns **tier (1/2/3)**, **shadow mode**, **health rollup**, **automatic tier
transitions with recovery hysteresis**, **manual override audit**, **cascade
drills**, and the **M13 promotion checklist gate**. Before this module, every
caller of governance state (M07, M09, M10, M11) read a hardcoded config stub
(`recommendations/governance.py` returning static `settings.governance_*`
values) — there was no way to actually change tier or shadow mode at runtime,
and no health signal tying the modules together.

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/governance/tier` | Current tier + shadow mode + manual_mode |
| POST | `/governance/override-tier` | Manual tier override — `{ tier, reason, operator_id }`, immutable audit |
| POST | `/governance/shadow-mode` | Toggle shadow mode — `{ enabled, operator_id }` |
| GET | `/governance/transitions` | Tier change audit log (manual + automatic) |
| GET | `/governance/health` | Per-module health rollup (M01/M02/M03/M07/M10/M11) |
| GET | `/governance/promotion/checklist/{model_version}` | M13 promotion checklist |
| POST | `/governance/promotion/approve` | Sign-off — 403 if checklist incomplete |
| POST | `/governance/drills/cascade` | Trigger a synthetic cascade drill |
| GET | `/governance/drills/cascade/last` | Last drill result |

---

## Core behavior

### The sync-read problem and how it's solved

Every existing caller — `recommendations/service.py` (M09), `execution/service.py`
(M10), `vms/service.py` (M11), `dispatch/service.py` (M07, via `GovernanceTier`) —
calls `get_governance()` **synchronously, with no DB session**, on the hot path.
Rewriting this to be async would have meant touching every one of those call
sites. Instead:

- The durable source of truth is the `governance_state` DB row (singleton, `id=1`).
- A module-level in-process cache (`governance/service.py::_cache`) mirrors it,
  written on every `GovernanceService` write (`bootstrap`, `override_tier`,
  `set_shadow_mode`, automatic transitions).
- **Until M14 has written at least once**, `get_governance()` transparently
  proxies live `settings.governance_tier` / `settings.governance_shadow_mode`
  — this is exactly the old stub's behavior, preserved as a fallback so the
  136 pre-existing tests that do
  `monkeypatch.setattr(settings, "governance_shadow_mode", False)` continue
  to work **completely unmodified**.
- The moment any M14 write happens, the DB-backed cache becomes authoritative
  for the rest of that process's lifetime — settings are no longer consulted.
- If M14 has never bootstrapped at all (e.g. app crashed before `lifespan`
  ran), the cache's hardcoded dataclass default is `tier="3", shadow_mode=True`
  — the spec's documented last-resort: *"M14 itself is Tier 3 last-resort:
  embedded tier defaults in M15/M16 clients if M14 unreachable."*

`recommendations/governance.py::get_governance()` is now a 5-line function
that calls `governance.service.read_cached_state()` — zero I/O, same call
signature as before, zero changes required in M07/M09/M10/M11.

### Manual tier override / shadow mode toggle

- `override_tier(tier, reason, operator_id)` — updates `governance_state`,
  appends an immutable `tier_transitions` row (`operator_id` set = manual),
  refreshes the cache.
- `set_shadow_mode(enabled, operator_id)` — same pattern, no tier transition
  logged (shadow mode is orthogonal to tier).

### Health rollup (`GovernanceService.health()`)

Probes 6 modules using data already being written by those modules — no new
instrumentation needed:

| Module | Signal | Degraded when |
|---|---|---|
| M01_Ingestion | `IngestionService.health()` error rate | error_rate_pct ≥ 20% |
| M02_Features | `feature_snapshots` table reachable | query raises → down |
| M03_Impact | `ModelRegistry._ml_available` | ML artifacts not loaded → **down** (rule-fallback active) |
| M07_Dispatch | Greedy-fallback rate over last 50 `dispatch_recommendations` | fallback_rate > 50% |
| M10_Execution | Dead-letter rate over last 50 `execution_queue` rows | dlq_rate > 20% |
| M11_VMS | Dead-letter rate over last 50 `vms_deliveries` rows | dlq_rate > 20% |

`overall_status` = `down` if any module is down, else `degraded` if any is
degraded, else `healthy`.

### Automatic tier transitions (`evaluate_auto_transition`)

Implements the spec's exact rules:

- **M01 + M02 both down → Tier 3** (continuity SOP mode)
- **M03 down → Tier 2** (rule-fallback active, MILP/ML untrustworthy — greedy dispatch only)
- **Recovery hysteresis: 5 minutes continuously healthy → auto-upgrade to Tier 1**
  (tracked via `_healthy_since`; resets if a downgrade condition reappears)

Automatic transitions log to `tier_transitions` with `operator_id=None`,
distinguishing them from manual overrides in the audit trail. A background
`asyncio` task (`main.py::_governance_probe_loop`) calls this every 30s per
the spec's "probe cycle 30 s" latency contract — same pattern as M10's
command-queue worker.

### Cascade drills (`run_cascade_drill`)

The spec's drill ("inject 5 concurrent ORR closures + forced MILP timeout;
score M07+M09") is run against **real active incidents already ingested**,
not synthetic IDs — a drill that fabricates incident IDs the dispatch
pipeline would 404 on proves nothing. `force_milp_timeout=True` maps to
`RecommendRequest(force_greedy=True)`, and the drill fires one dispatch call
per active incident concurrently via `asyncio.gather`. Pass criteria:
100% `GREEDY_FALLBACK` and max latency under `dispatch_total_deadline_ms`
(1800ms). With **zero active incidents**, the drill returns `passed=False`
with an honest "no active incidents to drill against" detail rather than a
hollow pass.

### Promotion checklist

`promotion_checklist()` now queries M13's `model_registry`/`learning_jobs`
tables for the given `model_version`: `accuracy_gate_94pct` and
`anchor_slice_stable` reflect M13's real eval result once a retrain has
produced that version. If no M13 job has ever produced the requested
`model_version`, the checklist still returns the same honest
"incomplete, no eval available" shape it always did — no 404, matching
existing behavior. `shadow_mode_stability` remains intentionally hardcoded
`False` — that item is M14's own contract per spec ("Tertiary: shadow mode
stability (M14) passing"), not blocked on M13.

---

## Status machine (tier transitions)

```
Tier 1 (full MILP+ML) --[M03 down]--> Tier 2 (greedy, ML untrustworthy)
Tier 1/2              --[M01+M02 down]--> Tier 3 (manual SOP)
Tier 2/3              --[healthy ≥5min]--> Tier 1 (auto-recovery)
Any tier              --[manual override]--> any tier (audited, operator_id set)
```

---

## Integration

| Module | Usage |
|---|---|
| M07 | `dispatch/service.py` reads `GovernanceTier` via `RecommendRequest.tier`, set from `get_governance().tier` in M09's card assembly |
| M09 | `recommendations/service.py::build_card()` / `approve()` / `reject()` all call `get_governance()` — tier 3 → SOP fallback card with `dispatch=None`; shadow_mode gates M10/M11 enqueue |
| M10 | `execution/service.py::enqueue_dispatch()` — 403 if `shadow_mode=true`, 503 if `tier="3"` |
| M11 | `vms/service.py::push()` — 403 if `shadow_mode=true` |
| M01/M02/M03/M07/M10/M11 | Read-only health probe sources for `/governance/health` |

---

## Source files

| File | Responsibility |
|---|---|
| `schemas.py` | `GovernanceTierResponse`, `HealthRollup`, `ModuleHealth`, `DrillResult`, `PromotionChecklistResponse`, etc. |
| `repository.py` | `governance_state` (singleton) / `tier_transitions` (immutable) / `drill_results` persistence |
| `service.py` | `GovernanceService` — tier/shadow read+write, health probes, auto-transition, drills, promotion stub; module-level cache + `get_governance()` backing |
| `router.py` | FastAPI routes |

`recommendations/governance.py` was rewritten (not replaced) — same
`get_governance()` signature and `GovernanceState` shape, now backed by this
module's cache instead of a static stub.

---

## Database

### `governance_state` (singleton, `id=1`)

| Column | Notes |
|---|---|
| `tier` | `"1"` \| `"2"` \| `"3"` |
| `shadow_mode` | bool |
| `updated_by` | operator_id of last write, null if last write was automatic |
| `updated_at` | |

### `tier_transitions` (immutable)

| Column | Notes |
|---|---|
| `id` | PK autoincrement |
| `from_tier`, `to_tier` | |
| `reason` | Free text — mandatory on manual override |
| `operator_id` | **null = automatic transition**, set = manual override |
| `created_at` | Indexed |

### `drill_results`

| Column | Notes |
|---|---|
| `id` | PK autoincrement |
| `drill_type` | `"cascade"` (only type implemented) |
| `result_json` | `{ concurrent_closures, fallback_rate, max_latency_ms, deadline_ms }` |
| `passed` | bool |
| `created_at` | |

---

## Tests

| File | Count | Coverage |
|---|---|---|
| `test_governance.py` | 12 | Pre-bootstrap settings proxy, manual override + audit log, cache propagation to `get_governance()`, shadow-mode toggle end-to-end through M10, health rollup module set + dispatch fallback-rate metric, M03-down auto-Tier-2 chaos test, hysteresis-gated auto-recovery to Tier 1, cascade drill with no incidents (honest fail), cascade drill 100% greedy fallback under deadline, last-drill 404 before any run, promotion checklist incomplete → 403 |
| `test_integration.py` | +1 | M14 → M09 end-to-end: Tier 1 card has a dispatch section; after `override-tier` to Tier 3, a new card uses the SOP fallback path (`dispatch=None`, `provenance.dispatch=disabled`) — proving `get_governance()` reads live M14 state |

A genuine SQLite `StaticPool` timing race was found and fixed during test
development: toggling shadow mode back to `true` immediately after an M10
dispatch enqueue could race the M10 background worker's concurrent DB writes
on the single shared in-memory connection. The test now waits for the
dispatch to settle before the second toggle — a test-environment artifact
(Postgres's separate connections wouldn't collide this way), not a service bug.

---

## Known limitations (MVP, all explicitly deferred or out of scope per spec)

- `D-M14-02` — `operator_id` is a plain string field, not backed by an IAM/RBAC
  system (explicitly out of scope per spec: *"User identity provider
  implementation"*).
- `D-M14-03` — The 30s probe cycle runs as an in-process `asyncio` task inside
  the API server, not a separately deployable health-check service.
- Cascade drills only implement the `"cascade"` type from the spec's example;
  no drill scheduler (nightly cron) — drills are triggered on demand via the API.
- No M15 dashboard / M16 field-app tier badge consumption yet (those modules
  don't exist).

---

## Next

- **M13** ReplayLearningService is implemented — see
  [M13_ReplayLearningService.md](M13_ReplayLearningService.md). Remaining
  gap: `shadow_mode_stability` still needs M14 to implement shadow
  agreement-rate tracking independently.
- **M15** CommandDashboard — surface `/governance/health` and the tier badge
  live via WebSocket.
- **M16** FieldOfficerApp — degradation tier visible to field officers per
  spec user story 3.
- Nightly drill scheduler (cron) instead of on-demand-only triggering.
