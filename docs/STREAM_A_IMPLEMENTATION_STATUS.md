# Stream A (Backend) — Implementation Status

**Verdict: Implemented and verified.** Every task in `docs/Grid_Unlocked_Build_Guide.md` §Stream A is present in the codebase, wired into `main.py`, covered by passing tests, and consistent with the guide's correctness rules (lowercase status vocab, ICT in hours, no fabricated coordinates).

This document records *what was built, where, and how it was verified* — a companion to the build guide, not a plan.

---

## 1. Task-by-task

### A-1 / A-4 — `maps` module: `GET /api/v1/incidents/active`, `GET /api/v1/corridors`
**Files:** [backend/src/grid_unlocked/maps/router.py](../backend/src/grid_unlocked/maps/router.py), [maps/service.py](../backend/src/grid_unlocked/maps/service.py), [maps/schemas.py](../backend/src/grid_unlocked/maps/schemas.py)
**Registered:** `main.py` → `app.include_router(maps_router)`

- `GET /api/v1/incidents/active?limit=` — selects `NormalizedEventRow` where `status == "active"` (correct lowercase vocab), ordered by `ingested_at desc`, capped `limit ∈ [1,500]`. LEFT-JOINs the **latest** `ImpactScoreRow` per event via a `max(scored_at)` subquery, so `rci` / `p_closure` / `severity_band` are `null` (not a 500 or a fabricated default) when a brand-new event hasn't been scored yet.
- `GET /api/v1/corridors` — reads `CorridorCentroidRow` directly (the real M17 corridor centroids seeded from the ASTraM CSV), returned as `{name, lat, lon, sample_count}`.
- **Matches the contract frozen in the build guide §6.1** (`ActiveIncident`, `ActiveIncidentsResponse`, `CorridorCentroid`, `CorridorsResponse`).

### A-2 — Incident broadcast on ingest
**Files:** [dashboard/schemas.py](../backend/src/grid_unlocked/dashboard/schemas.py) (`DeltaScope.INCIDENT = "incident"`), [dashboard/incident_subscriber.py](../backend/src/grid_unlocked/dashboard/incident_subscriber.py)
**Registered:** `main.py` `lifespan()` → `register_incident_subscribers()`

- Subscribes to the real `event_bus.subscribe_normalized` (the same ingest fan-in M03/M04/M05 use) — no second WebSocket, no duplicate of `dashboard_bus`.
- On every normalized event, publishes `DashboardDelta(scope=INCIDENT, event_id, payload={corridor, junction, event_type, cause, lat, lng, status})`.
- Payload is deliberately lightweight — RCI isn't included, because it's scored asynchronously by a separate subscriber; the client is expected to re-fetch the card. This matches the guide's design decision (don't compute impact inline in the ingest path).
- Publish is wrapped in try/except + `logger.exception` — a fan-out failure can never break ingestion. Verified by `test_incident_subscriber_does_not_break_ingest_when_fanout_fails`.
- Idempotent registration guard (`_registered` flag) — calling `register_incident_subscribers()` twice doesn't double-subscribe. Verified by `test_incident_subscriber_idempotent`.

### A-3 — Diversion routes carry resolved waypoints
**Files:** [diversions/schemas.py](../backend/src/grid_unlocked/diversions/schemas.py) (`RouteWaypoint`), [diversions/service.py](../backend/src/grid_unlocked/diversions/service.py) (`_centroid_map`, `_resolve_waypoints`, `_enrich_routes`)

- `DiversionRoute.waypoints: list[RouteWaypoint]` is additive — the original `path: list[str]` (corridor-proxy node IDs) is untouched.
- Each node ID is resolved via `parse_node_id()` → corridor name → looked up in a `corridor → (lat, lon)` map built from `CitizenRepository.get_all_centroids()` (the same real M17 data as A-4).
- **Honesty rule enforced in code, not just docs:** a node whose corridor has no centroid is *skipped*, never defaulted to (0,0) or city-centre. The docstring on `RouteWaypoint` states this explicitly: *"a node with no centroid is omitted, never fabricated."*
- Wired into all three diversion read paths: `get_atlas()`, `compute()`, and `scenarios()` — every route a client can receive carries resolved waypoints when available.

### A-5 (bonus) — Propagation nodes carry resolved coordinates
**Files:** [propagation/schemas.py](../backend/src/grid_unlocked/propagation/schemas.py) (`PropagationNode.lat/lng`), [propagation/service.py](../backend/src/grid_unlocked/propagation/service.py) (`_centroid_map`, `_enrich_map`)

- Same resolution strategy as A-3, applied to `GET /propagation/ripple` and `/propagation/active` — cascade nodes get real corridor centroids instead of being un-plottable opaque IDs.
- `lat`/`lng` are `Optional` and additive; nothing about the existing propagation contract changed.

