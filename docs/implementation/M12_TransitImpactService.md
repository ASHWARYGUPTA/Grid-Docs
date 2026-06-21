# M12 — TransitImpactService (Implementation Record)

**Version:** 1.0
**Backend path:** `backend/src/grid_unlocked/transit/`
**Status:** Implemented (MVP, stubbed per spec — mock GTFS-RT, static route-corridor mapping)
**Spec reference:** [IMPLEMENTATION_MODULES.md § M12](../IMPLEMENTATION_MODULES.md)

---

## Purpose

Corridor closures disproportionately affect BMTC passengers. M12 overlays mock BMTC schedule data with M03's predicted corridor delay to produce a passenger-delay index for command briefings — advisory only, never bus dispatch/rerouting control. The spec explicitly marks this module **"Hackathon MVP: stubbed"** — mock GTFS-RT and a static route-corridor mapping; Phase 2 is live BMTC integration.

---

## Key findings from reading the existing codebase

- **No BMTC/GTFS/transit data exists anywhere in this repo** (`data/` has only ASTraM CSVs). The route-corridor mapping in `bmtc_registry.py` is invented synthetic data, deliberately mirroring M11's `vms/board_registry.py` stub pattern (hardcoded dict, same non-error fallback philosophy for unmapped corridors).
- **The spec's Tier 1/Live-GTFS-RT vs Tier 2/scheduled-timetable degradation collapses to identical behavior in this MVP** — there is no live GTFS-RT feed to differentiate "live" from "scheduled" yet, so both tiers run the same mock-data computation. Only **Tier 3** is behaviorally distinct: it returns a static advisory string instead of a computed index, mirroring M14's documented "Tier 3 = last-resort, trust nothing computed" stance used elsewhere in this codebase.
- **`get_governance()`** (`recommendations/governance.py`) — the same zero-I/O synchronous tier read used by M07/M09/M10/M11 — is reused directly for the Tier 3 gate, rather than the async/DB-backed `GovernanceService.get_tier()` (which exists for the `/governance/tier` endpoint itself, not for hot-path reads).
- **M03's `ImpactService.score(event_id).ict_p50_h`** is the spec's "predicted delay" multiplier, applied as `ict_p50_h * 60` minutes per affected route.
- **No module calls M12 in this pass.** Unlike M10/M11 (wired into M09's `approve()`), the spec defers M12's dashboard panel integration explicitly to Phase 2 ("transit impact panel on high-severity cards (Phase 2)"). M12 is implemented as a standalone, independently-queryable module — not wired into M09's `ActionCard` or M15's dashboard. This is a spec-aligned boundary, not an oversight (see Known limitations).
- **`transit_impact_cache`, TTL 15 min** is the spec's only storage requirement — a plain cache row, not an audit trail (M12 is advisory, so none of M10/M11's 7-year retention requirement applies).

---

## Core behavior

### Route-corridor mapping (`bmtc_registry.get_routes_for_corridor`)

Hardcoded dict of ~10 synthetic Bengaluru BMTC routes mapped to ~10 corridors with an overlap fraction each. Partial keyword matching (same as `vms/board_registry.py`) so corridor suffix variants still resolve. Unmapped/unknown corridors fall back to two default routes rather than erroring — a query never fails just because a corridor string didn't match, matching M11's established non-422 philosophy.

### Mock GTFS occupancy (`mock_gtfs.MockGtfsClient.get_occupancy`)

Returns each route's static default occupancy (45 passengers/bus peak per spec, the same `DEFAULT_OCCUPANCY` constant `bmtc_registry.py` already defines) — there is no real-time AVL load data in this MVP.

### Impact computation (`TransitImpactService.compute_impact`)

