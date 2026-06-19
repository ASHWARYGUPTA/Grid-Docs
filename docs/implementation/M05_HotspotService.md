# M05 — HotspotService (Implementation Record)

**Version:** 0.5  
**Backend path:** `backend/src/grid_unlocked/hotspots/`  
**Status:** Implemented (MVP)  
**Spec reference:** [IMPLEMENTATION_MODULES.md § M05](../IMPLEMENTATION_MODULES.md) · [ML_MODELS_PRD.md § M05](../ML_MODELS_PRD.md)

---

## Purpose

M05 unifies **observed** hotspot detection (where incidents cluster now) and **predicted** hotspot forecasting (where Poisson intensity models expect load). It prevents duplicated H3/DBSCAN logic in M09 and M15.

Outputs map layers for the command dashboard and spatial context for impact scoring (`simultaneous_events_2km`).

---

## What is implemented

### API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/hotspots/observed` | Top-10 DBSCAN clusters (active + 24 h recent events) |
| GET | `/hotspots/predicted?horizon_hours=4` | Poisson intensity forecast by corridor |
| GET | `/hotspots/anomalies` | CUSUM alerts in last 24 h |
| GET | `/hotspots/cell/{h3_res7}` | H3 cell history summary |

### Observed cluster fields

| Field | Description |
|---|---|
| `cluster_id` | Unique cluster identifier |
| `layer` | `observed` |
| `centroid_lat/lon` | Cluster centroid |
| `density` | Event count in cluster |
| `cause_entropy` | Shannon entropy over causes |
| `h3_cells` | H3 res7 cells covered |
| `corridors` | Corridors represented |
| `persistence_score` | 30-day frequency normalized [0, 1] |
| `label` | Optional name (static/singleton) |

### Predicted forecast fields

| Field | Description |
|---|---|
| `corridor` | Corridor zone |
| `expected_count` | Poisson E[count] over horizon |
| `baseline_count` | Historical average for horizon |
| `lift_pct` | Percent above baseline |

---

## Algorithms

### Observed — Haversine DBSCAN

1. Collect **active** + **last 24 h** events from `normalized_events`
2. Run DBSCAN with `metric='haversine'` on radian (lat, lon)
3. Parameters: `eps=0.005 rad (~500 m)`, `min_samples=5`
4. Aggregate cluster metadata: centroid, H3 cells, cause entropy, persistence
5. Cache result (TTL 5 min)

**Forbidden:** Euclidean DBSCAN on raw lat/lon degrees.

**Fallback chain:**
1. Live DBSCAN on observable events
2. Historical H3 DBSCAN from ASTraM CSV
3. Tier 3 static BTP black spots (includes Bellandur flyover)

### Predicted — Poisson GLM

```
log(E[count]) ~ hour_sin/cos + dow_sin/cos + is_weekend + corridor_fixed_effects
```

- Trained offline on ASTraM CSV corridor×hour counts at startup
- Forecast top-20 corridors for requested horizon (default 4 h)
- Cache TTL 6 h

### Anomaly — CUSUM

- Rolling 30-min corridor event rate vs CSV baseline
- Alert when rate ≥ **3σ** above baseline
- Events recorded via `EventNormalized` subscriber

### Cell history

- H3 res7 aggregation from full ASTraM CSV
- Returns total events, 30-day count, top causes/corridors, persistence score

---

## Source files

| File | Responsibility |
|---|---|
| `router.py` | FastAPI routes |
| `service.py` | Orchestration, cache, warm startup |
| `dbscan.py` | Haversine DBSCAN + cause entropy |
| `historical.py` | CSV index for cells, persistence, Poisson training |
| `poisson.py` | PoissonRegressor forecast |
| `cusum.py` | Anomaly tracker |
| `geo.py` | Haversine, H3 helpers, 2 km count |
| `cache.py` | Redis + in-memory observed/predicted cache |
| `repository.py` | Active + recent event queries |
| `static_blackspots.py` | Tier 3 BTP black spots |
| `subscriber.py` | CUSUM rate recording on ingest |

---

## Integration flow

```
M01 ingest → EventNormalized → CUSUM rate tracker
                    ↓
GET /hotspots/observed ← active + 24h events → Haversine DBSCAN
GET /hotspots/predicted ← Poisson GLM (CSV-trained)
                    ↓
              M09 ActionCard / M15 map layers
```

Historical index and Poisson model warmed in `main.py` lifespan via `HotspotService.warm()`.

---

## Tests

`backend/tests/test_hotspots.py` — 11 tests:

- Observed/predicted/anomalies/cell API endpoints
- Bellandur zone in historical top-10
- Haversine DBSCAN ≠ Euclidean-on-degrees
- Cause entropy on mixed-cause cluster
- CUSUM synthetic spike ≥ 3σ
- 2 km count matches brute-force Haversine
- Predicted layer distinct from observed

Run: `cd backend && uv run pytest`

---

## Deferred (not blocking MVP)

| Item | Target |
|---|---|
| HDBSCAN / KMeans beat boundaries | Phase 2 patrol planning |
| Weather covariate in Poisson | Phase 2 |
| Redis geo index for 2 km queries | Phase 1.5 (brute-force from CSV for now) |
| 5-min background refresh job | On-demand + cache TTL sufficient for hackathon |
| Hawkes process evaluation | Phase 3 (12+ months data) |
| Tier 2/3 auto-switch via M14 | M14 GovernanceState |

---

## Version history

| Version | Change |
|---|---|
| 0.5.0 | M05 HotspotService — observed DBSCAN, Poisson forecast, CUSUM anomalies, cell history |

**Next module:** M06 PlannedEventTemplateEngine — planned event packages with staffing/barricade templates.
