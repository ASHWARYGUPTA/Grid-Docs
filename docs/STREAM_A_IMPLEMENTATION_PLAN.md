# Stream A (Backend) — Implementation Plan

**Source:** `docs/Grid_Unlocked_Implementation_Guide.docx` → *Stream A: Backend Python Developer* (tasks **A‑0 … A‑8**).
**Scope of this plan:** Section A (backend) **only**. No frontend (Stream B), no integration UI (Stream C).
**Author of plan:** reconciliation of the hackathon guide against the *actual* codebase as it stands on `master`.
**Status:** PLAN ONLY — no code has been written yet.

---

## 0. Read this first — the guide's code is illustrative, not literal

The guide was written against a **simplified, hypothetical** backend (flat `routers/*.py`, models named `NormalizedEvent`, a `get_db` dependency, a `ConnectionManager`, a `ReplayBufferEntry` table, etc.).

**The real backend is a mature, domain‑modular FastAPI app** (`ingestion/`, `dashboard/`, `recommendations/`, `learning/`, `field/`, … each with `router.py` / `service.py` / `repository.py` / `schemas.py`). It already implements M01–M18.

Copy‑pasting the guide's snippets verbatim **will not compile and will silently match zero rows.** Every task below has been re‑mapped onto the real code. The single biggest win of this plan: **3 of the 9 tasks are already done** (A‑1, A‑2 route, A‑7) and **A‑0 / A‑6 are partly wrong** — so we avoid building duplicates and avoid a needless heavy `osmnx` install.

### Verdict at a glance

| Guide task | Verdict | What we actually do |
|---|---|---|
| **A‑0** Add deps (osmnx, websockets, httpx, geojson) | ⚠️ Mostly unnecessary | `httpx` already present; `osmnx`/`geojson` not used by the real A‑3/A‑5 code; WS already works via `uvicorn[standard]`. **Add nothing heavy.** |
| **A‑1** `ws/manager.py` ConnectionManager | ❌ Skip (duplicate) | `DashboardBus` (M15) already exists in `dashboard/bus.py`. Do **not** create a second fanout. |
| **A‑2** `/ws/dashboard` route | ✅ Route already exists | Real new work = **broadcast an "incident" delta on ingest** via an event‑bus subscriber. |
| **A‑3** Heatmap endpoint | 🟩 Real, build it | New `GET /api/v1/heatmap`; fix column/units bugs from the guide. |
| **A‑4** Recent‑events endpoint | 🟩 Real, build it | New `GET /api/v1/events/recent`; fix `status`/`created_at`/`rci` bugs. |
| **A‑5** Gutter‑points endpoint | 🟩 Real, build it | New `GET /api/v1/gutter-points`; hardcoded list + haversine (no osmnx); fix `status`. |
| **A‑6** Learning‑close endpoint | ⚠️ Re‑design | No `ReplayBufferEntry` table exists. Close = re‑ingest as `closed` (feeds M13 buffer). Reuse the existing close path. |
| **A‑7** Replace "mock" action card | ❌ Already done (richer) | `GET /recommendations/{event_id}` returns a full real `ActionCard`. Optional: a thin flattened **adapter** endpoint for the guide's exact shape. |
| **A‑8** Demo seed script | 🟩 Real, build it | New `scripts/seed_demo.py`; fix invalid causes + drop the non‑existent matview refresh. |

---

## 1. Ground truth — facts every task depends on

Verified by reading the source. Use these names exactly.

