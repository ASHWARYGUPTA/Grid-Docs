# M02 — FeatureGraphService (Implementation Record)

**Version:** 0.2  
**Backend path:** `backend/src/grid_unlocked/features/`  
**Status:** Implemented (MVP)  
**Spec reference:** [IMPLEMENTATION_MODULES.md § M02](../IMPLEMENTATION_MODULES.md) · [ML_MODELS_PRD.md](../ML_MODELS_PRD.md)

---

## Purpose

M02 materializes **leakage-safe feature vectors** for every normalized incident. It eliminates duplicated graph/prior logic across M03–M07 by providing a single `GET /features/{event_id}` contract.

On startup, historical priors and bias weights are seeded from `data/astram_events.csv`. On each `EventNormalized` event, features are materialized asynchronously, cached in Redis, and snapshotted to Postgres.

---

## What is implemented

### API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/features/{event_id}` | Full `FeatureVector` (cache hit ≤50 ms target) |
| POST | `/features/batch` | Batch read (up to 100 event IDs) |
| GET | `/priors/corridor-cause/{corridor}/{cause}` | Historical closure rate + median ICT |
| GET | `/graph/centrality/{node_id}` | Corridor centrality (MVP stub) |
| GET | `/graph/neighbors/{node_id}?hops=1-5` | Adjacent corridor nodes for GCDH |

### Event bus subscription

| Event | Handler | Action |
|---|---|---|
| `EventNormalized` | `subscriber._handle_normalized` | Async materialize + Redis cache + DB snapshot |
| `EventClosed` | `subscriber._handle_closed` | Delete Redis feature cache entry |

Materialization runs in a background `asyncio.create_task` so M01 ingest ACK is not blocked.

### FeatureVector outputs

All fields are **leakage-safe** — knowable at `start_datetime` only.

| Category | Fields |
|---|---|
| Temporal (IST) | `hour_ist`, `dow`, `hour_sin/cos`, `dow_sin/cos`, `is_peak_hour`, `is_weekend` |
| Bias correction | `reporting_bias_weight` (REQ-BIAS-001) |
| Graph / spatial | `graph_node_id`, `betweenness_norm`, `degree_norm`, `h3_res7`, `h3_res9`, `is_named_corridor` |
| Historical priors | `corridor_cause_closure_rate`, `corridor_cause_median_ict_h`, `duration_prior_h`, `cause_median_resolution_global_h`, `low_confidence_priors` |
| Context | `veh_complexity_score`, `simultaneous_events_2km` |
| Meta | `materialized_at`, `cache_hit` |

**Explicitly excluded** (per ML PRD denylist): `priority`, `requires_road_closure`, `closed_datetime`, observed duration.

---

## Algorithms

### Cyclical temporal encoding

```
hour_sin = sin(2π × hour_ist / 24)
hour_cos = cos(2π × hour_ist / 24)
dow_sin  = sin(2π × dow / 7)
dow_cos  = cos(2π × dow / 7)
```

Peak hours (IST): 07–10 and 17–21. Naive UTC datetimes from DB are converted via UTC → IST before encoding.

### Evening bias weights (REQ-BIAS-001)

Seeded from ASTraM CSV hourly event counts:

```
weight(h) = clip(median_hourly_count / logged_hourly_count, 0.5, 3.0)
```

Hours 14–18 IST receive elevated weights (typically 2.5–3.0×) to correct under-reporting during the evening peak.

### Corridor×cause priors

Seeded from 8,173 historical incidents:

| Prior type | Rows seeded | Fallback |
|---|---|---|
| `hour_bias_weights` | 24 (one per hour) | weight = 1.0 |
| `corridor_cause_priors` | 217 combinations | cause-global prior |
| `cause_priors` | 15 cause classes | default (8.3% closure, 1.0 h ICT) |

Lookup logic:
- If corridor×cause has **≥ 5 samples** → use specific prior
- Else → fall back to cause-global prior (`low_confidence_priors=true`)
- Else → hardcoded defaults

### Vehicle complexity score

```
base: heavy_vehicle=1.0, truck=0.9, lcv=0.7, bmtc_bus=0.8, private_car=0.3, two_wheeler=0.2
default (unknown): 0.5
```

`cargo_material` and `age_of_truck` not yet in `NormalizedEvent` — deferred to M01 schema extension.

### Simultaneous active events (2 km)

Haversine query over `normalized_events` where `status=active`, excluding the current event. Bounding-box pre-filter for performance.

### Graph stub (MVP — OSM deferred)

Corridor-level centrality proxy until full OSM graph ingest:

| Corridor type | `betweenness_norm` range |
|---|---|
| ORR segments | 0.90 – 0.95 |
| Named arterial roads | 0.65 – 0.88 |
| Non-corridor | 0.15 |

