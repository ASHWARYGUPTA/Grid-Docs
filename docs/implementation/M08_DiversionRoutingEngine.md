# M08 — DiversionRoutingEngine (Implementation Record)

**Version:** 0.8  
**Backend path:** `backend/src/grid_unlocked/diversions/`  
**Status:** Implemented (MVP)  
**Spec reference:** [IMPLEMENTATION_MODULES.md § M08](../IMPLEMENTATION_MODULES.md)

---

## Purpose

M08 provides **top-k diversion routes** for closure-prone junctions using a pre-computed **diversion atlas** and on-demand **Yen's k-shortest paths** on the M02 corridor graph. Includes **cyclic gridlock detection** for routes that re-enter closed zones.

Replaces the M06 static diversion stub with graph-backed routes.

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/diversions/atlas/{junction_id}` | Pre-computed top-k routes (≤80 ms) |
| GET | `/diversions/atlas` | List all atlas junction IDs |
| POST | `/diversions/compute` | On-demand k-shortest for cache miss |
| GET | `/diversions/scenarios/{event_id}` | Event-ranked alternatives + auto-suggest flag |
| POST | `/diversions/validate` | Cyclic gridlock check on proposed path |

---

## Algorithms

### Atlas (offline / import-time)

- 12 junction entries covering Mysore Road, ORR East 1, Bellary Road 1 + generic fallbacks
- k-shortest paths on M02 `CORRIDOR_NEIGHBORS` graph
- Closed corridor node excluded from paths
- Ranked by ETA delta (minutes), gridlock flag deprioritized

### Yen's k-shortest (on-demand)

- Dijkstra + spur paths for k=1..3
- Edge-disjoint where possible
- Tier 2: atlas only; Tier 3: static generic-1 per corridor

### Gridlock detection

- Re-entry into `closed_node_id` after exit
- Duplicate nodes in path (cycle)
- Hop count > `diversion_max_hops + 2` → capacity exceeded

### Auto-suggest policy

`auto_suggest = p_closure > 0.35 AND is_peak_hour` (from M03 + M02)

---

## Integration

| Module | Usage |
|---|---|
| M02 | Corridor graph (`CORRIDOR_NEIGHBORS`, centrality weights) |
| M03 | `p_closure` for scenario auto-suggest |
| M06 | `DiversionService.refs_for_corridor()` replaces stub |
| M09 | `/diversions/scenarios/{event_id}` feeds action cards |
| M11 | Route summaries for VMS text (Phase 1.5) |

---

## Source files

| File | Responsibility |
|---|---|
| `router.py` | FastAPI routes |
| `service.py` | Orchestration, M06 refs adapter |
| `atlas.py` | Pre-computed junction registry + build |
| `graph.py` | Dijkstra + Yen's k-shortest |
| `gridlock.py` | Cycle / re-entry detection |
| `schemas.py` | Request/response contracts |

---

## Configuration

| Setting | Default | Meaning |
|---|---|---|
| `diversion_k_default` | 3 | Routes returned per lookup |
| `diversion_max_hops` | 5 | Gridlock capacity hop budget |
| `closure_alert_threshold` | 0.35 | Auto-suggest p_closure gate |

---

## Tests

| File | Coverage |
|---|---|
| `test_diversions.py` | M08 unit tests (9) |
| `test_m08_requirements.py` | PRD compatibility gates (9) |
| `test_integration.py` | M01–M08 E2E wiring (11) |
| `test_robustness.py` | Cross-module resilience incl. M08 (22) |

Run: `uv run pytest tests/test_m08_requirements.py tests/test_integration.py tests/test_robustness.py -v`

---

```bash
curl http://localhost:8000/diversions/atlas/junction:ORR-Sarjapur

curl -X POST http://localhost:8000/diversions/compute \
  -H 'Content-Type: application/json' \
  -d '{"corridor":"Mysore Road","k":3}'

curl http://localhost:8000/diversions/scenarios/FKIDDIV0001
```

---

## Known limitations (MVP)

- Corridor-level graph stub — not full OSM segment geometry
- No PostGIS polyline storage (path = node ID list)
- No Phase 2 speed-based rerank
- Atlas refresh is import-time, not weekly job

---

## Next

- **M09** RecommendationAPI — unify M03–M08 into action cards
