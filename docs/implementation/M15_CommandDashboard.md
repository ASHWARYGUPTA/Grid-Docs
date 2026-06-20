# M15 — CommandDashboard (Implementation Record)

**Version:** 1.0
**Backend path:** `backend/src/grid_unlocked/dashboard/` (WebSocket fanout only — every panel's data still comes directly from M05/M06/M08/M09/M13/M14)
**Frontend path:** `frontend/` (Next.js 14+ App Router, TypeScript, shadcn/ui + Tailwind)
**Status:** Implemented (MVP — `/live`, `/planned`, `/governance`, `/analytics` routes; in-process WebSocket fanout; citizen triage placeholder pending M17)
**Spec reference:** [IMPLEMENTATION_MODULES.md § M15](../IMPLEMENTATION_MODULES.md), [ARCHITECTURE.md § 9.1](../ARCHITECTURE.md)

---

## Purpose

M15 is the Primary TMC UI: the first and only frontend in the repo. Every
prior module (M01–M11, M13, M14) is REST-only, consumed via curl/Swagger —
M15 makes the backend's real-time intelligence (alert queue, hotspots,
propagation ripples, action cards, governance tier, learning gate) visible
to a human operator. It is also the architectural foundation for M16
(FieldOfficerApp) and M18: all three are one Next.js application, not
separate apps, per `ARCHITECTURE.md` §9.4's single-browser-box diagram.

---

## Routes

| Route | Panels |
|---|---|
| `/live` | Alert queue, live map, action card (approve/reject) |
| `/planned` | 72h planned-event timeline |
| `/governance` | Health rollup, cascade drills, learning gate status |
| `/analytics` | Citizen triage (placeholder — M17 not implemented) |

---

## Core behavior

### WebSocket transport — `dashboard.delta`

No WebSocket infrastructure existed anywhere in the backend before this
module. `dashboard/bus.py::DashboardBus` is a new in-process fanout —
deliberately mirroring `ingestion/bus.py::InProcessEventBus`'s shape
(register/publish, no external broker) rather than introducing Redis
pub/sub, matching `TECH_STACK.md`'s own "M15 WebSocket fanout" tag under
**Phase 1.5**, not MVP.

`GET /ws/dashboard` (FastAPI native `WebSocket`, not a separate library)
accepts a connection, registers it with `DashboardBus`, and pushes
`DashboardDelta` JSON until the client disconnects:

```json
{
  "type": "dashboard.delta",
  "scope": "card" | "tier" | "hotspot",
  "event_id": "string | null",
  "payload": { ... },
  "emitted_at": "iso8601"
}
```

This schema didn't exist anywhere in the docs (`dashboard.delta` was named
but never defined) — it's new, minimal, and intentionally narrow: only
**individual card changes**, **tier/shadow-mode changes**, and
**hotspot-affecting ingests** are pushed. Queue-wide and health-rollup
changes stay pull-only (the frontend's own polling), since the spec's
payload description ("event cards... tier badge") doesn't call for a
queue-wide push and a narrower hook surface means fewer call sites touched
in M09/M14/M05.

### Emission hooks (one-line additions, no refactors)

| Source | Trigger | Scope |
|---|---|---|
| `recommendations/service.py::build_card()` | Card reaches `COMPLETE` | `card` |
| `recommendations/service.py::approve()` / `reject()` | Approval recorded | `card` |
| `governance/service.py::override_tier()` / `set_shadow_mode()` | Manual change | `tier` |
| `governance/service.py::evaluate_auto_transition()` | Automatic tier change | `tier` |
| `hotspots/subscriber.py::_handle_normalized` | New event ingested | `hotspot` |

Each is a single `await dashboard_bus.publish(...)` call inserted at an
existing write path — no service was refactored to accommodate this.

### Frontend data flow

Every panel is a **REST proxy plus a WebSocket patch**, not a WebSocket-only
view: on mount, each page fetches its REST snapshot (`lib/api.ts`); the
`useDashboardSocket()` hook (`lib/ws.ts`) then exposes the latest delta,
and `/live`'s `page.tsx` re-fetches only the affected piece (queue on
`card`/`hotspot`, the open card on a matching `card` delta) instead of
reloading the whole page. On disconnect, the hook auto-reconnects with
exponential backoff (500ms doubling to 8s) — the client never needs a full
page reload to resume receiving deltas.

### Tier-aware rendering (no new backend fields)

`/governance/tier`'s existing `tier`/`shadow_mode`/`manual_mode` fields
(M14, already returned today) drive all degradation behavior client-side:

- **Tier 1**: full dispatch section, approve/reject enabled (unless shadow
  mode).
- **Tier 2**: `ActionCardPanel` shows a "GREEDY_FALLBACK (static forecast)"
  badge — MILP/ML untrustworthy per spec.