### 1.1 Database session & models
- **DB dependency:** `from grid_unlocked.db.session import get_session` → `session: AsyncSession = Depends(get_session)`. There is **no `get_db`**.
- **Models live in `grid_unlocked.db.models`** and are suffixed `Row`:
  - `NormalizedEventRow` (table `normalized_events`)
    - **PK is `event_id: str`** (not `id`).
    - Has: `latitude`, `longitude`, `corridor`, `junction`, `event_type`, `event_cause`, `status`, `priority`, `description`, `is_planned`, `requires_road_closure`, `start_datetime`, `end_datetime`, `closed_datetime`, `created_date`, `ingested_at`, `updated_at`, `authenticated`, `source`, `zone`, `police_station`, `veh_type`, `anomaly_flags`.
    - **Does NOT have `rci_score`** (RCI lives in `impact_scores`).
    - **Does NOT have `created_at`** (the timestamp is `ingested_at`).
  - `ImpactScoreRow` (table `impact_scores`): `event_id`, `p_closure`, `ict_p20_h`, `ict_p50_h`, `ict_p80_h` (**hours**, not minutes), `rci`, `severity_band`, `scored_at`, `closure_model_version`, `ict_model_version`.
  - `DispatchRecommendationRow` (table `dispatch_recommendations`): PK `recommendation_id`, `recommendation_json` (assignments/station/etc. are **inside this JSON blob**), `source`, `tier_at_decision`, `created_at`. **There is no `event_id` column and no `assigned_station`/`manpower_count`/`diversion_roads`/`provenance` columns.**
  - `ActionCardRow` (table `action_cards`): `card_id` (PK), `event_id`, `status`, `card_json`.
  - `FieldClosureRow`, `ReplayBufferManifestRow`, `ModelRegistryRow`, `LearningJobRow` exist; **`ReplayBufferEntry` does NOT exist.**

