# M04 — PropagationEngine (Implementation Record)

**Version:** 0.4  
**Backend path:** `backend/src/grid_unlocked/propagation/`  
**Status:** Implemented (MVP)  
**Spec reference:** [IMPLEMENTATION_MODULES.md § M04](../IMPLEMENTATION_MODULES.md) · [ML_MODULES_IMPLEMENTATION.md § M04](../ML_MODULES_IMPLEMENTATION.md)

---

## Purpose

M04 models **spatial cascade risk** without STGCN or live speed telemetry. It implements the **Graph-Centrality Decay Heuristic (GCDH)** — an explainable BFS propagation over the corridor graph with centrality-amplified exponential decay.

Output `CascadeRisk` feeds M07 greedy dispatch (δ term) and commander ripple maps on M15.

---

## What is implemented

### API endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/propagation/ripple` | Run GCDH from event seed; returns `PropagationMap` |
| GET | `/propagation/active` | All cached ripple maps for active incidents |
| GET | `/propagation/config` | Current λ, k, ε, max_hops defaults |

### Ripple request

```json
{
  "event_id": "FKIDPROP0001",
  "seed_rci": 0.82,
  "max_hops": 5,
  "epsilon": 0.02
}
```

`seed_rci` is optional — when omitted, M03 scores the event inline via `ImpactEngine` registry (no duplicate DB log).

### PropagationMap outputs

| Field | Description |
|---|---|
| `seed_node_id` | M02 `graph_node_id` (corridor node) |
| `seed_rci` | RCI seed from M03 or request override |
| `nodes[]` | `{ node_id, corridor, risk, hop, parent_edge }` trace |
| `cascade_risk` | Max risk within 2-hop neighborhood (2 km proxy) |
| `gcdh_params` | λ, k, ε, max_hops used for this run |
| `latency_ms` | Propagation timing |

---

## Algorithms

### GCDH formula

```
risk_{t+1}(v) = Σ_u risk_t(u) × edge_weight(u,v) × exp(-λ × hop) × (1 + k × betweenness(v))
```

| Parameter | Default | Meaning |
|---|---|---|
| λ (lambda) | 0.35 | Hop decay rate |
| k | 0.15 | Centrality amplification |
| ε (epsilon) | 0.02 | Stop when marginal risk &lt; ε |
| max_hops | 5 | Hard cap (Tier 2: 2) |
| edge_weight | 0.5 + 0.5 × avg(betweenness) | MVP capacity proxy |

### Algorithm steps

1. Map event → seed corridor node via M02 `FeatureVector.graph_node_id`
2. Initialize `risk(seed) = RCI` from M03 (or request override)
3. Level-order BFS hop expansion applying GCDH update
4. Prune contributions where `delta < epsilon`
5. `CascadeRisk` = max node risk at hop ≤ 2
6. Cache map in Redis (+ in-memory fallback); return explainable traces

### CascadeRisk aggregation

Default: **max risk within 2 hops** of seed (corridor-graph proxy for 2 km radius). Includes seed at hop 0.

---

## Source files

| File | Responsibility |
|---|---|
| `router.py` | FastAPI routes |
| `service.py` | Event lookup, M03 seed RCI, cache write |
| `gcdh.py` | Core GCDH BFS algorithm |
| `cache.py` | Redis + in-memory `PropagationMap` store |
| `schemas.py` | Pydantic models |
| `subscriber.py` | `EventClosed` → delete cached map |

---

## Event bus subscription

| Event | Handler | Action |
|---|---|---|
| `EventClosed` | `subscriber._handle_closed` | Delete propagation cache entry |

---

## Integration flow

```
M01 ingest → M02 features → M03 impact score (RCI)
                                    ↓
                    POST /propagation/ripple
                                    ↓
              PropagationMap + CascadeRisk (cached)
                                    ↓
                         M07 DispatchOrchestrator (next)
```

---

## Degradation (configured, M14 wiring deferred)

| Tier | Behavior |
|---|---|
| Tier 1 | Full GCDH up to 5 hops (default) |
| Tier 2 | 2-hop GCDH (`gcdh_tier2_max_hops=2`) |
| Tier 3 | Single-node seed only; `CascadeRisk = RCI` |

Tier flags will be driven by M14 `GovernanceState`; config constants are in place.

---

## Tests

`backend/tests/test_propagation.py` — 7 tests:

- Ripple after ingest (API integration)
- Active maps list
- Config endpoint defaults
- Monotonic decay hop 2 ≤ hop 1
- Centrality amplification (ORR East 2 &gt; Hosur Road at hop 1)
- Epsilon stops expansion
- Parent edge explainability on all hop &gt; 0 nodes

Run: `cd backend && uv run pytest`

---

## Deferred (not blocking MVP)

| Item | Target |
|---|---|
| OSM lane-count edge weights | Phase 2 graph ingest |
| Redis-only active index (no in-memory set) | Phase 1.5 |
| `gcdh_params` versioned DB table | Phase 2 calibration via M13 |
| STGCN adapter behind same interface | Phase 3 telemetry gate |
| Tier 2/3 auto-switch via M14 health probes | M14 GovernanceState |
| Auto-ripple on `EventNormalized` | On-demand API sufficient for hackathon |

---

## Version history

| Version | Change |
|---|---|
| 0.4.0 | M04 PropagationEngine — GCDH ripple, cascade risk, active maps, config |

**Next module:** M05 HotspotService — observed DBSCAN clusters + predicted Poisson intensity.
