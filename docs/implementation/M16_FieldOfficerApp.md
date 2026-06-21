# M16 — FieldOfficerApp (Implementation Record)

**Version:** 1.0
**Backend path:** `backend/src/grid_unlocked/field/`
**Frontend path:** `frontend/app/field/[recommendationId]/` (new route group in the existing Next.js app)
**Status:** Implemented (MVP — packet assembly, ack, closure capture with resource labels, tier proxy; localStorage-backed offline queue, no real Service Worker)
**Spec reference:** [IMPLEMENTATION_MODULES.md § M16](../IMPLEMENTATION_MODULES.md)

---

## Purpose

Field officers need their dispatch assignment packet — route/unit, ICT quantiles, top diversion — within seconds, plus a one-step closure form capturing actual resources used (barricades, officers) for future M13 learning labels. M16 is a mobile-responsive page within the existing Grid Unlocked Next.js app, not a separate app, consuming M07/M03/M08 outputs.

---

## Key findings from reading the existing codebase

- **No `assignment_id` exists anywhere.** `dispatch/schemas.py::Assignment` has no id of its own; `DispatchRecommendation.recommendation_id` is the only stable identifier, and it already covers a list of assignments. `recommendations/service.py` had already assumed this — it builds `field_packet_link = f"/field/packet/{rec.recommendation_id}"` when a card has dispatch assignments, even though M16 didn't exist yet. M16 uses `recommendation_id` as the path param for `/field/packet/{assignment_id}`'s contract.
- **`DispatchRepository.get_recommendation(recommendation_id)`** (`dispatch/repository.py`) already existed, unused by any router — M16 calls it directly, in-process.
- **M13's replay buffer has zero resource-label support today.** `learning/buffer.py::_load_recent_pool()` reads only `cause`/`corridor`/`is_planned`/`closure`/`duration_h`/`event_observed`/`veh_type` straight off `NormalizedEventRow`. `field_closures` rows are captured by this module but **not** joined into that training dataframe — a deliberate scope boundary, not an oversight (see Known limitations).
- **Closure must re-submit the full event, not a partial payload.** `ingestion/normalizer.py::normalize_payload()` re-validates required fields and `IngestRepository.upsert_event()` does a full-column overwrite on re-ingest — a partial `{event_id, status, closed_datetime}` payload would null out the event's other fields.
- **SQLite round-trips datetimes as naive** (the same caveat `learning/buffer.py` already documents for its own pool-loading code). A bug was found and fixed during implementation: building the closure re-submission payload from `event.model_dump(mode="json")` (whose `start_datetime` comes back naive after a SQLite round-trip) alongside a tz-aware `closed_datetime` from the request body made `ingestion/validator.py::detect_anomalies()`'s `closed < start` comparison raise `TypeError: can't compare offset-naive and offset-aware datetimes`. Fixed in `field/service.py::close()` by stripping tzinfo from `closed_datetime` to match `start_datetime`'s awareness whenever the event's own timestamp came back naive (Postgres, which keeps tzinfo on both sides, is unaffected).
- **No service worker infrastructure exists anywhere in this app** — confirmed zero `next-pwa`/`public/sw.js`/`serviceWorker.register` calls. Building one would be disproportionate to the spec's actual testable requirement ("offline queue drains on reconnect"); a `localStorage`-backed queue satisfies it without new build infrastructure.
- **`frontend/lib/types.ts` had drifted from the backend** since M17: `ActionCard` was missing the `source` field added during M17, and `DeltaScope` was missing `"citizen"`. Both fixed while touching this file for M16's own additions.
- **No real station SOP PDF exists in this repo** (only an unrelated research PDF under `docs/`). Tier 3 shows a placeholder message, not a fabricated link.

---

## Core behavior

### Packet assembly (`field/service.py::get_packet`)

`DispatchRepository.get_recommendation(recommendation_id)` → 404 if missing or has no assignments → `event_id = rec.assignments[0].event_id` → `IngestionService.get_event(event_id)`. `ImpactService.score(event_id)` and `DiversionService.scenarios(event_id)` are each wrapped in try/except — a transient downstream failure degrades to zeroed ICT bands / no diversion rather than failing the whole packet, since packet render must stay fast (spec: ≤3s on 4G). `rec.tier_at_decision` (tier when dispatched) is distinct from the live `GET /field/tier` call (tier right now) — the packet always shows both, never conflated. `navigation_deep_link` is a Google Maps search URL built from the event's own `latitude`/`longitude` — no fabricated external service.

### Acknowledgement (`field/service.py::ack`)

Upserts a `field_acknowledgements` row (one per `recommendation_id`, idempotent — re-acking just updates `officer_id`/`acknowledged_at`) and publishes a `DeltaScope.FIELD` dashboard delta.

### Closure (`field/service.py::close`)

Idempotency guard (409 if `field_closures` already has a row for this `event_id`) → fetch event (404 if missing) → re-submit the **full** event payload via `IngestionService.ingest(status="closed", closed_datetime=...)` → **only on success**, best-effort persist the `field_closures` resource-label row (log-and-continue if this secondary write fails — the officer-facing event closure must never fail just because the auxiliary label write did) → publish a `DeltaScope.FIELD` delta. This ordering is deliberate: `NormalizedEventRow.status="closed"` is the single source of truth M13's existing pool already depends on unconditionally; persisting `field_closures` first and having the ingest call then fail would leave a confusing, silently-wrong "closure on record that didn't actually close anything" state.

`barricades_used >= 0` / `officers_used >= 1` are enforced at the Pydantic level (`Field(ge=0)`/`Field(ge=1)` on `ClosureRequest`), matching this codebase's existing convention for simple numeric bounds (e.g. `diversions/schemas.py::ComputeRequest`).

### Tier proxy (`field/service.py::get_tier`)

Pure passthrough to `GovernanceService.get_tier()` — no new logic.

---

## API

| Endpoint | Behavior |
|---|---|
| `GET /field/packet/{recommendation_id}` | Assignment bundle: assignments, ICT bands, top diversion, nav link, ack/closed state, provenance |
| `POST /field/ack/{recommendation_id}` | `{officer_id}` → idempotent upsert, publishes a dashboard delta |
| `POST /field/close/{event_id}` | `{closed_datetime, barricades_used, officers_used, diversion_activated, notes?, officer_id}` → closes the event, persists resource labels |
| `GET /field/tier` | Live tier proxy to M14 |

---

## Storage

Two new tables (`backend/src/grid_unlocked/db/models.py`):

- `field_closures` — report-of-record for officer-submitted resource labels (`event_id`, `recommendation_id` nullable, `barricades_used`, `officers_used`, `diversion_activated`, `notes`, `closed_datetime`, `officer_id`).
- `field_acknowledgements` — one row per `recommendation_id` (primary key), upserted on each ack.

A dedicated `field_acknowledgements` table was chosen over bolting ack-mutation onto `DispatchRecommendationRow` — that row's only content is an opaque `recommendation_json` blob, written once and never mutated elsewhere; a small dedicated table matches this codebase's existing pattern of small audit-style tables alongside their main entity (e.g. `TierTransitionRow`, `DrillResultRow`).

---

## Frontend

`frontend/app/field/[recommendationId]/page.tsx` — the **first dynamic route** in this app. Uses `useParams<{ recommendationId: string }>()` (a Client Component hook, synchronous in this Next.js 16 app) rather than the Promise-based server-component `params` prop, since every existing page here is `"use client"` with client-side fetching only — confirmed via `node_modules/next/dist/docs/` per this repo's `AGENTS.md` warning about this Next.js version's breaking changes from training data.

`_components/`: `packet-header.tsx` (id, source/tier badges, provenance, nav link, ack button), `ict-panel.tsx` (P20/P50/P80 + severity badge), `diversion-panel.tsx` (top diversion summary, "no diversion available" empty state), `closure-form.tsx` (barricades/officers/diversion-activated/notes, client-side validation mirroring the backend's bounds, owns the offline-queue retry).

**Tier-aware degradation lives entirely client-side** — `FieldPacket` always returns full data; the React components render it differently per the live tier (mirroring `/live`'s existing `action-card-panel.tsx` pattern):
- Tier 1: full packet, all panels live.
- Tier 2: same ICT data labeled "cached bands"; diversion panel shows only `route_summary` text, hides path/ETA detail.
- Tier 3: ICT and diversion panels hidden entirely; a static "Tier 3 — manual mode, refer to station SOP" placeholder (no PDF link); the closure form remains the only interactive element.

**Offline queue** (`frontend/lib/field-offline-queue.ts`) — `localStorage`-backed, no Service Worker: a failed `api.fieldClose` call gets queued instead of hard-erroring; a `window.addEventListener("online", ...)` effect in the page retries queued entries on reconnect. The "cache last packet" half of the spec is similarly approximated — the last successfully-fetched `FieldPacket` is cached under `field-packet-cache-${recommendationId}` and rendered (with a "showing cached data" banner) if a live fetch fails.

---

## Source files

| File | Responsibility |
|---|---|
| `field/schemas.py` | `FieldPacket`, `AckRequest`/`AckResponse`, `ClosureRequest`/`ClosureResponse` |
| `field/repository.py` | Ack upsert, closure persistence/idempotency lookup |
| `field/service.py` | Packet assembly, ack, closure flow ordering |
| `field/router.py` | 4 contract endpoints |
| `frontend/lib/field-offline-queue.ts` | localStorage closure queue + packet cache |
| `frontend/app/field/[recommendationId]/page.tsx` + `_components/` | Field officer UI |

Modified: `db/models.py`/`db/session.py` (2 new tables), `dashboard/schemas.py` (`DeltaScope.FIELD`), `main.py` (router include), `frontend/lib/api.ts`/`lib/types.ts` (field endpoints/types + the pre-existing `ActionCard.source`/`DeltaScope` drift fix from M17).

---

## Tests

`backend/tests/test_field.py` — 13 tests: packet contains provenance + ICT bands; 404 on unknown recommendation; packet renders with `top_diversion: null` when the diversion scenario has no routes (via monkeypatching `DiversionService.scenarios`, since no real corridor in this codebase's atlas actually produces zero routes — every corridor falls back to a default set); ack persists and is idempotent; ack 404; close writes `field_closures` AND flips the underlying event to `status="closed"`; `barricades_used=-1` → 422; `officers_used=0` → 422; closing twice on the same event → 409; close on unknown event → 404; `/field/tier` matches `/governance/tier`'s live state; ack/close each publish a `DeltaScope.FIELD` delta (verified via a `dashboard_bus.publish` spy, same technique as M17's tests). Uses the `import grid_unlocked.db.session as _session_module` pattern from the start — the stale-`SessionLocal`-reference bug found during M17 was not reintroduced.

`frontend/tests/unit/` — `field-closure-form.test.tsx` (8 tests: validation blocks negative barricades/zero officers before calling the API; valid input calls `api.fieldClose` with the exact expected body; already-closed state hides the form) and `field-offline-queue.test.ts` (enqueue, drain-on-online success removes the entry, drain-on-online with continued failure keeps it queued, empty-queue no-op).

`frontend/tests/e2e/field-packet.spec.ts` — one Playwright spec against a real production build + a real running backend: ingest an event, call `/dispatch/recommend` for a `recommendation_id`, navigate to `/field/{id}`, confirm the packet renders, fill and submit the closure form, confirm the success toast.

Full backend suite: 207 passed (194 prior + this module's 13), the same 6 pre-existing `test_dashboard.py` failures excluded (confirmed unrelated, reproduced identically on an unmodified checkout before M16). Frontend unit suite: 24 passed (17 prior + this module's 7 new test cases across 2 files).

A second, environment-only issue was found and resolved (not a code bug, but worth recording): running the E2E suite against non-default ports (backend :8100, frontend :3100, to avoid colliding with a real dev server) tripped CORS — `config.py::Settings.cors_allow_origins` defaults to `localhost:3000`/`127.0.0.1:3000` only. Resolved for this one-off verification run via `GRID_CORS_ALLOW_ORIGINS` env override, not a code change — the real app always runs on port 3000 per the documented workflow, so this isn't a defect to fix in `config.py`.

---

## Known limitations (MVP, deliberate scope reductions)

- `D-M16-01` — M13's `learning/buffer.py` does not yet consume `field_closures` resource labels. They are captured and persisted now; joining them into the training dataframe is separate follow-up work, not done here.
- `D-M16-02` — No real authentication. `officer_id` is a free-text field with zero token verification, identical to every other actor-id convention in this codebase (`commander_id`, `operator_id`, `user_ref`).
- `D-M16-03` — No real Service Worker / Cache API — offline support is a `localStorage`-backed queue and packet cache only.
- `D-M16-04` — No fabricated SOP PDF link — Tier 3 shows an explanatory placeholder; no asset that doesn't exist is linked.
- ASTraM BOT replacement, ANPR/camera integration, officer GPS tracking — untouched, per spec's explicit out-of-scope list.

---

## Next

- **M18** CitizenApp — the remaining MVP-scope frontend module, independent of M16.
- Wiring `DeltaScope.FIELD` deltas into `/live`'s panels so commanders see field acknowledgement status without a separate poll (the data path already exists; only the dashboard-side consumption is unbuilt).
- M13 buffer enrichment with `field_closures` resource labels, once that module's training pipeline is revisited.
- Phase 1.5/2: real Service Worker, real station SOP asset, push-based (not client-polled) tier badge.