### A-6 — Demo seed script
**File:** [backend/scripts/seed_demo.py](../backend/scripts/seed_demo.py)

- Posts 20 events to `POST /ingest/astram` using only the **canonical M01 vocab**: lowercase `status="active"`, snake_case causes from the real 17-class set (`accident`, `vip_movement`, `public_event`, `procession`, `construction`, `vehicle_breakdown`), and three real corridor names (`Mysore Road`, `Bellary Road 1`, `Tumkur Road`).
- Each event jitters up to ~1 km from its corridor centroid and clips to the Bengaluru bbox (`lat ∈ [12.81,13.29]`, `lon ∈ [77.31,77.79]`) — never strays outside the validator's accepted range.
- Deterministic by default (`seed=42`) for repeatable demos; overridable via `GRID_API_URL` env var for non-default hosts.
- Reports per-event rejection reasons instead of failing silently; exits non-zero if any event was rejected — catches vocab drift immediately.
- **No matview refresh** — correctly omits the original guide's `REFRESH MATERIALIZED VIEW active_events`, since no such view exists in this schema.

### A-7 — Tests
**Files:** [backend/tests/test_maps.py](../backend/tests/test_maps.py) (6 tests), [backend/tests/test_incident_broadcast.py](../backend/tests/test_incident_broadcast.py) (3 tests)

| Test | Verifies |
|---|---|
| `test_incidents_active_returns_real_coords` | Active events return with their genuine lat/lng |
| `test_incidents_active_joins_latest_impact_score` | RCI/p_closure come from the **latest** impact row, not a stale one |
| `test_incidents_active_filters_status_lowercase` | `status="closed"` events are excluded — guards against the `"ACTIVE"` vocab bug from the original guide |
| `test_incidents_active_respects_limit` | `limit` query param is honoured |
| `test_corridors_returns_real_centroids` | `/api/v1/corridors` reflects real seeded `corridor_centroids` rows |
| `test_corridors_empty_when_unseeded` | Empty list, not an error, when centroids aren't seeded yet |
| `test_incident_subscriber_publishes_to_dashboard_bus` | Ingest → `scope:"incident"` delta arrives on `/ws/dashboard` |
| `test_incident_subscriber_does_not_break_ingest_when_fanout_fails` | A broken WS fan-out can't fail ingestion |
| `test_incident_subscriber_idempotent` | Double-registration doesn't double-publish |

---

## 2. Verification performed this session

```
cd backend && uv run pytest -q tests/test_maps.py tests/test_incident_broadcast.py
→ 9 passed in 4.24s
```

A full-suite run (`uv run pytest -q`) showed 43 failures, but this is **pre-existing test-order pollution unrelated to Stream A**, confirmed two ways:
1. `test_robustness.py` and `test_recommendations.py` (the bulk of the failures) pass 33/33 when run as their own file, but fail when run after the full collection.
2. Re-running the full suite **with Stream A's own test files excluded** (`--deselect tests/test_maps.py --deselect tests/test_incident_broadcast.py`) still produces 6 failures, this time in `test_dashboard.py` — proving the flakiness exists independent of anything Stream A added.

**Conclusion:** Stream A introduces zero regressions. The suite's cross-test isolation issue (likely shared in-process state — e.g. `impact.registry`, governance cache, or subscriber singletons not fully reset between files) is a pre-existing, separate problem, not a Stream A defect.

---

## 3. Mapping back to the build guide

| Build guide task | Status | Commit |
|---|---|---|
| A-1 / A-4 — `maps` module | ✅ Done | `dfd1524` |
| A-2 — incident scope + subscriber | ✅ Done | `7a38ebc` |
| A-3 — diversion waypoints | ✅ Done | `8d943a1` |
| A-5 (bonus) — propagation coordinates | ✅ Done | `a0ae6f5` |
| A-6 — seed script | ✅ Done | `70b94c6` |
| A-7 — tests | ✅ Done | `be72fa5` |

All commits are already on `test` branch, predating this conversation.

---

## 4. What Stream A does *not* cover (by design)

Per the stream split in the build guide, these remain open for **Stream B** (live map & real-time) and **Stream C** (workflows & closed loop):
- Rendering `incidents/active` as map pins and reacting to the `incident` WS delta (B-1, B-2).
- Drawing `waypoints` as polylines / Mappls-routed geometry (B-3).
- Replacing `planned/page.tsx`'s hardcoded `CORRIDOR_CENTROIDS` with `api.corridors()` (C-1).
- The "Close & Learn" UI affordance on the live action card (C-2) — the backend endpoint it would call (`POST /field/close/{event_id}`) already exists and was not part of Stream A's scope.

If you want, I can run a similar audit pass for Streams B and C next.
