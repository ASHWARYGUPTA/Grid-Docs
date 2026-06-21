# M18 — CitizenApp (Implementation Record)

**Version:** 1.0
**Frontend path:** `frontend/app/report/`
**Status:** Implemented (MVP — report submission, ICT quote display, corridor subscriptions, in-tab pre-alert toasts; no backend changes)
**Spec reference:** [IMPLEMENTATION_MODULES.md § M18](../IMPLEMENTATION_MODULES.md)

---

## Purpose

Commuters need a lightweight interface to report congestion with a photo, see an estimated clearance time immediately, and receive pre-notifications for corridors they care about — without replacing ASTraM's full citizen app (fines, violations). M18 is a frontend-only module: it consumes M17's already-implemented `citizen/` backend (`POST /citizen/report`, `GET /citizen/report/{id}`, `POST /citizen/subscribe`, `DELETE /citizen/subscribe/{id}`) with no backend changes required.

---

## Key findings from reading the existing codebase

- **The spec's `GET /citizen/nearby-hotspots?lat=&lon=` endpoint does not exist** in M17's actual router. Building it was out of scope for "M18 is a frontend module" — skipped, not silently dropped (see Known limitations). The confirmation screen instead shows only the report's own snapped corridor/H3 cell and ICT bands, which `CitizenReport`'s response already contains in full.
- **No server-side rate limiting** (spec's "max 3 reports/hour/user_ref") exists anywhere in this codebase — M17's own implementation doc already flagged this as out of scope, confirmed still true. Not invented here.
- **Location resolution priority is entirely server-side**: the backend tries device `lat`/`lon` form fields first, falls back to EXIF GPS extraction from the photo, and 400s if neither is present. The frontend's only job is to attempt `navigator.geolocation`, send whatever it gets (or omit `lat`/`lon` entirely if permission is denied so the backend's EXIF fallback can still kick in), and surface the 400 if both are missing.
- **`frontend/lib/api.ts`'s `request<T>()` helper always sets `Content-Type: application/json`**, which breaks multipart upload (the browser must set its own `multipart/form-data; boundary=...`). `api.citizenReport()` uses a raw `fetch()` call instead, bypassing `request<T>()` entirely.
- **The dashboard WebSocket (`useDashboardSocket()`) is a single shared firehose** — every `DashboardDelta`, any scope, arrives through one `lastDelta` value. The pre-alert listener filters `scope === "citizen"` and `payload.type === "CitizenPreAlert"` client-side, then checks the alert's `subscription_id` against this browser's own locally-stored subscriptions before toasting — `CitizenReportSubmitted` deltas (meant for M15's commander dashboard) are ignored by this client.
- **`/analytics` is the commander-facing citizen-triage placeholder (M15), a different audience from M18.** Its copy claimed "M17 CitizenReportService has not been implemented yet," which was stale now that M17 has shipped — corrected to note that a dedicated commander-side triage panel surfacing pending citizen reports on `/live` still doesn't exist (a real, separate gap, not part of this module).
- **No PWA manifest or Service Worker infrastructure exists** in this app (same conclusion as M16) — pre-alerts are in-tab `sonner` toasts requiring the tab to be open with a live WebSocket connection, not native browser push.
- **22 corridors total** (21 named + `"Non-corridor"`) — confirmed directly from `data/astram_events.csv`'s `corridor` column, matching the set `citizen/geo.py::nearest_corridor()` snaps against. No corridor list constant exists in the backend to import; hardcoded in `subscription-manager.tsx` as the authoritative list, since the backend builds this set at seed-time from CSV data, not from a static export the frontend can request.
- **`user_ref` is free-text, no auth** — a random client-side UUID (`crypto.randomUUID()`) generated once and persisted in `localStorage`, matching every other actor-id convention in this codebase.

## Core behavior

### Report submission (`_components/report-form.tsx`)

Attempts `navigator.geolocation.getCurrentPosition()` on a "Share my location" button (not automatically on mount, to avoid an unsolicited permission prompt). Submit is allowed if either a photo is attached or location was captured — not both — since the backend's own fallback chain (device GPS → EXIF GPS) means a photo alone can still succeed if it carries EXIF GPS data; the photo itself is always required by the backend (`File(...)`, non-optional), so the client always requires a photo file regardless of location state. On submit, builds a `FormData` with `photo`, optional `lat`/`lon`, optional `description`, and posts via `api.citizenReport()`.

### Confirmation (`_components/report-result.tsx`)

Plain-language ICT formatter: `formatIctQuote(p50, p80)` → "Typical clearance: ~{p50}h" / "Worst case: up to ~{p80}h", matching the spec's exact phrasing pattern. Displays snapped corridor, H3 cell, and cause hint from the `CitizenReport` response.

### Subscriptions (`_components/subscription-manager.tsx`)

Corridor-name subscription only (no raw H3-cell subscription — see Known limitations). Calls `POST /citizen/subscribe` with `{user_ref, corridors: [selected], h3_cells: []}` (the backend's `SubscriptionRequest` already accepts an empty `h3_cells` list). Subscriptions persist in `localStorage` as `{subscription_id, corridors}[]`; removing one calls `DELETE /citizen/subscribe/{id}` then drops it locally regardless of that call's success (best-effort, since a stuck-subscribed UI with no way to remove it is worse than a soft-deleted-but-still-shown-locally edge case).

### Pre-alerts (`app/report/page.tsx`)

An effect filters `useDashboardSocket()`'s `lastDelta` for `scope === "citizen"` and `payload.type === "CitizenPreAlert"`, then calls `matchesSubscription(payload, subscriptions)` (a pure function in `subscription-manager.tsx`, unit-tested directly) to check whether the alert's `subscription_id` belongs to this browser. Matches fire a `sonner` toast — `toast.error` for `severity_band === "Orange"`, `toast.warning` otherwise.

### Recent reports (`_components/recent-reports.tsx`)

Last 5 submitted reports cached in `localStorage` (`addRecentReport()` caps at 5, drops oldest). On mount, each row independently polls `GET /citizen/report/{id}` once to refresh its status badge (`pending`/`verified`/`rejected`) — no WebSocket needed since status transitions are commander-driven and infrequent.

---

## Frontend

`frontend/app/report/page.tsx` — top-level page (not a dynamic route, since a citizen has no id ahead of time), `"use client"`, composing the form, last result, subscription manager, recent reports list, and the pre-alert toast effect. Reuses the existing shared `NavBar`/`RootLayout` rather than a separate citizen-only shell — acceptable MVP simplification since `/report` calls none of the commander-side verify/reject endpoints, so functional separation from commander triage logic already holds without a separate UI shell.

`_components/`: `report-form.tsx`, `report-result.tsx`, `subscription-manager.tsx`, `recent-reports.tsx`.

`lib/api.ts` additions: `citizenReport(formData)` (raw `fetch`, multipart), `citizenReportStatus(reportId)`, `citizenSubscribe(req)`, `citizenUnsubscribe(subscriptionId)`.

`lib/types.ts` additions: `CitizenReport`, `CitizenReportStatusResponse`, `SubscriptionRequest`, `SubscriptionResponse`, `CitizenPreAlertPayload` — mirrored 1:1 from `citizen/schemas.py`.

`lib/citizen-storage.ts` (new) — `getOrCreateUserRef()`, `readSubscriptions()`/`writeSubscriptions()`, `readRecentReports()`/`addRecentReport()`, same defensive `localStorage` try/catch pattern as `field-offline-queue.ts`.

`components/nav-bar.tsx` — added `{ href: "/report", label: "Report" }`.

`app/analytics/page.tsx` — corrected stale copy now that M17/M18 exist; explicitly notes the remaining gap (no commander-facing triage panel for citizen reports on `/live`).

---

## Source files

| File | Responsibility |
|---|---|
| `app/report/page.tsx` | Page composition, pre-alert toast filtering |
| `app/report/_components/report-form.tsx` | Geolocation + photo capture, submit |
| `app/report/_components/report-result.tsx` | ICT quote formatting, confirmation panel |
| `app/report/_components/subscription-manager.tsx` | Corridor list, subscribe/unsubscribe, `matchesSubscription()` |
| `app/report/_components/recent-reports.tsx` | Last-5 report list with status polling |
| `lib/citizen-storage.ts` | localStorage helpers (user_ref, subscriptions, recent reports) |

Modified: `lib/api.ts`/`lib/types.ts` (citizen endpoints/types), `components/nav-bar.tsx` (new route), `app/analytics/page.tsx` (stale-copy fix).

No backend files were changed for this module.

---

## Tests

`frontend/tests/unit/` — `report-form.test.tsx` (7 tests: `canSubmitReport()` pure-function bounds; blocks submission with neither photo nor location; submits with photo + geolocation, asserting the exact `FormData` keys including `lat`/`lon`; submits with photo only when geolocation is denied, asserting `lat`/`lon` are absent from the `FormData`), `subscription-manager.test.tsx` (3 tests: `matchesSubscription()` pure function; subscribe calls `api.citizenSubscribe` with the expected body shape; unsubscribe calls `api.citizenUnsubscribe` and excludes the removed entry), `citizen-storage.test.ts` (2 tests: `getOrCreateUserRef()` stability across calls; `addRecentReport()` cap-at-5-drop-oldest behavior).

`frontend/tests/e2e/citizen-report.spec.ts` — one Playwright spec using Playwright's `geolocation`/`permissions` context options (`test.use({ geolocation: {...}, permissions: ["geolocation"] })`) against the real production build + a real running backend: navigate to `/report`, share location, attach a minimal JPEG fixture (inline base64, no EXIF needed since geolocation supplies coordinates), submit, assert the confirmation panel and ICT quote render.

Full backend suite: 207 passed (no backend files changed by this module — confirmed as a true no-op regression check), the same 6 pre-existing `test_dashboard.py` failures excluded (unrelated, pre-existing prior to M16/M17/M18). Frontend unit suite: 33 passed (24 prior + this module's 9 new test cases across 3 files). `tsc --noEmit` clean.

A real environment issue was found and resolved during E2E verification, not a code bug: a stray `uvicorn` process from an earlier (failed) port-binding attempt was still listening on port 8100 without the test run's `GRID_CORS_ALLOW_ORIGINS` override, causing a genuine CORS failure on the first E2E attempt (`Access to fetch ... has been blocked by CORS policy`) that looked like an app bug until `lsof -i :8100` revealed the zombie process. Killed it and restarted cleanly; not a defect in the report/subscribe flow itself.

---

## Known limitations (MVP, deliberate scope reductions)

- `D-M18-01` — No `GET /citizen/nearby-hotspots` proxy/map context; the confirmation screen shows text-based ICT/corridor data only, no map pin rendering.
- `D-M18-02` — No server-side rate limiting (3 reports/hour/user_ref) — no primitive exists in this codebase; not invented here.
- `D-M18-03` — Subscriptions are corridor-name only, no raw H3-cell ("use current location") subscription — would require a client-side H3 library that isn't currently a dependency.
- `D-M18-04` — No PWA manifest / native browser push notifications — pre-alerts are in-tab `sonner` toasts only, requiring the tab to be open with an active WebSocket connection.
- No ASTraM deep link / push bridge (Phase 1.5, explicitly out of scope per spec).
- No commander-facing triage panel surfacing pending citizen reports on `/live` — `/analytics`'s placeholder still flags this as an open gap, separate from M18 itself.

---

## Next

- A real commander-side citizen-triage panel on `/live` or `/analytics`, replacing the current placeholder, wired to `POST /citizen/verify/{id}` / `POST /citizen/reject/{id}`.
- M12 (Advisory) remains the only unbuilt MVP-adjacent module aside from Phase 1.5/2 items.
- Phase 1.5/2: ASTraM push bridge, real PWA manifest/Service Worker, server-side rate limiting primitive, H3-cell-based subscriptions.