- **Tier 3 / `manual_mode`**: a destructive-styled banner reads "continuity
  SOP mode... audit-only," and approve/reject becomes informational —
  matches the spec's literal Tier 3 SOP-fallback behavior already
  implemented server-side in `recommendations/service.py::_sop_fallback_card`.
- **Shadow mode**: Approve renders disabled with a `Tooltip` explanation
  (`"Disabled — shadow mode active, approvals are logged but not
  executed"`) — the spec's literal shadow-UI testing decision. The tooltip
  trigger wraps a `pointer-events-none` button rather than relying on the
  native `disabled` attribute, since disabled HTML elements don't receive
  hover events in most browsers and would otherwise make the explanation
  unreachable.

### Citizen triage placeholder

`/analytics` renders an explicit empty state ("Citizen reporting service
not yet available") rather than a stub form or silently-omitted route —
M17 CitizenReportService doesn't exist in this codebase yet.

---

## API additions (small, backend-side)

- `QueueItem.p_closure: float` (`recommendations/schemas.py`) — the alert
  queue panel needs to *display* the P(closure) value already computed
  server-side for `_alert_priority()`'s RCI×P(closure)×peak sort; this is a
  display field only, the sort order itself was already correct.
- `GET /learning/jobs/latest` (`learning/router.py` +
  `LearningRepository.get_latest_job()`) — the governance page's learning
  panel needs the most recent retrain job without the operator supplying a
  `job_id`; no existing M13 endpoint covered this lookup.
- `CORSMiddleware` (`main.py`) + `settings.cors_allow_origins`
  (`config.py`) — found missing during manual smoke testing: the browser
  silently blocks cross-origin fetches from the Next.js dev/prod server to
  the FastAPI backend without it. Defaults to `localhost:3000` /
  `127.0.0.1:3000`.

---

## Frontend stack

- **Next.js 14+ App Router, TypeScript, pnpm** — one app, M15's routes are
  the first route group; M16/M18 land as future route groups in the same
  app per the architecture doc's single-browser diagram.
- **shadcn/ui + Tailwind** for every UI primitive (`Button`, `Dialog`,
  `Badge`, `Tabs`, `Card`, `Tooltip`, `Sheet`, `Table`, `Skeleton`,
  `Sonner`) — this shadcn version is built on **base-ui**, not Radix:
  triggers use a `render={<Element />}` prop instead of `asChild` +
  manually-wrapped children.
- **MapLibre GL JS + h3-js** for the live map — H3 hex polygons for
  observed hotspot clusters (`hotspots/observed`'s real
  `centroid_lat`/`centroid_lon`/`h3_cells`), a marker at the selected
  card's `hotspot_context.h3_res7`. Predicted hotspots
  (`hotspots/predicted`) have no geo coordinates in their response shape
  (corridor-level forecasts only) — rendered as a corridor lift list
  overlay instead of fabricated map pins.
- **Playwright** (E2E, against a **production build** — `next build &&
  next start`) and **Vitest + React Testing Library** (unit).

---

## Source files

| File | Responsibility |
|---|---|
| `backend/src/grid_unlocked/dashboard/schemas.py` | `DashboardDelta`, `DeltaScope` |
| `backend/src/grid_unlocked/dashboard/bus.py` | `DashboardBus` — in-process WS fanout |
| `backend/src/grid_unlocked/dashboard/router.py` | `WebSocket /ws/dashboard` |
| `frontend/lib/types.ts` | TypeScript mirrors of backend Pydantic schemas |
| `frontend/lib/api.ts` | Typed REST client, one function per endpoint |
| `frontend/lib/ws.ts` | `useDashboardSocket()` — connect, reconnect/backoff, latest delta |
| `frontend/components/tier-badge.tsx` | Header tier badge, polled + delta-patched |
| `frontend/app/live/page.tsx` + `_components/` | Alert queue, map, action card panel |
| `frontend/app/planned/page.tsx` | 72h timeline |
| `frontend/app/governance/page.tsx` | Health / drills / learning tabs |
| `frontend/app/analytics/page.tsx` | Citizen triage placeholder |

---

## Tests

| File | Count | Coverage |
|---|---|---|
| `backend/tests/test_dashboard.py` | 6 | WebSocket connects + receives a card delta on approve; hotspot delta on ingest; multiple simultaneous connections all receive the same delta; disconnect+reconnect doesn't crash the server; tier delta on override; card delta arrives within the spec's 5s latency contract |
| `backend/tests/test_recommendations.py` | +1 assertion | `QueueItem.p_closure` present on every queue item, in `[0, 1]` |
| `frontend/tests/unit/alert-queue.test.tsx` | 4 | Renders rows in backend-given order, empty state, click → `onSelect(event_id)`, 2-decimal formatting |
| `frontend/tests/unit/tier-badge.test.tsx` | 5 | Loading placeholder, Tier 1 label, shadow-mode suffix, Tier 3 tooltip explanation, re-fetch on tier-scoped delta |
| `frontend/tests/unit/ws.test.tsx` | 4 | Connects + `connected=true` on open, exposes parsed delta on message, exponential backoff reconnect sequencing, no reconnect after unmount |
| `frontend/tests/e2e/dashboard.spec.ts` | 4 | New event → map pin + action card within 5s; shadow mode disables approve with a hoverable explanation; Tier 3 override shows the manual-mode banner; WebSocket survives a network blip and the queue still picks up a subsequent ingest |

A real bug was found and fixed during E2E test development: ingestion's
`normalize_corridor()` (M01, pre-existing) maps any corridor string outside
`ingestion/vocab.py::VALID_CORRIDORS` to `null` — early test data used
invented corridor names ("ORR Test Corridor 1") that silently normalized
away, making rows impossible to find by corridor text. Fixed by using real
corridor names from the vocab in every E2E fixture, not a test framework
bug.

**Sandbox environment note**: Turbopack dev mode's HMR WebSocket failed its
handshake in this environment (no outbound access for that specific
upgrade), which left React hydration silently stuck — `useEffect`s and even
`useState` click handlers never fired despite no console errors. This is
why Playwright's config (`playwright.config.ts`) always targets `next
build && next start`, never `next dev` — a real deployment is unaffected
since the issue only reproduced when HMR itself couldn't complete its
handshake.

**Pre-existing M02 race found during `docker compose up` verification (not
an M15 bug, not fixed here)**: `features/repository.py::save_snapshot()`
does a `session.get()`-then-insert-or-update without a unique-constraint
upsert. Under Postgres's real connection concurrency (unlike SQLite's
single-connection `StaticPool` in the test suite, which serializes this
away), two near-simultaneous requests materializing features for the same
uncached `event_id` can both see no existing row and both `INSERT`,
producing a transient `UniqueViolationError` / 500 on whichever endpoint
triggered the second materialization (observed once on
`GET /recommendations/queue` immediately after `POST /ingest/astram` in the
Dockerized stack). The request is safely retryable — a second call
succeeds immediately, the row exists, and no data is lost — but it is a
real bug in M02, not something to silently paper over inside M15's panels.

**Pre-existing Dockerfile gap found and fixed during the same verification
pass**: the root `Dockerfile` never copied `backend/models/` into the `api`
image, so `ImpactRegistry.load()` always logged "M03 models not found... —
using rule-based fallback" and M14's health probe correctly auto-downgraded
to Tier 2 on every Docker run, regardless of M15. Fixed by adding `COPY
backend/models /app/backend/models` + `GRID_MODELS_DIR` to the Dockerfile,
and a read-write bind mount (`./backend/models:/app/backend/models`, not
read-only — M13's promotion flow writes new `v2/`, `v3/`, ... directories
here at runtime) to `docker-compose.yml`'s `api` service. Verified
end-to-end: `governance/health` now reports `M03_Impact: healthy / "ML
models loaded"`, and `POST /impact/score` returns
`model_versions.source: "ml"` with the real trained LightGBM/Cox-PH
artifacts, not the rule fallback.

---

## Known limitations (MVP, deliberate scope reductions)

- `D-M15-01` — Citizen triage (`/analytics`) is an explicit placeholder;
  M17 CitizenReportService doesn't exist yet.
- `D-M15-02` — WebSocket fanout is in-process (`DashboardBus`), not Redis
  pub/sub — same "MVP now, Redis Phase 1.5" precedent as M01's event bus.
  A future multi-instance deployment would need this swapped for a shared
  broker.
- `D-M15-03` — Only individual card/tier/hotspot changes are pushed;
  queue-wide and health-rollup changes are pull-only (15s/30s client polls).
- Predicted hotspots render as a list overlay, not map pins —
  `hotspots/predicted`'s response has no per-forecast geo coordinates
  (corridor-level only), so there's nothing to plot without inventing
  coordinates.
- The live map's MapLibre base style (`demotiles.maplibre.org`) is a public
  demo tile source — fine for a hackathon/MVP, not a production basemap.

---

## Next

- **M16** FieldOfficerApp — a new route group in this same Next.js app, per
  the architecture doc; reuses `lib/api.ts`/`lib/ws.ts`/the tier badge.
- **M18** — likewise a route group in this app, not a separate build.
- **M17** CitizenReportService, once implemented, replaces `/analytics`'s
  placeholder with real photo/ICT-band triage and a `source=CITIZEN`
  verify/reject workflow.
- Redis-backed `DashboardBus` (Phase 1.5) if/when the API runs as more than
  one process.
