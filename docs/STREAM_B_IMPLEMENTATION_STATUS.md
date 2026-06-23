# Stream B — Live Map & Real-Time: Implementation Status

Status: **complete**, including the B-4 bonus. All tasks B-1 through B-5 from
`Grid_Unlocked_Build_Guide.md` are implemented and verified.

## What was built

### B-1 · Live incident pin layer
- `api.incidentsActive()` added to [frontend/lib/api.ts](../frontend/lib/api.ts), backed by
  `GET /api/v1/incidents/active`.
- Pins rendered as `window.mappls.Marker` instances inside
  [map-panel.tsx](../frontend/app/live/_components/map-panel.tsx) (kept in this file rather
  than a separate `incident-layer.tsx`, per explicit decision — see Deviations below).
- Coloured by RCI via the exported pure function `rciColor()`: null → grey,
  `>0.7` red, `>0.4` orange, `>0.2` yellow, else green — matching the action
  card's existing severity colour bands.
- Diffed by `event_id` against `incidentMarkersRef` on every refresh; stale
  markers are removed, changed-colour markers are recreated (the SDK has no
  documented way to swap a marker's `html` post-construction).
- Clicking a pin calls `onSelectEvent(eventId)`, which `live/page.tsx` wires
  to the existing action-card-selection state — opens the real card, not a
  stub.

### B-2 · Wire the `incident` delta
- `"incident"` added to `DeltaScope` in [frontend/lib/types.ts](../frontend/lib/types.ts)
  (additive, as required).
- `map-panel.tsx` refreshes incident pins whenever `lastDelta.scope` is
  `"incident"` or `"card"` (the latter because approve/reject/close can
  change an event's active status, which also needs a pin refresh).
- Backend side: a new `incident_subscriber` was added on the ingest fan-in
  bus so an `incident`-scoped `DashboardDelta` fires within the same
  WebSocket round-trip as ingest — verified end-to-end in
  `frontend/tests/e2e/dashboard.spec.ts` (pin appears without waiting for
  any poll).

### B-3 · Diversion route overlay
- File: kept inside `map-panel.tsx` rather than a separate
  `diversion-overlay.tsx` (see Deviations).
- Routes drawn as MapLibre GL `line` layers using `route.waypoints`
  (corridor-centroid-resolved lat/lng from Stream A's M17 work) — **not**
  Mappls Directions. The Mappls SDK v3.0 has no Directions/Polyline API;
  confirmed against its own minified source before deciding to draw
  straight corridor-level polylines via the underlying MapLibre map
  instance directly (the SDK's existing `getLayer`/`removeLayer` methods
  already prove it wraps MapLibre).
- Routes with fewer than 2 resolved waypoints are skipped entirely — the
  existing text list is left as the only representation, with an added
  "Map geometry unavailable for this route." note in
  [action-card-panel.tsx](../frontend/app/live/_components/action-card-panel.tsx).
  Coordinates are never synthesized.
- Rank-ordered colours/widths (rank 1 most prominent), with cross-highlight:
  hovering a route row in the card's Routes tab widens/brightens its line
  and dims the others (`setPaintProperty`, no redraw).
- Selecting a card draws its routes; clearing the selection (or switching
  cards) removes the previous routes first — old layers/sources are cleared
  at the top of the effect rather than via a returned cleanup, since the map
  instance outlives the effect and a second removal would throw.

### B-4 (bonus) · Cascade overlay
- Fetches `api.propagationActive()` (`GET /propagation/active`, already
  existed) and filters client-side for the `PropagationMap` whose
  `event_id` matches the selected card — no new per-event endpoint was
  needed.
- Drawn as two MapLibre layers: graded `circle` nodes (radius and colour
  both scaled by `node.risk`, same RCI colour bands as incident pins) and
  `line` edges connecting each node back to its parent, derived by parsing
  `parent_edge` (`"{parentNodeId}->{thisNodeId}"`, as encoded by the
  backend's GCDH algorithm in `propagation/gcdh.py`).
- Nodes whose `lat`/`lng` are `null` (no corridor centroid on record) are
  skipped — same never-fabricate rule as B-3's waypoints.
- Gated behind a new "Cascade" toggle button (disabled when no card is
  selected), alongside the existing Observed/Predicted toggles. Layers are
  cleared at the top of the effect on toggle-off, selection change, or
  selection clear.

### B-5 · Types & tests
- All new types (`ActiveIncident`, `ActiveIncidentsResponse`,
  `CorridorCentroid`, `CorridorsResponse`, `RouteWaypoint`, and the
  `lat`/`lng` additions to `PropagationNode`) are additive in
  `lib/types.ts`.
- Unit tests (Vitest): `rciColor()` threshold tests
  (`tests/unit/incident-layer.test.ts`) and diversion hover/cross-highlight
  wiring (`tests/unit/diversion-overlay.test.tsx`).
- E2E (Playwright, `tests/e2e/dashboard.spec.ts`): a posted ingest appears
  in `/api/v1/incidents/active` with matching `event_id`/`corridor`/`lat`/
  `lng`/`status: "active"`, and a raw WebSocket client observes an
  `incident`-scoped delta on the same ingest.

## Deviations from the guide (and why)

- **Single-file implementation.** The guide names new files
  (`incident-layer.tsx`, `diversion-overlay.tsx`). All map-drawing logic was
  kept inside the existing `map-panel.tsx` instead — explicit choice made
  via `AskUserQuestion` mid-implementation, since this was built solo
  rather than across three parallel Stream B developers, and the map
  instance/refs were already centralized there.
- **No Mappls Directions.** The guide says "prefer Mappls Directions...
  fall back to a straight corridor-level polyline." Directions does not
  exist in this SDK version, so the fallback path is the only path — there
  was no preference to express.

## Cross-stream contract notes (§6.1 in the build guide)

- B-1 pins: consumed Stream A's real `/api/v1/incidents/active` directly
  (Stream A had already landed by the time this work started, so no stub
  was needed).
- B-2 delta: `"incident"` scope added to the shared `DeltaScope` union.
- B-3 overlay: consumes Stream A's `waypoints` field on `DiversionRoute`,
  resolved server-side via M17 corridor centroids.
- B-4 overlay: consumes Stream A's `lat`/`lng` additions to
  `PropagationNode` (same M17 centroid resolution).

## Bugs found and fixed along the way

- **Regression (introduced by this work):** the new `incident_subscriber`
  causes two WS deltas per ingest (`hotspot` + `incident`) instead of one,
  breaking two existing backend tests that assumed exactly one delta per
  ingest. Fixed by updating `test_dashboard.py` to drain messages by scope
  (`_receive_until_scope` helper) instead of assuming delta order.
- **Pre-existing backend bug (not introduced by this work, but exposed by
  the extra ingest traffic from new tests):** `hotspots/cusum.py`'s
  module-level `cusum_tracker` singleton crashed comparing naive vs
  timezone-aware datetimes when different test files' timestamps mixed in
  its sample buffer within the same pytest process. This was the actual
  root cause of the "37–43 pre-existing test failures" previously
  documented as unrelated flakiness in `STREAM_A_IMPLEMENTATION_STATUS.md`.
  Fixed with a one-line UTC-normalization in `CusumTracker.record()`. Full
  backend suite went from 37–43 failures to **233 passed, 0 failed**,
  confirmed stable across repeated runs.

## Verification

- `npx tsc --noEmit` — clean.
- `pnpm test:unit` — 41/41 passing (10 files).
- `pnpm build` — succeeds.
- `pnpm lint` — no new errors in any file touched by this work (pre-existing
  unrelated errors remain in `context/auth-context.tsx` and
  `hooks/use-mobile.ts`).
- Backend: `uv run pytest` — 233 passed, 0 failed.
- E2E (`dashboard.spec.ts`): all 6 tests passing against a live stack
  (Postgres/Redis via Docker Compose, backend on :8100, frontend on :3100,
  real Mappls key) across 4+ consecutive runs.
- Visual confirmation via Playwright screenshots against the live stack:
  real coloured incident pins on real Bengaluru geography, a populated
  action card, and a real diversion polyline drawn from resolved
  corridor-centroid waypoints (B-1 through B-3).
- B-4's cascade overlay was verified via typecheck + unit tests + build
  only — the live stack was in an indeterminate state by the time B-4 was
  implemented (stale process on port 3100 not controllable from the
  sandboxed shell), and live visual re-verification was explicitly skipped
  by user decision rather than attempting to reclaim the stack.