### 1.2 Controlled vocabularies (M01 normalizer)
- **Status** is lowercase: `VALID_STATUSES = {"active", "closed", "resolved"}`. `normalize_status(None) → "active"`. → **Filter on `"active"`, never `"ACTIVE"`.**
- **Event type** is lowercase: `{"planned", "unplanned"}`. Input is `.lower()`‑ed, so `"Planned"`/`"Unplanned"` are accepted.
- **Cause** is a 17‑class snake_case vocab. Valid examples: `accident`, `vip_movement`, `public_event`, `procession`, `construction`, `vehicle_breakdown`, `congestion`, `water_logging`, `tree_fall`, `debris`, `pot_holes`, `protest`, `road_conditions`, `fog_low_visibility`, `others`, `unknown_obstruction`. Free‑text is snake‑cased then checked. **`"Road Work"`→`road_work` and `"Breakdown"`→`breakdown` are INVALID → 422 reject.** Use `construction` / `vehicle_breakdown`.
- **Corridors** must match `VALID_CORRIDORS` exactly. `Mysore Road`, `Bellary Road 1`, `Tumkur Road` are valid (guide's seed corridors are fine).
- **bbox:** lat `[12.8, 13.3]`, lon `[77.3, 77.8]`. All guide seed coordinates fall inside.

### 1.3 Ingestion flow (no inline scoring)
`POST /ingest/{astram|planned|field|citizen}` → `IngestionService.ingest()` normalizes, upserts `NormalizedEventRow`, and **publishes to the in‑process event bus** (`grid_unlocked.ingestion.bus.event_bus`). Impact/propagation/hotspot scoring happens **asynchronously in subscribers**, *not* inline. So the ingest handler has **no `impact`/`dispatch`/`rec` objects** — the guide's A‑2 broadcast (which reads them) cannot work as written.

- Event bus API: `event_bus.subscribe_normalized(handler)` where `handler(msg: EventNormalizedMessage)` and `msg.event` is a `NormalizedEvent` pydantic model. Mirror `hotspots/subscriber.py`.
- Subscribers are wired in `main.py` `lifespan()` via `register_*_subscribers()`.

### 1.4 WebSocket fanout (M15) — already built
- Route: `@router.websocket("/ws/dashboard")` in `dashboard/router.py` (registered in `main.py`).
- Fanout: `dashboard_bus.publish(DashboardDelta(...))` from `dashboard/bus.py`.
- `DashboardDelta` (`dashboard/schemas.py`): `{ type: "dashboard.delta", scope: DeltaScope, event_id, payload: dict, emitted_at }`.
- `DeltaScope` today = `{card, tier, hotspot, citizen, field}` — **no `incident`/`event.ingest` scope yet.**
- Existing publishers: `recommendations/service.py` (CARD on card‑complete + approve/reject), `field/service.py` (FIELD), `governance/service.py` (TIER), `hotspots/subscriber.py` (HOTSPOT on ingest), `citizen/service.py` (CITIZEN).
- **Confirmed by `tests/test_dashboard.py`:** on ingest a `hotspot` delta fires; on approve a `card` delta fires. **Nothing currently announces "a new incident arrived" in card‑ready form.** That is the genuine A‑2 gap.

### 1.5 Recommendations / action card (M09) — already real
- `GET /recommendations/{event_id}` → builds & returns a full `ActionCard` (impact, propagation, hotspot context, diversions, dispatch section, planned section, governance, evidence). **This is the action card. There is no mock and no `routers/station.py`.**
- `POST /recommendations/{event_id}/refresh` → force rebuild.
- `POST /recommendations/{card_id}/approve` → **keyed by `card_id` (`CARD‑…`), not `event_id`/`rec_id`.** Body `{commander_id, override_codes}`.
- `POST /recommendations/{card_id}/reject`; `GET /recommendations/queue`.
- Dispatch/station data is reachable via `card.dispatch.assignments[*].station_id` and `card.dispatch.recommendation_id`, computed on demand inside `build_card`.

### 1.6 Learning (M13) — buffer is derived, retrain is on‑demand
- The replay buffer is **built live** from `NormalizedEventRow WHERE status == "closed" AND closed_datetime IS NOT NULL` within the window, unioned with a stratified CSV anchor sample (`learning/buffer.py`). **There is nothing to "append to."**
- Retrain: `POST /learning/retrain` → `LearningService.start_retrain(trigger)` is **synchronous (~3–5 s)** and **tier‑gated** (503 in Tier 3). **No scheduler / drift monitor / "every‑50" auto‑trigger exists** (documented design decision D‑M13‑03).
- Closure feedback path **already exists**: `POST /field/close/{event_id}` (`FieldService.close`) re‑ingests the event with `status="closed"` + `closed_datetime`, writes a `FieldClosureRow` (the M13 "report of record"), and emits a FIELD delta. Requires a richer `ClosureRequest` (`barricades_used`, `officers_used`, `officer_id`, `closed_datetime`, `diversion_activated`, `notes`).

### 1.7 Conventions
- Routers registered in `main.py` via `app.include_router(...)`.
- Tests: `pytest` + `pytest-asyncio` (auto mode), in‑memory SQLite via autouse `test_db` fixture (`tests/conftest.py`), `starlette.testclient.TestClient`; subscribers + `registry.load()` set up per test (see `tests/test_dashboard.py`). Canonical lowercase payloads.
- Scripts: live under `backend/scripts/`, run with `uv run python scripts/<name>.py`.

---

## 2. Target design decisions (resolve the guide's ambiguities)

**D1 — Dependencies (A‑0): add essentially nothing.**
`httpx>=0.28.1` is already a project dependency. The real A‑5 gutter‑points code is a hardcoded list + haversine — **`osmnx` is never imported** (the guide's "osmnx downloads 40 MB" gotcha is moot here; skip the 2–3 min heavy install of networkx/shapely/geopandas). The real A‑3 builds GeoJSON dicts by hand — **`geojson` not needed**. WebSockets already work through `uvicorn[standard]`. *Decision:* do not add `osmnx`/`geojson`. Adding an explicit `websockets` pin is optional and low‑value; default to **no pyproject change**. (If a reviewer insists on A‑0 literally, add only `websockets` and document why the others were dropped.)

**D2 — New endpoints live in one new module `grid_unlocked.maps`.**
Create `maps/router.py` (prefix `/api/v1`) for A‑3/A‑4/A‑5, registered in `main.py` — consistent with the domain‑modular architecture (rather than the guide's flat `routers/map_layers.py`). Gutter‑point constants go in `maps/gutter_points.py`.

**D3 — A‑2 incident broadcast = a new event‑bus subscriber + new `DeltaScope.INCIDENT`.**
Add `DeltaScope.INCIDENT` to `dashboard/schemas.py`. Add `dashboard/incident_subscriber.py` (mirroring `hotspots/subscriber.py`) that subscribes to `event_bus.subscribe_normalized` and publishes a `DashboardDelta(scope=INCIDENT, event_id=…, payload={corridor, junction, event_type, cause, lat, lng, status})`. Register it in `main.py` `lifespan()`.
- *Why not enrich with RCI/p_closure/station inline?* Those require features to be materialized and impact scored, which happens in other subscribers; doing it here risks ordering races and slows ingest. **Decision:** emit a lightweight incident signal; the frontend reacts by calling `GET /recommendations/{event_id}` (which builds the full card on demand). This keeps Stream A small and matches the existing on‑demand card model.
- *Wire‑contract note for Stream B/C:* the message is `{type:"dashboard.delta", scope:"incident", event_id, payload:{…}}`, **not** the guide's `{type:"event.ingest", payload:{…}}`. Document this so the frontend `useWebSocket` switches on `scope === "incident"`. (If we must match the guide's literal `type:"event.ingest"`, we add a second `ws.send` of a flattened message — defer unless Stream C requires it.)

**D4 — A‑6 learning‑close = thin endpoint that closes the event (feeds the buffer).**
Add `POST /api/v1/learning/close/{event_id}` accepting `{road_closed: bool, actual_clearance_minutes: int | None}`. Implementation: set the event to `closed` with a `closed_datetime` (now, or `start + actual_clearance_minutes` when provided) and `requires_road_closure = road_closed`, via the same re‑ingest mechanism `FieldService.close` uses (so it lands in the M13 recent pool). Then count `normalized_events WHERE status="closed"`; if `count % 50 == 0` and governance tier != 3, fire `start_retrain` as a **non‑blocking, non‑fatal** `asyncio.create_task`; otherwise just return the flag. Response: `{closed, trigger_retrain, buffer_size}`.
- *Overlap with `/field/close`:* keep both. `/field/close` is the officer "report of record" (requires resource counts). `/api/v1/learning/close` is the commander's one‑click "Close & Learn" for the live dashboard. Guard against the 409 the field path raises when a closure already exists (learning‑close should be idempotent / tolerant).

**D5 — A‑7 = leave the real card alone; add an optional flattened adapter only.**
Do **not** rewrite the action card. Optionally add `GET /recommendations/{event_id}/action-card` returning the guide's flat shape derived from the existing `ActionCard`:
`{event_id, corridor, junction, cause, p_closure, ict_p50_minutes (= round(ict_p50_h*60)), assigned_station, manpower_count, diversion_roads, vms_message, provenance}`.
This is purely additive (no behavior change) and lets the guide's frontend bind without touching M09. If Stream B agrees to consume the rich card directly, **skip A‑7 entirely.**

**D6 — A‑8 seed uses canonical vocab and no matview refresh.**
Use only valid causes; replace `'Road Work'→'construction'`, `'Breakdown'→'vehicle_breakdown'`. Do **not** issue `REFRESH MATERIALIZED VIEW active_events` — no such matview exists in this schema (the guide's "Known Gotcha" does not apply here; it would error).

---

## 3. Work plan — task by task

> Each task lists the real file(s), the exact corrections vs. the guide, and acceptance criteria. Code direction is precise enough to be mechanical; final code written at implementation time.

### Phase 0 — Dependencies (A‑0)
- **Files:** `backend/pyproject.toml` (likely **no change**).
- **Action:** Confirm `httpx` present (it is). Decide per **D1**; default to no edit. If adding `websockets`, run `uv sync`.
- **Accept:** `uv sync` clean; `uv run python -c "import httpx"` ok; no `osmnx` pulled.

### Phase 1 — Incident broadcast on ingest (replaces A‑1/A‑2)
- **Skip A‑1** (`ws/manager.py`) — duplicate of `DashboardBus`.
- **A‑2 (real work):**
  - `dashboard/schemas.py` — add `INCIDENT = "incident"` to `DeltaScope`.
  - `dashboard/incident_subscriber.py` *(new)* — `register_incident_subscribers()` that does `event_bus.subscribe_normalized(_on_normalized)`; `_on_normalized` publishes the INCIDENT `DashboardDelta` (per **D3**). Use `datetime.now(UTC)` for `emitted_at`. Swallow/log exceptions so a fanout failure never breaks ingest.
  - `main.py` — import and call `register_incident_subscribers()` inside `lifespan()` next to the other `register_*` calls.
- **Accept:** WS client connected to `/ws/dashboard` receives a `scope:"incident"` delta within ~1 s of `POST /ingest/astram`; ingest latency unaffected; existing `test_dashboard.py` still passes.

### Phase 2 — Map‑layer read endpoints (A‑3, A‑4, A‑5)
New module `grid_unlocked.maps` (per **D2**): `maps/__init__.py`, `maps/router.py` (`APIRouter(prefix="/api/v1", tags=["maps"])`), `maps/gutter_points.py`. Register in `main.py`.

- **A‑3 `GET /api/v1/heatmap`** — params `event_type: str | None`, `from_dt: datetime | None`.
  - Group `NormalizedEventRow` by `func.round(latitude,4)`, `func.round(longitude,4)`, `func.count()`.
  - Optional `where(event_type == event_type)` (lowercase values), `where(start_datetime >= from_dt)`.
  - Normalize weights by max count; return GeoJSON `FeatureCollection` (`[lng, lat]` order, `properties:{weight,count}`); empty collection when no rows.
  - **Fixes vs guide:** model name; **no** bogus `created_at`; historical heatmap counts all events (no status filter).
  - *Demo note:* shows as many points as are ingested — to get the headline "8,173 incidents", ingest the full ASTraM CSV (`scripts/replay_csv.py` currently caps `limit=100`; raise it / run a full replay). Operational, not Stream‑A code.
- **A‑4 `GET /api/v1/events/recent`** — param `limit: int = 50 (le=200)`.
  - `where(status == "active")`, `order_by(ingested_at.desc())`, `limit`.
  - **RCI:** `NormalizedEventRow` has none → LEFT JOIN the latest `ImpactScoreRow` per `event_id` (subquery on max `scored_at`, or `outerjoin` + order) and use `rci`, default `0.5` when absent.
  - Return `{events:[{event_id, corridor, event_type, lat, lng, rci, status, ingested_at}]}`.
  - **Fixes vs guide:** `"active"` not `"ACTIVE"`; `event_id` not `id`; `ingested_at` not `created_at`; join for RCI instead of `e.rci_score`.
- **A‑5 `GET /api/v1/gutter-points`**
  - Constant list of 8 bottlenecks in `maps/gutter_points.py` (Silk Board, Hebbal, KR Puram, Marathahalli, Nagavara, Mysore Rd KSRTC, Hope Farm, Tumkur Rd Yeswanthpur) with `lat/lng/severity/desc`.
  - Query active event coords (`status == "active"`), boost `live_severity` when an active event is within 1 km (haversine), clamp to 1.0.
  - **Fixes vs guide:** `"active"`; **no osmnx** (pure python).
- **Accept:** all three return 200 with correct shapes against a seeded DB; `events/recent` shows seeded active events with an RCI; `gutter-points` returns 8 with boosted severities near active events.

### Phase 3 — Learning close (A‑6)
- **File:** add to `learning/router.py` (+ a small method in `learning/service.py`, or reuse `IngestionService`). Endpoint per **D4**: `POST /api/v1/learning/close/{event_id}` with `ClosePayload{road_closed: bool, actual_clearance_minutes: int | None}`.
  - *Path prefix:* the existing learning router uses prefix `/learning`. To hit the guide's `/api/v1/learning/close/...`, either mount this on the `maps`/a new `/api/v1` router, or add a second `APIRouter(prefix="/api/v1/learning")` in the learning module. **Decision:** add it to the learning module under an `/api/v1/learning` router to keep learning code together; register in `main.py`.
  - Close the event (re‑ingest as `closed`, set `closed_datetime`, `requires_road_closure=road_closed`), tolerant of "already closed".
  - Count closed events; background `start_retrain` on the 50th (tier‑guarded, non‑fatal); return `{closed, trigger_retrain, buffer_size}`.
- **Fixes vs guide:** no `ReplayBufferEntry` insert (table doesn't exist); closure feeds the buffer by being `status="closed"`; retrain is tier‑gated & backgrounded.
- **Accept:** endpoint flips the event to `closed`; appears in `learning/buffer` recent pool on next `POST /learning/retrain`; returns the trigger flag; never 500s when retrain is unavailable (Tier 3).

### Phase 4 — Action‑card adapter (A‑7, optional)
- **File:** add `GET /recommendations/{event_id}/action-card` to `recommendations/router.py` per **D5**, delegating to `RecommendationService.build_card` and flattening (convert `ict_p50_h*60`, pull station from `card.dispatch.assignments[0].station_id`, derive a VMS string).
- **Decide with Stream B:** if the frontend will consume the rich `GET /recommendations/{event_id}`, **skip this.**
- **Accept (if built):** returns the flat shape; `ict_p50_minutes` is integer minutes; `assigned_station` populated when dispatch present, else `"UNASSIGNED"`.

### Phase 5 — Demo seed script (A‑8)
- **File:** `backend/scripts/seed_demo.py` *(new)* per **D6**.
  - `httpx` POST 20 events to `/ingest/astram` across Mysore Road / Bellary Road 1 / Tumkur Road with valid junctions/coords (within bbox), **canonical causes only**, `event_type` `planned`/`unplanned`, varied `priority`, `start_datetime` within the last ~2 h.
  - Print per‑event status; summary line. **No matview refresh.**
- **Accept:** `uv run python scripts/seed_demo.py` against a running API yields 20× `200` (zero 422s); afterwards `/api/v1/events/recent` and `/api/v1/gutter-points` reflect the seeded events.

### Phase 6 — Tests & verification
- **New tests** (mirror `tests/test_dashboard.py` / `conftest.py` patterns, canonical payloads, in‑memory SQLite, register subscribers + `registry.load()`):
  - `tests/test_maps.py` — heatmap shape/filters; recent‑events status+ordering+RCI join; gutter‑points count + proximity boost.
  - `tests/test_incident_broadcast.py` — WS receives `scope:"incident"` on ingest.
  - `tests/test_learning_close.py` — close flips status, returns flags, tolerant when retrain disabled.
  - (If A‑7 built) extend `tests/test_recommendations.py` for the adapter shape.
- **Run:** `cd backend && uv run pytest -q` (full suite stays green — regression guard for the M15 changes).
- **Manual E2E** (subset of guide §6.2, corrected): `docker compose up --build` → seed → `GET /api/v1/heatmap` (features[]) → `GET /api/v1/gutter-points` (8) → `GET /api/v1/events/recent` (active w/ rci) → connect `/ws/dashboard`, POST an ingest, observe `scope:"incident"` → `GET /recommendations/{event_id}` builds a card → `POST /recommendations/{card_id}/approve` (200) → `POST /api/v1/learning/close/{event_id}` (200).

---

## 4. Sequencing & dependencies
1. **Phase 0** (deps decision) — unblocks everything; trivial.
2. **Phase 2** (A‑3/A‑4/A‑5 read endpoints) — independent, highest demo value, lowest risk. Do first.
3. **Phase 1** (incident broadcast) — independent; touches shared M15 code, so land with its test.
4. **Phase 3** (learning close) — independent.
5. **Phase 4** (adapter) — optional; coordinate with Stream B.
6. **Phase 5** (seed) — after Phase 2 so it can be verified end‑to‑end.
7. **Phase 6** (tests) — alongside each phase; full‑suite gate before "done".

**Cross‑stream contracts to publish to B/C:** WS message is `scope:"incident"` (not `type:"event.ingest"`); approve is keyed by **`card_id`**; the canonical action card is `GET /recommendations/{event_id}` (rich) unless the A‑7 adapter is built.

---

## 5. Master checklist

**Phase 0 — Dependencies (A‑0)**
- [ ] Confirm `httpx` present; decide per D1 (default: no pyproject change; no `osmnx`/`geojson`)
- [ ] `uv sync` clean if anything changed

**Phase 1 — Incident broadcast (A‑1 skipped, A‑2 reworked)**
- [ ] Do **not** create `ws/manager.py` (DashboardBus already exists)
- [ ] Add `DeltaScope.INCIDENT` to `dashboard/schemas.py`
- [ ] Create `dashboard/incident_subscriber.py` (`register_incident_subscribers`, subscribe_normalized → INCIDENT delta, exception‑safe)
- [ ] Register subscriber in `main.py` `lifespan()`

**Phase 2 — Map layers (A‑3/A‑4/A‑5)**
- [ ] Create `maps/` module (`__init__`, `router.py` prefix `/api/v1`, `gutter_points.py`) and register in `main.py`
- [ ] `GET /api/v1/heatmap` — round/group/count GeoJSON; `event_type`+`from_dt` filters; no `created_at`
- [ ] `GET /api/v1/events/recent` — `status=="active"`, `order_by ingested_at desc`, RCI via ImpactScore join (default 0.5), `event_id`
- [ ] `GET /api/v1/gutter-points` — 8‑point constant + haversine boost; `status=="active"`; no osmnx

**Phase 3 — Learning close (A‑6)**
- [ ] `POST /api/v1/learning/close/{event_id}` `{road_closed, actual_clearance_minutes?}` (new `/api/v1/learning` router)
- [ ] Close via re‑ingest as `closed` (+`closed_datetime`, `requires_road_closure`); tolerant of already‑closed
- [ ] Count closed events; tier‑guarded, backgrounded, non‑fatal `start_retrain` on the 50th; return `{closed, trigger_retrain, buffer_size}`

**Phase 4 — Action‑card adapter (A‑7, optional)**
- [ ] Confirm with Stream B whether the rich `GET /recommendations/{event_id}` suffices (if yes, skip)
- [ ] Else add flattened `GET /recommendations/{event_id}/action-card` (`ict_p50_minutes = round(ict_p50_h*60)`, station from assignments, VMS string)

**Phase 5 — Seed (A‑8)**
- [ ] `scripts/seed_demo.py` — 20 events, **canonical causes** (`construction`/`vehicle_breakdown`/`accident`/`vip_movement`/`public_event`/`procession`), valid corridors, in‑bbox coords; **no matview refresh**
- [ ] `uv run python scripts/seed_demo.py` → 20× 200, zero 422

**Phase 6 — Tests & verification**
- [ ] `tests/test_maps.py`, `tests/test_incident_broadcast.py`, `tests/test_learning_close.py` (+ recommendations adapter test if built)
- [ ] `uv run pytest -q` full suite green (M15 regression guard)
- [ ] Manual E2E (corrected §6.2 sequence) passes

---

## 6. Risks, gotchas & out of scope
- **Heatmap corpus:** the "8,173 incidents" headline needs the full ASTraM CSV ingested; `scripts/replay_csv.py` caps at 100. Raise the cap / run a full replay before a demo. *(Operational, not Stream‑A code.)*
- **No `active_events` matview** in this schema — never call `REFRESH MATERIALIZED VIEW`. Endpoints read `normalized_events` directly.
- **ICT units:** always `*_h` (hours). Convert to minutes only at the API edge (`*60`).
- **Impact may be unscored** for a brand‑new event (features still materializing) — `events/recent` must default RCI gracefully; the adapter must tolerate a missing impact row.
- **Tier 3 gates retrain** — learning‑close must never 500 when retrain is unavailable.
- **Out of scope (other streams):** all of Stream B (map UI, decision card, layer toggles) and Stream C (Zustand store, `useWebSocket`, citizen/field/governance pages, navbar). The WS wire‑contract delta noted in §4 is the key hand‑off.

---

*Plan complete. No implementation performed. Next action on approval: execute Phases 0→6 in order.*
