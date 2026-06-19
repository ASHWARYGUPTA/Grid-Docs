# M07 — DispatchOrchestrator (Implementation Record)

**Version:** 0.7  
**Backend path:** `backend/src/grid_unlocked/dispatch/`  
**Status:** Implemented (MVP)  
**Spec reference:** [IMPLEMENTATION_MODULES.md § M07](../IMPLEMENTATION_MODULES.md) · [ML_MODULES_IMPLEMENTATION.md § M07](../ML_MODULES_IMPLEMENTATION.md)

---

## Purpose

M07 assigns police units to active incidents using **OR-Tools MILP** with a **1.5 s hard cutoff** and **deterministic greedy fallback**. ML signals from M02–M04 (RCI, corridor centrality, cascade risk) replace ASTraM static priority for ranking.

Non-blocking guarantee: every request returns assignments labeled `MILP` or `GREEDY_FALLBACK` within **1.8 s**.

---

## What is implemented

### API endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/dispatch/recommend` | Unit-to-incident assignment recommendation |
| GET | `/dispatch/status/{recommendation_id}` | Completion status + late MILP flag |
| GET | `/dispatch/roster` | Cached default unit roster (54-station proxy) |

### DispatchRecommendation outputs

| Field | Description |
|---|---|
| `recommendation_id` | Immutable audit ID (`DISP-…`) |
| `source` | `MILP` or `GREEDY_FALLBACK` |
| `assignments[]` | unit, station, event, ETA, RCI, cascade |
| `solver_ms` | MILP or greedy runtime |
| `latency_ms` | End-to-end orchestration time |
| `tier_at_decision` | Governance tier (1/2/3) |
| `astram_shadow[]` | ASTraM priority rank vs Grid RCI rank |
| `milp_attempted` / `milp_feasible` | Solver provenance |
| `late_milp_logged` | True if MILP finished after fallback issued |

---

## Algorithms

### MILP primary (Tier 1)

- Bipartite assignment: units × incidents
- Objective: minimize `α·ETA + α_uncovered·(β·RCI + δ·Cascade + p_closure)`
- Constraints: one unit per incident, one incident per unit, heavy-tow equipment gate
- OR-Tools SCIP/CBC with `SetTimeLimit(1500 ms)`

### Greedy fallback (Tier 1 timeout / Tier 2)

```
cost = α·ETA + β·RCI + γ·Centrality + δ·Cascade − η·(heavy_tow_match)
```

- Min-heap partial sort over all valid pairs
- Tie-break: `station_id ASC`, `unit_id ASC`
- High-RCI non-starvation: unassigned incidents get best compatible unit

### Tier 3

Nearest unit per incident, incidents sorted by RCI descending.

### Heavy vehicle heuristic (REQ-DISP-001)

`needs_heavy_tow` when `veh_type=heavy_vehicle` or cargo keywords in description. Non-tow units penalized (+10 cost); tow match gets `η=0.5` bonus.

### Bias correction

During 14–18 IST, `β·RCI` multiplied by M02 `reporting_bias_weight` (capped at 3.0).

---

## Integration

| Module | Usage |
|---|---|
| M02 | Feature vector, centrality, bias weight, 2 km density |
| M03 | `registry.score()` for RCI + p_closure |
| M04 | GCDH ripple inline for `cascade_risk` |
| M01 | Active incident list from `normalized_events` |

M07 is **on-demand API** (not event-bus driven).

---

## Source files

| File | Responsibility |
|---|---|
| `router.py` | FastAPI routes |
| `service.py` | Orchestrator, tier routing, late MILP log |
| `milp.py` | OR-Tools assignment solver |
| `greedy.py` | Deterministic fallback |
| `incidents.py` | IncidentContext builder |
| `roster.py` | 12-unit MVP roster (54-station proxy) |
| `travel.py` | Haversine ETA (30 km/h city avg) |
| `repository.py` | Audit persistence + active event query |
| `schemas.py` | Request/response contracts |

---

## Database

### `dispatch_recommendations`

| Column | Notes |
|---|---|
| `recommendation_id` | PK |
| `source` | MILP / GREEDY_FALLBACK |
| `tier_at_decision` | 1 / 2 / 3 |
| `recommendation_json` | Full `DispatchRecommendation` |
| `solver_ms`, `latency_ms` | Timing audit |
| `created_at` | Immutable timestamp |

---

## Configuration (`GRID_*` env)

| Setting | Default | Meaning |
|---|---|---|
| `dispatch_milp_deadline_ms` | 1500 | MILP hard cutoff |
| `dispatch_total_deadline_ms` | 1800 | Total SLA target |
| `dispatch_alpha_eta` | 1.0 | Travel time weight |
| `dispatch_beta_rci` | 0.4 | RCI weight |
| `dispatch_gamma_centrality` | 0.25 | Centrality weight |
| `dispatch_delta_cascade` | 0.35 | Cascade risk weight |
| `dispatch_eta_heavy_tow` | 0.5 | Tow match bonus |

---

## Tests

`backend/tests/test_dispatch.py` — 7 tests:

- Heavy vehicle → tow unit in greedy
- Dual incident ASTraM shadow ranks
- 100× greedy determinism
- Tie-breaker (lower station_id wins)
- Status endpoint
- Roster endpoint
- MILP or greedy within deadline

---

## Demo curl

```bash
# Ingest heavy ORR incident
curl -X POST http://localhost:8000/ingest/astram -H 'Content-Type: application/json' -d '{
  "id": "FKIDDISP-DEMO",
  "event_type": "unplanned",
  "latitude": 12.969, "longitude": 77.701,
  "event_cause": "accident", "corridor": "ORR East 1",
  "start_datetime": "2024-03-07T16:00:00+00:00",
  "status": "active", "authenticated": "yes",
  "veh_type": "heavy_vehicle", "priority": "High",
  "description": "Heavy truck steel coils"
}'

# Wait ~0.3s for M02 features, then recommend
curl -X POST http://localhost:8000/dispatch/recommend \
  -H 'Content-Type: application/json' \
  -d '{"event_id":"FKIDDISP-DEMO"}'
```

---

## Known limitations (MVP)

- Travel time uses Haversine @ 30 km/h — not OSM shortest path matrix (Appendix I)
- Roster is static 12-unit seed, not live station API (M10)
- Late MILP logged in-memory; not yet written to separate audit table
- Tier 2/3 selected via request param until M14 GovernanceConsole ships

---

## Next

- **M08** DiversionRoutingEngine — replace M06 diversion stub + feed dispatch route hints
- **M09** RecommendationAPI — unify M03–M08 into action cards
