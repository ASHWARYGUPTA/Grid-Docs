# GRID UNLOCKED — Codebase-Grounded Build Guide (v2)

**Gridlock 2.0 | Flipkart × MapMyIndia (Mappls) × Bengaluru Traffic Police**

| Property | Value |
|---|---|
| Audience | 3 developers building **concurrently** — Claude Code ready |
| Backend | FastAPI · Python 3.12 · **uv** · SQLAlchemy async · PostgreSQL 16 + PostGIS · Redis 7 |
| Frontend | **Next.js 16.2.9 (App Router)** · **React 19** · **Tailwind 4** · shadcn/`@base-ui` · **pnpm** · **Mappls Web SDK v3** · `h3-js` · recharts |
| ML | LightGBM + isotonic (closure) · Cox PH (ICT) · DBSCAN + Poisson (hotspots) — **trained, do not retrain** |
| Streams | **A — Backend / Data APIs** · **B — Live Map & Real-Time** · **C — Workflows & Closed-Loop** |
| Purpose | Refactor + extend an **already-working** product. Close the operational loop and add map intelligence — with **100% real data**. |

> This document **supersedes** `docs/Grid_Unlocked_Implementation_Guide.docx`. That guide was written against a *hypothetical* scaffold (flat `routers/*.py`, `NormalizedEvent`, `get_db`, a `ConnectionManager`, a `ReplayBufferEntry` table, MapLibre, “route shells”). **None of that matches the real repo.** The real backend is a domain-modular FastAPI app implementing M01–M18, and the real frontend is a polished Next 16 / React 19 / Mappls app with a typed API client, a WebSocket hook, auth, and tests. See [Appendix B](#appendix-b--reality-vs-the-original-docx) for the full delta.

---

## 0. How to use this document

1. **Read your stream section end-to-end before writing code.** Each task gives exact file paths, real symbol names, a **Do / Don't** block, and acceptance criteria.
2. **Contract-first concurrency.** All three streams depend on a small shared contract surface (new TypeScript types + API methods + one WebSocket scope). Those contracts are frozen in [§6.1](#61--shared-contract-surface-freeze-this-first). Build against the contract, not against another stream's timing.
3. **The non-negotiable principle — no fake data.** Every number, pin, and route on screen must trace to a real endpoint backed by the real ASTraM corpus or a real model. Today the codebase honours this almost perfectly; there is exactly **one** hardcoded-coordinate smell to remove ([Feature 4](#feature-4--de-hardcode-planned-event-coordinates)). Do not add more.

### ⚠️ Five pitfalls that will waste your day

| # | Pitfall | Reality |
|---|---|---|
| P1 | "It's just Next.js." | **It is not.** Next 16 + React 19 + Tailwind 4 have breaking changes. `frontend/AGENTS.md` orders you to read `frontend/node_modules/next/dist/docs/` before writing frontend code. Heed it. |
| P2 | Using `get_db` / `NormalizedEvent` / `rci_score` / `created_at`. | DI is `get_session`; models are `…Row` in [backend/src/grid_unlocked/db/models.py](backend/src/grid_unlocked/db/models.py); RCI lives in `impact_scores`, not on the event; the event timestamp is `ingested_at`. |
| P3 | Filtering events on `status == "ACTIVE"`. | Status vocab is **lowercase**: `active` / `closed` / `resolved` ([backend/src/grid_unlocked/ingestion/vocab.py](backend/src/grid_unlocked/ingestion/vocab.py)). `"ACTIVE"` matches zero rows. |
| P4 | Treating ICT as minutes. | All ICT fields are **hours** (`ict_p50_h`). Convert at the UI edge only. |
| P5 | Building a new WebSocket / `ConnectionManager`. | The real-time spine exists: `event_bus` (ingest fan-in) + `dashboard_bus` → `/ws/dashboard` (fan-out) with `DashboardDelta`. Extend it; don't duplicate it. |

---

# SECTION 1 — What Works: Do Not Rebuild

These components are complete, tested, and **genuinely data-driven**. Treat them as the stable foundation. Do not rewrite them; only the explicit tasks in Section 2 touch them.

## 1.1 Backend — feature-complete (M01–M18)

Every module is a self-contained package (`router.py` / `service.py` / `repository.py` / `schemas.py`) under [backend/src/grid_unlocked/](backend/src/grid_unlocked/), registered in [backend/src/grid_unlocked/main.py](backend/src/grid_unlocked/main.py). The HTTP surface already exists:

| Domain (module) | Key endpoints (already live) |
|---|---|
| Ingestion · M01 | `POST /ingest/{astram,planned,field,citizen}`, `GET /events/{event_id}`, `GET /health/ingest` |
| Features · M02 | `GET /features/{event_id}`, `/priors/corridor-cause/...`, `/graph/centrality/...` |
| Impact · M03 | `POST /impact/score`, `GET /impact/explain/{event_id}`, `GET /models/versions` |
| Propagation · M04 | `POST /propagation/ripple`, `GET /propagation/active`, `/config` |
| Hotspots · M05 | `GET /hotspots/{observed,predicted,density,anomalies}`, `GET /hotspots/cell/{h3_res7}` |
| Planned · M06 | `POST /planned/package`, `GET /planned/upcoming`, `GET /templates/{cause}` |
| Dispatch · M07 | `POST /dispatch/recommend`, `GET /dispatch/status/...`, `GET /dispatch/roster` |
| Diversions · M08 | `GET /diversions/scenarios/{event_id}`, `/atlas`, `/atlas/{junction_id}`, `POST /compute`, `/validate` |
| Recommendations · M09 | `GET /recommendations/queue`, `GET /recommendations/{event_id}`, `POST /{event_id}/refresh`, `POST /{card_id}/approve`, `POST /{card_id}/reject` |
| Execution · M10 | `POST /execute/dispatch`, `GET /execute/status/...`, `GET /execute/audit` |
| VMS · M11 | `POST /vms/push`, `GET /vms/status/...`, `POST /vms/retry/...` |
| Transit · M12 | `GET /transit/impact/{event_id}`, `GET /transit/routes/affected` |
| Learning · M13 | `POST /learning/retrain`, `GET /learning/{jobs/latest,buffer/manifest/...,eval/...}`, `POST /learning/promote/...` |
| Governance · M14 | `GET /governance/{tier,health,transitions}`, `POST /governance/{override-tier,shadow-mode,promotion/approve,drills/cascade}` |
| Dashboard · M15 | `WS /ws/dashboard` (fan-out of `DashboardDelta`) |
| Field · M16 | `GET /field/packet/{recommendation_id}`, `POST /field/ack/...`, `POST /field/close/{event_id}`, `GET /field/tier` |
| Citizen · M17 | `POST /citizen/report`, `GET /citizen/report/{id}`, `POST /citizen/{verify,reject}/...`, `POST /citizen/subscribe` |

> **Action card is real, not a mock.** `GET /recommendations/{event_id}` builds a full `ActionCard` (impact, propagation, hotspot context, diversions, dispatch, planned, governance, evidence) via [recommendations/service.py](backend/src/grid_unlocked/recommendations/service.py). Approve/reject are keyed by **`card_id`** (`CARD-…`), not `event_id`.

## 1.2 ML models & data — do not retrain

- LightGBM + isotonic calibrator (closure), Cox PH (ICT, output in **hours**), DBSCAN + Poisson GLM (hotspots). Artifacts under `backend/models/`. Loaded by `impact.registry` at startup.
- Real ASTraM corpus (~8,170 incidents) drives priors, anchor buffer, and the density heatmap. `GET /hotspots/density` returns full-history per-H3-cell counts — this is the genuine, broad heatmap field the live map renders.
- M13 retrain is **synchronous, on-demand, tier-gated** (503 in Tier 3); the replay buffer is **derived live** from `normalized_events WHERE status='closed'` — there is no buffer table to append to. Closure feedback already flows through `POST /field/close/{event_id}`.

## 1.3 Database & vocab — the names you must use

Models: [backend/src/grid_unlocked/db/models.py](backend/src/grid_unlocked/db/models.py). DI: `get_session` from [db/session.py](backend/src/grid_unlocked/db/session.py).

- `NormalizedEventRow` (`normalized_events`) — **PK `event_id`**; has real `latitude`, `longitude`, `corridor`, `junction`, `event_type`, `event_cause`, `status`, `priority`, `is_planned`, `requires_road_closure`, `start_datetime`, `closed_datetime`, `ingested_at`. **No `rci_score`, no `created_at`.**
- `ImpactScoreRow` (`impact_scores`) — `event_id`, `p_closure`, `ict_p20_h/p50_h/p80_h` (**hours**), `rci`, `severity_band`.
- `DispatchRecommendationRow` — PK `recommendation_id`; assignments/station live **inside `recommendation_json`** (no `event_id` column).
- `CorridorCentroidRow` (`corridor_centroids`) — real mean lat/lon per corridor (M17, seeded from the ASTraM CSV). Read via `CitizenRepository.get_all_centroids()`. **This is the genuine source for corridor geometry** ([Feature 3](#feature-3--diversion-route-overlay-on-the-map) & [4](#feature-4--de-hardcode-planned-event-coordinates)).
- Vocab ([ingestion/vocab.py](backend/src/grid_unlocked/ingestion/vocab.py)): status `{active,closed,resolved}`; event_type `{planned,unplanned}`; 17 snake_case causes (`accident`, `vip_movement`, `public_event`, `procession`, `construction`, `vehicle_breakdown`, …); 22 named corridors; bbox lat `[12.8,13.3]` lon `[77.3,77.8]`.

## 1.4 Real-time spine — already wired

- Ingest fan-in: [ingestion/bus.py](backend/src/grid_unlocked/ingestion/bus.py) `event_bus.subscribe_normalized(handler)`. Impact/propagation/hotspot scoring happen in **subscribers**, not inline in the ingest handler.
- Dashboard fan-out: [dashboard/bus.py](backend/src/grid_unlocked/dashboard/bus.py) `dashboard_bus.publish(DashboardDelta(...))` → [dashboard/router.py](backend/src/grid_unlocked/dashboard/router.py) `WS /ws/dashboard`.
- `DashboardDelta` = `{type:"dashboard.delta", scope, event_id, payload, emitted_at}`. Scopes today: `card | tier | hotspot | citizen | field` ([dashboard/schemas.py](backend/src/grid_unlocked/dashboard/schemas.py)). Publishers already emit `card` (on card-complete/approve/reject), `hotspot` (on ingest), `tier`, `field`, `citizen`.

## 1.5 Frontend — already built (NOT "route shells")

Structure is `frontend/app/**` (App Router, **no `src/`**), `frontend/components/**`, `frontend/lib/**`, `frontend/context/**`.

| Page | File | Status |
|---|---|---|
| Landing | [frontend/app/page.tsx](frontend/app/page.tsx) | Built (aurora hero) |
| Login | [frontend/app/login/page.tsx](frontend/app/login/page.tsx) | Built (auth context, role-based `can()`) |
| **Live Monitor** | [frontend/app/live/page.tsx](frontend/app/live/page.tsx) | Built — 3-column: alert queue · Mappls map · action card; WS-driven |
| **Planned** | [frontend/app/planned/page.tsx](frontend/app/planned/page.tsx) | Built — wizard: ingest → `generatePackage` → impact/analogues/diversions |
| Governance | [frontend/app/governance/page.tsx](frontend/app/governance/page.tsx) | Built — tier, health, transitions, drills, learning eval, promotion |
| Analytics | [frontend/app/analytics/page.tsx](frontend/app/analytics/page.tsx) | Built — hotspot density/predicted/anomalies + methodology charts |
| Field | [frontend/app/field/[recommendationId]/page.tsx](frontend/app/field/) | Built — packet, ack, closure form (offline queue) |
| Report (citizen) | [frontend/app/report/page.tsx](frontend/app/report/) | Built — geolocated report, status, subscriptions |

Shared infrastructure (the contract layer):
- **API client** [frontend/lib/api.ts](frontend/lib/api.ts) — typed methods for queue/card/approve/reject, hotspots(observed/density/predicted/anomalies/cell), diversions, governance, learning, planned, field, citizen, propagation. Base URL `NEXT_PUBLIC_API_URL`.
- **WebSocket hook** [frontend/lib/ws.ts](frontend/lib/ws.ts) — `useDashboardSocket()` returns `{lastDelta, connected}`, auto-reconnect with backoff; parses `DashboardDelta`.
- **Types** [frontend/lib/types.ts](frontend/lib/types.ts) — mirror of backend schemas (`ActionCard`, `QueueItem`, `ScenarioResponse`, `DiversionRoute`, hotspot/propagation/field/citizen types, `DashboardDelta`).
- Auth [frontend/context/auth-context.tsx](frontend/context/auth-context.tsx) + [frontend/lib/auth.ts](frontend/lib/auth.ts); offline queues [frontend/lib/field-offline-queue.ts](frontend/lib/field-offline-queue.ts), [frontend/lib/citizen-storage.ts](frontend/lib/citizen-storage.ts); Mappls typings [frontend/lib/mappls.d.ts](frontend/lib/mappls.d.ts).
- Tests: Vitest unit (`frontend/tests/unit/*`) + Playwright e2e (`frontend/tests/e2e/*`).

## 1.6 The live map is genuinely data-driven

[frontend/app/live/_components/map-panel.tsx](frontend/app/live/_components/map-panel.tsx) loads the **Mappls Web SDK** and renders:
- a **heatmap** from `GET /hotspots/density` (real ~150-day per-cell counts; density simulated by proportional point-repeat because the SDK hardcodes per-point weight — documented in-file);
- **click-to-histogram** popups from `GET /hotspots/cell/{h3}` (real hourly distribution);
- **observed** clusters (M05 live) + **predicted** corridor lift (M05 Poisson, `GET /hotspots/predicted`);
- a **selected-event marker** placed from `ActionCard.hotspot_context.h3_res7` via `h3.cellToLatLng`.

This already beats the original guide's MapLibre + **hardcoded gutter-points** plan. **Do not** reintroduce a hardcoded bottleneck list — real hotspots already cover it.

## 1.7 ✗ Do-Not List (applies to all streams)

- ✗ Don't rebuild the map, action card, alert queue, planned wizard, field packet, citizen flow, governance console — they exist and work.
- ✗ Don't add a hardcoded gutter-points / bottleneck list (use M05 hotspots).
- ✗ Don't create `ws/manager.py`, a second WebSocket, or a `ReplayBufferEntry` table.
- ✗ Don't add `osmnx`/`geojson`/`maplibre` to satisfy the old guide — `httpx` and Mappls are already in place; the real new endpoints need none of them.
- ✗ Don't fabricate coordinates. Incidents have real lat/lng; corridor geometry comes from `corridor_centroids`.

---

# SECTION 2 — New Features to Add

The product is already a strong command center. These features **close the operational loop** and **add map intelligence** — turning a great dashboard into a live decision system. Every one is backed by real data; none are cosmetic.

### Feature 1 — Live incident pins (real coordinates + RCI colour)
Today the map shows the *density field* and the *selected* event, but not **every active incident** as its own pin. `NormalizedEventRow` already stores real `latitude`/`longitude`, so this needs **zero fabrication** — only exposure. Plot active events as RCI-coloured circles (red >0.7, orange 0.4–0.7, yellow 0.2–0.4, green <0.2); click a pin → select that event (loads its action card). *Genuine source:* new `GET /api/v1/incidents/active` (Stream A) = `normalized_events (status='active')` ⨝ latest `impact_scores`.

### Feature 2 — Real-time incident broadcast (sub-second)
A freshly ingested event currently only surfaces when the 15 s queue poll catches it, or indirectly via the `hotspot` delta. Add a first-class **`incident` scope** to `DashboardDelta`, emitted from an ingest subscriber, so a new pin (and, for high-RCI events, an auto-previewed card) appears in **< 1 s**. *Genuine source:* the real `event_bus` + `dashboard_bus` spine; payload carries the event's real fields.

### Feature 3 — Diversion route overlay on the map
The action card lists M08 routes as **text only** ("Routes" tab). Draw them on the map. ⚠️ Honesty constraint: `DiversionRoute.path` is a list of **corridor-proxy node IDs**, not GPS coordinates ([diversions/graph.py](backend/src/grid_unlocked/diversions/graph.py) is a static OSM *proxy*). So resolve each node → its **real corridor centroid** (`corridor_centroids`) to get ordered waypoints, then either (a) draw a labelled corridor-level polyline, or (b) call the **Mappls Directions API** through the already-loaded SDK to render the drivable road geometry between those waypoints. Both are honest; (b) looks best. **Never invent node coordinates.** *Genuine source:* `GET /diversions/scenarios/{event_id}` (real) + `corridor_centroids` (real) [+ Mappls routing].

### Feature 4 — De-hardcode planned-event coordinates
[frontend/app/planned/page.tsx](frontend/app/planned/page.tsx) has a `CORRIDOR_CENTROIDS` constant (≈8 corridors) used to supply lat/lng when ingesting a planned event — the **one** hardcoded-data smell in the repo. Replace it with the real `corridor_centroids` via a new `GET /api/v1/corridors` endpoint, and/or let the operator drop a pin on a mini Mappls map. *Genuine source:* M17 `corridor_centroids` (mean lat/lon per corridor from the ASTraM CSV).

### Feature 5 — Commander "Close & Learn" on the live action card
The field app can close events (`POST /field/close/{event_id}` → re-ingests as `closed` → feeds the M13 replay buffer), but the **commander's** live action card has no closure affordance, so the learning loop isn't visible in the command center. Add a "Close & Learn" action on approved/active cards that calls the **existing** close endpoint and shows the resulting buffer/learning signal. *Genuine source:* existing M16 close → M13 buffer (no new ML, no fakes).

### Feature 6 *(bonus)* — Cascade propagation overlay
`GET /propagation/active` (M04 GCDH) returns ripple nodes with risk/hop. Visualise the selected event's cascade as graded nodes/edges on the map (resolve corridor-proxy nodes → centroids, same as Feature 3). *Genuine source:* real M04 output.

### Feature 7 *(bonus)* — Transit impact tab (M12)
`GET /transit/impact/{event_id}` returns a real Transit Impact Index (affected BMTC routes). Add a "Transit" tab to the action card. *Genuine source:* real M12 endpoint, currently unused by the UI.

---

# STREAM DIVISION — three concurrent builders

**Owner split (no file collisions):**
- **Stream A** owns Python only — `backend/src/grid_unlocked/**` + `backend/scripts/**` + `backend/tests/**`.
- **Stream B** owns the live map & real-time — `frontend/app/live/**`, and *additive* edits to `frontend/lib/ws.ts` / `frontend/lib/types.ts`.
- **Stream C** owns workflows & loop — `frontend/app/planned/**`, `frontend/app/report/**`, `frontend/app/field/**`, the action-card close affordance, and *additive* edits to `frontend/lib/api.ts` / `frontend/lib/types.ts`.

**The only coupling is the contract surface in [§6.1](#61--shared-contract-surface-freeze-this-first).** B and C build against those typed contracts immediately (stub the fetch with the frozen shape if A hasn't merged yet). `lib/types.ts` edits are additive-only; coordinate ownership of that file via the contract table to avoid merge conflicts.

---

## STREAM A — Backend / Data APIs (Python)

**Pre-reqs:** Python 3.12, `uv`, Docker (postgres + redis), API at `localhost:8000`. **No new dependencies needed.**

### A-0 · Ground rules (read once)
**Do:** use `get_session`; reference `…Row` models; filter `status == "active"`; join `impact_scores` for RCI; keep ICT in hours server-side; place new read endpoints in a new module `grid_unlocked.maps` (`router.py`, prefix `/api/v1`) registered in [main.py](backend/src/grid_unlocked/main.py); follow the test pattern in [backend/tests/test_dashboard.py](backend/tests/test_dashboard.py).
**Don't:** invent `get_db`/`rci_score`/`created_at`; add a hardcoded bottleneck list; touch frontend files.

### A-1 · `GET /api/v1/incidents/active` — pins with real geometry (Feature 1)
- **File:** `backend/src/grid_unlocked/maps/router.py` *(new)*; register in `main.py`.
- Query `NormalizedEventRow` where `status == "active"`, order by `ingested_at desc`, `limit` (default 100, ≤500). LEFT-JOIN the latest `ImpactScoreRow` per `event_id` (subquery on max `scored_at`) for `rci`/`p_closure`/`severity_band`; default `rci=null` when unscored (UI greys it).
- **Response (freeze):** `{ "incidents": [{ event_id, corridor, junction, event_type, event_cause, lat, lng, rci, p_closure, severity_band, status, ingested_at }] }`.
- **Do/Don't:** Do reuse the real coords on the row. Don't read RCI off the event (it isn't there); don't filter `"ACTIVE"`.
- **Accept:** seeded active events return with coords; unscored events return `rci:null` (no 500).

### A-2 · Incident broadcast on ingest (Feature 2)
- **Files:** add `INCIDENT = "incident"` to `DeltaScope` in [dashboard/schemas.py](backend/src/grid_unlocked/dashboard/schemas.py); create `backend/src/grid_unlocked/dashboard/incident_subscriber.py` mirroring [hotspots/subscriber.py](backend/src/grid_unlocked/hotspots/subscriber.py); register it in `main.py` `lifespan()`.
- On `event_bus.subscribe_normalized`, publish `DashboardDelta(scope=INCIDENT, event_id, payload={corridor, junction, event_type, cause, lat, lng, status}, emitted_at=now)`. Wrap in try/except + log so a fan-out failure never breaks ingest.
- **Do/Don't:** Do keep the payload lightweight (RCI is scored async; the client refetches the card/queue). Don't compute impact inline; don't create a new socket.
- **Accept:** a client on `/ws/dashboard` receives a `scope:"incident"` delta < 1 s after `POST /ingest/astram`; existing [test_dashboard.py](backend/tests/test_dashboard.py) still green.

### A-3 · Diversion route geometry resolver (Feature 3)
- **Files:** extend [diversions/service.py](backend/src/grid_unlocked/diversions/service.py) `scenarios()` (or add `maps/router.py` `GET /api/v1/diversions/{event_id}/geometry`).
- Build a corridor→centroid map from `CitizenRepository.get_all_centroids()` (real `corridor_centroids`). For each `DiversionRoute`, map `path` node IDs → corridor (`parse_node_id`) → centroid, producing `waypoints: [{lat,lng,corridor}]`. Add `waypoints` alongside the existing `path` (don't replace it).
- **Response addition (freeze):** each route gains `"waypoints": [{lat, lng, corridor}]` (empty when a corridor has no centroid).
- **Do/Don't:** Do label these as corridor-level waypoints. **Don't** fabricate coordinates for nodes with no centroid — omit them and let the client decide (straight polyline vs Mappls routing).
- **Accept:** `/diversions/scenarios/{event_id}` returns routes with ≥2 resolved waypoints for corridor-mapped paths.

### A-4 · `GET /api/v1/corridors` — real centroids (Feature 4)
- **File:** `maps/router.py`. Return `{ "corridors": [{ name, lat, lon, sample_count }] }` straight from `CitizenRepository.get_all_centroids()` / `CorridorCentroidRow`.
- **Accept:** returns the seeded corridor centroids; matches `VALID_CORRIDORS` names.

### A-5 *(bonus)* · Propagation node coordinates (Feature 6)
- Add resolved `lat/lng` (via centroids) to `GET /propagation/active` nodes, same resolver as A-3. Additive field; omit when unresolved.

### A-6 · Demo seed script
- **File:** `backend/scripts/seed_demo.py` *(new)*. `httpx`-POST ~20 events to `/ingest/astram` across `Mysore Road` / `Bellary Road 1` / `Tumkur Road`, in-bbox coords, **canonical causes only** (`accident`, `vip_movement`, `public_event`, `procession`, `construction`, `vehicle_breakdown`), `event_type` planned/unplanned, varied priority, `start_datetime` within the last ~2 h.
- **Do/Don't:** Do use canonical vocab (`"Road Work"`/`"Breakdown"` → 422). **Don't** call `REFRESH MATERIALIZED VIEW active_events` — no such view exists here.
- **Accept:** `uv run python scripts/seed_demo.py` → 20×200, zero 422; afterwards `/api/v1/incidents/active` is populated.

### A-7 · Tests
- Add `backend/tests/test_maps.py` (incidents/active shape + RCI join + status filter; corridors), `backend/tests/test_incident_broadcast.py` (WS `incident` delta on ingest), and extend a diversions test for `waypoints`. Mirror [conftest.py](backend/tests/conftest.py) (in-memory SQLite, register subscribers, `registry.load()`, canonical payloads). Gate: `uv run pytest -q` fully green.

---

## STREAM B — Live Map & Real-Time (Frontend)

**Pre-reqs:** Node 20+, pnpm. `NEXT_PUBLIC_MAPPLS_KEY` + `NEXT_PUBLIC_API_URL` + `NEXT_PUBLIC_WS_URL` in `frontend/.env.local`.

### B-0 · Read before coding (mandatory)
Read [frontend/AGENTS.md](frontend/AGENTS.md) and the relevant guide under `frontend/node_modules/next/dist/docs/`. Study [map-panel.tsx](frontend/app/live/_components/map-panel.tsx) — it documents the **Mappls SDK quirks** you must respect:
- `new window.mappls.Map(CONTAINER_ID_STRING, …)` — pass the **id string**, not the element.
- `HeatmapLayer({...})` / geojson helpers are called as **plain functions**, not `new` (they read `this`).
- No `flyTo`/per-point weight/layer-hide API — patterns for those already exist in-file; reuse them.

### B-1 · Live incident pin layer (Feature 1)
- **File:** `frontend/app/live/_components/incident-layer.tsx` *(new)*, mounted by [map-panel.tsx](frontend/app/live/_components/map-panel.tsx).
- Fetch `api.incidentsActive()` (add to `lib/api.ts` — coordinate with Stream C, [§6.1](#61--shared-contract-surface-freeze-this-first)); render one `window.mappls.Marker` per incident, colour by RCI; click → call the page's `onSelect(eventId)` so the existing card panel loads.
- **Do/Don't:** Do reuse the marker-churn/visibility patterns already in `map-panel.tsx`. Don't recreate markers every render — diff by `event_id`.
- **Accept:** active incidents appear as coloured pins; clicking one selects it and opens its real action card.

### B-2 · Wire the `incident` delta (Feature 2)
- **Files:** [frontend/lib/types.ts](frontend/lib/types.ts) — add `"incident"` to `DeltaScope` (additive); [frontend/app/live/page.tsx](frontend/app/live/page.tsx) — on `lastDelta.scope === "incident"`, optimistically add/refresh the pin and (if high RCI) auto-select to preview the card; keep the existing `card`/`hotspot` handling.
- **Accept:** posting an ingest makes a pin appear in < 1 s without waiting for the 15 s poll.

### B-3 · Diversion route overlay (Feature 3)
- **File:** `frontend/app/live/_components/diversion-overlay.tsx` *(new)*, driven by the selected `ActionCard.diversions` + A-3 `waypoints`.
- Draw the top routes as polylines (rank-ordered colours). Prefer **Mappls Directions** between waypoints for drivable geometry; fall back to a straight corridor-level polyline. Cross-highlight with the card's "Routes" tab on hover/select.
- **Do/Don't:** Do gate on `waypoints.length >= 2`. Don't draw anything when waypoints are unresolved (show the existing text list only) — never synthesize a path.
- **Accept:** selecting a card with diversions draws real route lines; clearing selection removes them.

### B-4 *(bonus)* · Cascade overlay (Feature 6) — graded nodes/edges from `/propagation/active` + A-5 coords.

### B-5 · Types & tests
- Keep `lib/types.ts` additions additive. Add a Vitest test for the incident-delta reducer; extend the Playwright dashboard spec to assert a pin appears after a simulated delta.

---

## STREAM C — Workflows & Closed-Loop (Frontend)

**Pre-reqs:** same as Stream B.

### C-1 · De-hardcode planned coordinates (Feature 4)
- **File:** [frontend/app/planned/page.tsx](frontend/app/planned/page.tsx). Replace the `CORRIDOR_CENTROIDS` constant + `corridorCoords()` with data from `api.corridors()` (A-4). Optionally add a small Mappls pin-picker so an off-corridor event gets exact coords.
- **Do/Don't:** Do fall back to city-centre only if the corridor is unknown *and* no pin is dropped. Don't keep the static lookup as the primary source.
- **Accept:** ingesting a planned event uses a real centroid or a user-picked point; the constant is gone.

### C-2 · Commander "Close & Learn" (Feature 5)
- **Files:** [frontend/app/live/_components/action-card-panel.tsx](frontend/app/live/_components/action-card-panel.tsx) — add a "Close & Learn" action on approved/active cards calling `api.fieldClose(eventId, {...})` (already in [lib/api.ts](frontend/lib/api.ts)); reuse the closure-form fields from [field/.../closure-form.tsx](frontend/app/field/) and the offline queue.
- **Do/Don't:** Do surface the resulting learning signal (e.g. refresh `api.latestLearningJob()` / buffer count). Don't write a parallel close endpoint — M16 close already feeds M13.
- **Accept:** closing from the live card flips event status and the closure feeds the replay buffer (verify via `/learning/jobs/latest` after a retrain).

### C-3 · Citizen → verify → live loop
- Ensure `POST /citizen/verify/{report_id}` (returns an `ActionCard`) produces an event that appears live via Stream B's incident delta. Polish the report→status→appears-on-map narrative; surface verified reports.

### C-4 *(bonus)* · Transit tab (Feature 7) — add `api.transitImpact(eventId)` + a "Transit" tab in the action card from `GET /transit/impact/{event_id}`.

### C-5 · API/types & tests
- `lib/api.ts` additions (`corridors`, `incidentsActive`, `transitImpact`) — coordinate ownership per [§6.1](#61--shared-contract-surface-freeze-this-first). Extend Vitest/Playwright for the close-and-learn flow.

---

# SECTION 6 — Integration, Contracts & Demo

## 6.1 · Shared contract surface (freeze this first)

Add these to [frontend/lib/types.ts](frontend/lib/types.ts) and [frontend/lib/api.ts](frontend/lib/api.ts) **once**, before parallel work. Suggested owner in brackets; the others import.

```ts
// types.ts (additive) — [A defines shapes, C lands api methods, B lands ws scope]
export type DeltaScope = "card" | "tier" | "hotspot" | "citizen" | "field" | "incident"; // +incident [B]
export interface ActiveIncident {            // [A-1]
  event_id: string; corridor: string | null; junction: string | null;
  event_type: string; event_cause: string; lat: number; lng: number;
  rci: number | null; p_closure: number | null; severity_band: SeverityBand | null;
  status: string; ingested_at: string;
}
export interface ActiveIncidentsResponse { incidents: ActiveIncident[]; }
export interface RouteWaypoint { lat: number; lng: number; corridor: string | null; } // [A-3]
// DiversionRoute gains: waypoints: RouteWaypoint[];
export interface CorridorCentroid { name: string; lat: number; lon: number; sample_count: number; } // [A-4]
export interface CorridorsResponse { corridors: CorridorCentroid[]; }
```

```ts
// api.ts (additive) — [owner: C]
incidentsActive: (limit = 100) => request<ActiveIncidentsResponse>(`/api/v1/incidents/active?limit=${limit}`),
corridors:       ()           => request<CorridorsResponse>(`/api/v1/corridors`),
transitImpact:   (id: string) => request<unknown>(`/transit/impact/${id}`),
```

## 6.2 · Cross-stream dependencies (build concurrently)

| Consumer | Needs | Build-now strategy |
|---|---|---|
| B-1 pins | A-1 `/api/v1/incidents/active` | B stubs `incidentsActive()` with the frozen shape until A merges |
| B-2 delta | A-2 `incident` scope | B adds the scope to types immediately; reducer is testable with a mock delta |
| B-3 overlay | A-3 `waypoints` | B renders the text list until `waypoints` arrive; gate on `>=2` |
| C-1 planned | A-4 `/api/v1/corridors` | C keeps the constant behind a feature flag, swaps to `api.corridors()` on merge |
| C-2 close | existing `/field/close` | no A dependency — ship immediately |

## 6.3 · End-to-end test sequence (real data)
1. `docker compose up --build`; `cd backend && uv run python scripts/seed_demo.py` → 20×200.
2. `GET /api/v1/incidents/active` → incidents with coords + (mostly) RCI.
3. `GET /api/v1/corridors` → real centroids.
4. Open `/live`: heatmap + pins render; connect WS; `POST /ingest/astram` → a pin appears < 1 s (Feature 2).
5. Select a high-RCI event → real action card; "Routes" tab + map overlay agree (Feature 3).
6. Approve (when not shadow/Tier-3) → 200; **Close & Learn** → event closes; `/learning/jobs/latest` reflects the buffer after a retrain (Feature 5).
7. `/planned`: add an event → uses a real centroid / picked point (Feature 4); package shows real analogues + impact.
8. `pnpm test:unit && pnpm test:e2e` and `uv run pytest -q` green.

## 6.4 · Demo script (8 min, real product)
0:00 `/live` — explain heatmap = 8,170 real ASTraM incidents (density), pins = live active events, colour = RCI. · 1:30 `POST` an ingest → pin + card appear in real time (closure from LightGBM, ICT from Cox PH, dispatch from MILP). · 3:00 Open the diversion overlay — real M08 corridor routes drawn via Mappls. · 4:00 Approve → Close & Learn → "every commander decision feeds the M13 replay buffer." · 5:00 `/planned` — Dasara on Mysore Road: real analogues + 36% historical closure rate. · 6:00 `/governance` — 3-tier degradation, shadow mode, human-in-the-loop. · 7:00 `/report` → verify → appears live. · 7:30 Close: real ML, real ASTraM data, real Bengaluru topology, real WS feed, real approval loop — an intelligence layer on ASTraM, not a dashboard.

## 6.5 · Environment variables
`NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_WS_URL` (use `wss://` in prod), `NEXT_PUBLIC_MAPPLS_KEY` (domain-whitelisted — `localhost` is rejected; alias a host for local dev). Backend: `GRID_DATABASE_URL`, `GRID_REDIS_URL`, `GRID_CORS_ALLOW_ORIGINS`.

## 6.6 · Known gotchas
- **Next 16 / React 19 / Tailwind 4** — read `frontend/node_modules/next/dist/docs/` (P1).
- **Mappls SDK** — id-string container, plain-function layer helpers, no flyTo/per-point weight (see [map-panel.tsx](frontend/app/live/_components/map-panel.tsx)).
- **Status lowercase**, **ICT in hours**, **no `active_events` matview**, **no `osmnx` needed**.
- Diversion/propagation nodes are corridor proxies — geometry only via `corridor_centroids` (never fabricate).

---

# APPENDIX A — File creation / modification summary

| Stream | File | Action |
|---|---|---|
| A | `backend/src/grid_unlocked/maps/{__init__,router}.py` | CREATE — `/api/v1/incidents/active`, `/api/v1/corridors` |
| A | `backend/src/grid_unlocked/dashboard/schemas.py` | MODIFY — add `DeltaScope.INCIDENT` |
| A | `backend/src/grid_unlocked/dashboard/incident_subscriber.py` | CREATE — ingest→incident delta |
| A | `backend/src/grid_unlocked/main.py` | MODIFY — register maps router + incident subscriber |
| A | `backend/src/grid_unlocked/diversions/service.py` | MODIFY — add `waypoints` via corridor centroids |
| A | `backend/src/grid_unlocked/propagation/*` | MODIFY *(bonus)* — node coords |
| A | `backend/scripts/seed_demo.py` | CREATE — canonical-vocab seed |
| A | `backend/tests/test_maps.py`, `test_incident_broadcast.py` | CREATE |
| B | `frontend/app/live/_components/incident-layer.tsx` | CREATE — RCI pins |
| B | `frontend/app/live/_components/diversion-overlay.tsx` | CREATE — route polylines |
| B | `frontend/app/live/page.tsx`, `_components/map-panel.tsx` | MODIFY — mount layers, wire `incident` delta |
| B | `frontend/lib/types.ts` | MODIFY — `+incident` scope (additive) |
| C | `frontend/app/planned/page.tsx` | MODIFY — use `api.corridors()` / pin-picker |
| C | `frontend/app/live/_components/action-card-panel.tsx` | MODIFY — Close & Learn |
| C | `frontend/lib/api.ts` | MODIFY — `incidentsActive`, `corridors`, `transitImpact` |

# APPENDIX B — Reality vs the original `.docx`

| Original guide assumed | Reality | Consequence |
|---|---|---|
| Flat `routers/*.py`, `NormalizedEvent`, `get_db` | Domain modules, `…Row`, `get_session` | Old snippets don't compile |
| Build WebSocket + `ConnectionManager` (A-1/A-2) | `dashboard_bus` + `/ws/dashboard` exist (M15) | Skip; add only the `incident` scope |
| "Replace mock action card" (A-7) | Real M09 `ActionCard` already served | Don't touch; it's richer |
| `ReplayBufferEntry` table + every-50 retrain (A-6) | Buffer derived from `status='closed'`; close via `/field/close` | Reuse the real loop |
| Add `osmnx`/`geojson`/`websockets`/`maplibre` (A-0/B-0) | `httpx` present; Mappls + maplibre already installed; real endpoints need none | Add nothing heavy |
| Hardcoded 8 "gutter points" (A-5/Feature 6) | Real M05 hotspots (`/hotspots/*`) already on the map | Don't add hardcoded data |
| `status == "ACTIVE"`, ICT minutes | lowercase `active`, ICT hours | Filters/units fixed |
| MapLibre + "route shells" | Mappls SDK + fully-built pages, lib, auth, tests | This is a **refactor/extend**, not a build-from-stubs |

---
*Built for Gridlock 2.0. Every figure on screen is real ASTraM data or a real model output — keep it that way.*