1. 404 if `event_id` is unknown.
2. **Tier 3 gate** (`get_governance().tier == "3"`) → return immediately with `degraded=True`, `passenger_delay_index=0.0`, `affected_routes=[]`, and a static `advisory_message` ("BMTC services may be affected near {corridor}.") — no per-route computation, matching the spec's Tier 3 behavior.
3. **Cache check** — `transit_impact_cache` row for this `event_id`, TTL 15 min (checked at read-time, same "no cleanup job" pattern as other caches in this codebase). Cache hit returns the cached payload with `cached=True` and a fresh `latency_ms`.
4. **Cache miss** — `ImpactService.score(event_id).ict_p50_h * 60` → `predicted_delay_min`; for each route from `get_routes_for_corridor(corridor)`: `occupancy = MockGtfsClient.get_occupancy(route_id)`, `passenger_delay_index += occupancy * predicted_delay_min * overlap_fraction` (spec's exact formula). `transfer_overload_risk = min(1.0, num_affected_routes / 5)` — an MVP stand-in for the spec's unspecified `f(diversions ∩ transfer_hub, headway_reduction)`, since no transfer-hub or headway data exists in this codebase to compute the real thing (see `D-M12-03`).
5. Result is cached and returned.

### `GET /transit/routes/affected?corridor=`

Thin wrapper around `bmtc_registry.get_routes_for_corridor()` — no event lookup, no ICT computation, `predicted_delay_min=0.0` placeholder (this endpoint answers "which routes overlap this corridor," not "what's the current delay").

### `GET /mock/transit/demo`

Hardcoded canned response using a fixed demo corridor (`ORR East 1`) and a fixed delay constant — no DB/event/governance lookup at all, trivially satisfying the spec's "≤50ms" mock latency contract and "consistent index for demo corridor" testing decision.

---

## API

| Endpoint | Behavior |
|---|---|
| `GET /transit/impact/{event_id}` | `TransitImpactIndex` — passenger-delay index, affected routes, tier/degraded state |
| `GET /transit/routes/affected?corridor=` | Route list + overlap fractions for a corridor, no event needed |
| `GET /mock/transit/demo` | Canned demo index, hackathon UI/Swagger use |

---

## Storage

`transit_impact_cache` — `event_id` (PK), `payload_json` (the full serialized `TransitImpactIndex`), `expires_at`, `created_at`. TTL checked at read-time in `TransitImpactRepository.get_cached()`; the SQLite naive/aware datetime comparison caveat (datetimes round-trip as naive even when stored tz-aware, the same gotcha already documented in `learning/buffer.py` and fixed during M16) is handled by comparing against a same-awareness "now."

---

## Source files

| File | Responsibility |
|---|---|
| `bmtc_registry.py` | Hardcoded route inventory + corridor→route overlap map |
| `mock_gtfs.py` | `MockGtfsClient` — static occupancy stand-in for live GTFS-RT |
| `schemas.py` | `TransitImpactIndex`, `AffectedRoute`, `AffectedRoutesResponse`, `MockTransitDemoResponse` |
| `repository.py` | `transit_impact_cache` reads/writes, TTL check |
| `service.py` | `TransitImpactService` — Tier 3 gate, cache, delay-index computation |
| `router.py` | 3 endpoints |

Modified: `db/models.py`/`db/session.py` (1 new table), `main.py` (router include).

---

## Tests

`backend/tests/test_transit.py` — 9 tests: mock demo returns a consistent canned index across calls; mock demo latency under 50ms; `/transit/routes/affected` for a mapped corridor (`Hosur Road`) returns the expected known route; unmapped corridor falls back to default routes (non-error); no `corridor` query param returns the default list, not a 422; `/transit/impact/{event_id}` 404 on unknown event; impact computation uses M03's `ict_p50_h` as the exact delay multiplier (verified by monkeypatching `ImpactService.score` to a fixed value and hand-computing the expected `passenger_delay_index`); Tier 3 returns a static advisory with `degraded=True` and no per-route breakdown (monkeypatch `settings.governance_tier = "3"`); cache hit within the 15-min TTL skips recomputation (verified by spying on `ImpactService.score`'s call count across two requests for the same event).

Full backend suite: 216 passed (207 prior + this module's 9), the same 6 pre-existing unrelated `test_dashboard.py` failures excluded.

---

## Known limitations (MVP, deliberate scope reductions per spec's "stubbed" instruction)

- `D-M12-01` — `MockGtfsClient` stands in for real BMTC GTFS-RT; Phase 2 replaces it with live AVL/load-factor data.
- `D-M12-02` — Route-corridor mapping is a hardcoded Python dict, not a real route-polyline ∩ corridor-buffer spatial join — Phase 2 swaps this in once real BMTC route geometry is available.
- `D-M12-03` — `transfer_overload_risk` is a simple route-count heuristic (`min(1.0, routes/5)`), not the spec's `f(diversions ∩ transfer_hub, headway_reduction)` — no transfer-hub or headway data exists in this codebase to compute the real formula.
- `D-M12-04` — Not wired into M09's `ActionCard` or M15's dashboard — the spec explicitly defers the "transit impact panel on high-severity cards" to Phase 2; M12 is a standalone, independently-queryable module in this pass.
- Tier 1 and Tier 2 currently behave identically (no live GTFS-RT exists to differentiate "live" from "scheduled timetable only") — only Tier 3's static-advisory branch is behaviorally distinct.
- Out of scope per spec, confirmed untouched: BMTC dispatch control, Namma Metro, citizen notification delivery.

---

## Next

This was the last unbuilt module — **M01–M18 are now all implemented and documented.** Remaining work is exclusively Phase 1.5/2 per each module's own deferred markers:

- Wiring M12 into M09's `ActionCard` and M15's dashboard panel (Phase 2, per spec).
- Live BMTC GTFS-RT integration replacing `MockGtfsClient` (Phase 2).
- Real spatial join replacing the hardcoded corridor→route map (Phase 2).
- The broader Phase 1.5/2 backlog already itemized across M10/M11 (real station/webhook vendor APIs), M16 (real Service Worker), M18 (rate limiting, H3-cell subscriptions, ASTraM push bridge), and M14 (live promotion automation).