Node ID format: `corridor:{name}` (e.g. `corridor:ORR East 1`).

Static neighbor map in `constants.py` (`CORRIDOR_NEIGHBORS`) feeds `/graph/neighbors` for M04 GCDH.

### Caching

| Store | Key pattern | TTL |
|---|---|---|
| Redis | `feature:{event_id}` | 24 h |
| In-memory fallback | same key | if Redis unavailable |
| Postgres | `feature_snapshots` | permanent (M13 offline) |

---

## Source files

| File | Responsibility |
|---|---|
| `router.py` | FastAPI routes |
| `service.py` | FeatureService orchestration |
| `materializer.py` | Assembles `FeatureVector` from event + priors |
| `temporal.py` | IST conversion, cyclical encoding |
| `graph_stub.py` | Corridor centrality + neighbors (OSM placeholder) |
| `priors_loader.py` | CSV → DB seed on startup |
| `repository.py` | Prior lookups, 2 km count, snapshot persistence |
| `cache.py` | Redis + in-memory feature cache |
| `subscriber.py` | Event bus registration |
| `constants.py` | Peak hours, corridor centrality, veh bases |
| `schemas.py` | `FeatureVector`, `CorridorCausePrior`, graph models |

---

## Database tables

| Table | Purpose |
|---|---|
| `hour_bias_weights` | Per-hour IST reporting bias (PK: `hour_ist`) |
| `corridor_cause_priors` | Closure rate + median ICT per corridor×cause |
| `cause_priors` | Global cause-level fallbacks |
| `feature_snapshots` | Offline feature JSON per event (M13 training) |

Priors auto-seed on app startup if tables are empty (`main.py` lifespan → `FeatureService.ensure_priors_seeded()`).

---

## Tests (6)

File: `backend/tests/test_features.py`

| Test | Verifies |
|---|---|
| `test_features_materialized_after_ingest` | Ingest → async materialize → GET /features |
| `test_evening_bias_weight_higher_than_morning` | REQ-BIAS-001: hour 16 weight > hour 8 |
| `test_corridor_cause_prior_endpoint` | GET /priors/corridor-cause/Mysore Road/vehicle_breakdown |
| `test_graph_centrality_orr_high` | ORR centrality > Non-corridor |
| `test_feature_cache_hit` | Second GET returns `cache_hit=true` |
| `test_features_batch` | POST /features/batch returns multiple vectors |

---

## Deferred (not yet implemented)

| Capability | Planned phase |
|---|---|
| Full OSM graph + NetworkX betweenness | Phase 2 |
| Redis GEO index for 2 km counts | Phase 1.5 (currently DB Haversine) |
| Rolling 30d/7d prior windows (live refresh) | Phase 1.5 (currently static CSV seed) |
| `speed_ratio_corridor` from TomTom | Phase 2 |
| PostGIS spatial joins for zone imputation | Phase 1.5 |
| Tier 2/3 degradation (static priors only) | Phase 1.5 |
| mBERT / NLP features from description | Phase 2 |

---

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `GRID_REDIS_URL` | `redis://localhost:6379/0` | Feature cache |
| `GRID_ASTRAM_CSV_PATH` | `data/astram_events.csv` | Prior seed source |
| `GRID_DATABASE_URL` | SQLite / Postgres | Prior + snapshot storage |

---

## Example

```bash
# After ingesting an event (M01)
curl http://localhost:8000/features/FKID001

# Prior lookup
curl "http://localhost:8000/priors/corridor-cause/Mysore%20Road/vehicle_breakdown"

# Graph centrality (M04 prep)
curl "http://localhost:8000/graph/centrality/corridor:ORR%20East%201"
```

Sample response fields:

```json
{
  "event_id": "FKID001",
  "hour_ist": 16,
  "reporting_bias_weight": 3.0,
  "betweenness_norm": 0.80,
  "duration_prior_h": 0.64,
  "corridor_cause_closure_rate": 0.0602,
  "h3_res7": "8861812a15fffff",
  "simultaneous_events_2km": 2,
  "low_confidence_priors": false,
  "cache_hit": false
}
```

---

## Integration points

```
M01 EventNormalized ──► M02 subscriber (async)
                              │
                              ├── Redis cache (feature:{id})
                              ├── feature_snapshots (Postgres)
                              └── GET /features/{id}
                                      │
                                      ▼
                               M03 ImpactEngine (next)
                               M04 PropagationEngine
                               M07 DispatchOrchestrator
```

**Next module:** M03 ImpactEngine — consumes `FeatureVector` for LightGBM closure + Cox PH ICT bands + RCI.
