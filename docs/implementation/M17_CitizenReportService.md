# M17 — CitizenReportService (Implementation Record)

**Version:** 1.0
**Backend path:** `backend/src/grid_unlocked/citizen/`
**Status:** Implemented (MVP — photo+GPS report, EXIF GPS fallback, H3/corridor snap, keyword cause-hint, M03 live ICT quote with corridor×cause prior fallback, commander verify/reject, polling-based pre-alert matcher)
**Spec reference:** [IMPLEMENTATION_MODULES.md § M17](../IMPLEMENTATION_MODULES.md)

---

## Purpose

Commuters encounter blockages before ASTraM logs them. M17 lets a citizen
submit a photo + GPS report and get an immediate ICT (incident clearance
time) quote from M03, while a commander retains verification control before
the event can enter M07 dispatch. It is the backend prerequisite for M18
(CitizenApp) and replaces the citizen-triage placeholder M15 shipped with.

---

## Gaps found while reading the existing codebase (not assumptions)

The spec's prose described several capabilities that didn't actually exist
yet. These were resolved as part of this module rather than discovered late:

- **No lat/lon → corridor spatial join existed anywhere.** M02's corridor
  graph (`features/constants.py`) is name-keyed only — no polygons or
  centroids. A new `corridor_centroids` table is seeded once from
  `data/astram_events.csv` (mean lat/lon per corridor), following the exact
  pattern of `features/priors_loader.py::seed_priors_from_csv()`.
- **`ImpactService.score(event_id)` requires the event to already exist**
  in `normalized_events` — there is no way to score a provisional, unsaved
  event. The submit flow therefore ingests first (via `IngestionService`,
  in-process, no HTTP hop), then scores.
- **Bug:** `unknown_obstruction` was a member of
  `ingestion/vocab.py::VALID_CAUSES` but missing from `CAUSE_ALIASES`, so
  `normalize_cause("unknown_obstruction")` raised. M17's own low-confidence
  default cause depends on this — fixed by adding the missing alias.
- **Bug:** `RecommendationService.build_card()` had no check on
  `NormalizedEvent.authenticated` at all — an unverified citizen event
  would have flowed straight into M07 dispatch. Added an
  `unauthenticated_hold` gate (see below).
- **No push events exist from M04/M05** ("cluster updated" / "ripple
  crossed H3 cell") for the spec's pre-alert matcher — both are pull-only
  (`get_observed()` / `get_active()`). Implemented as a 10s polling loop
  instead of new push instrumentation inside M04/M05 (explicit MVP
  simplification, confirmed with the user before implementation).
- **No object storage, no real auth, no rate-limiting existed anywhere.**
  Per explicit user decision: photos are stored as `LargeBinary` directly
  on the `citizen_reports` row (no S3, no local disk), and commander/citizen
  identity is a free-text id/role field — matching the rest of the
  codebase's existing "trust-the-body" convention (`commander_id` elsewhere
  has no token verification either). Rate-limiting was scoped out entirely
  for this MVP pass.

---

## Core behavior

### Location snap (`citizen/service.py::_resolve_location`)

Device `lat`/`lon` form fields are used if both present; otherwise
`citizen/exif.py::extract_gps_from_exif()` reads the photo's GPS IFD
(`0x8825`) via Pillow. If neither is available, the request fails with
`400`. Once resolved, `ingestion/validator.py::validate_bbox()` (reused, not
reimplemented) rejects coordinates outside the Bengaluru bbox.

### Spatial join (`citizen/geo.py::nearest_corridor`)

`h3_res7(lat, lon)` (reused from `hotspots/geo.py`) gives the H3 cell.
Corridor is the nearest seeded centroid by haversine distance (also reused
from `hotspots/geo.py::haversine_km`). Note: nearest-centroid does **not**
reliably recover a point's "true" corridor when corridor regions overlap or
aren't compact — verified directly against the CSV during testing. This is
accepted as an MVP approximation; the spec calls for "nearest corridor
polygon," and no polygon data exists to do better. `junction` is always
`null` — no junction-level geometry exists anywhere in the codebase.

### Cause hint (`citizen/cause_hint.py::infer_cause_hint`)

First-match-wins keyword regex over the optional `description` field:
`water|flood|logging` → `water_logging`, `accident|crash|collision` →
`accident`, `breakdown|broke down|stalled` → `vehicle_breakdown`,
`tree|fallen tree|branch` → `tree_fall`, `pothole|pot hole|crater` →
`pot_holes`. No match or no description → `unknown_obstruction` at low
confidence (0.2); a match scores 0.65. A unit test asserts every cause this
function can emit is a real `VALID_CAUSES` member — a regression guard
against the exact vocabulary-drift bug found above.

### ICT quote (`citizen/service.py::_quote_ict`)

If ingest succeeded, `ImpactService.score(event_id)` is tried first
(`ict_quote_source="m03_live"`). On any failure — ingest failed, or
`score()` raised — falls back to `FeatureService.get_prior(corridor, cause)`
(`ict_quote_source="corridor_prior_fallback"`). The fallback path only has a
single median ICT, not real quantiles, so `ict_p80 = ict_p50 * 1.6` is an
explicit MVP heuristic, not a modeled quantity.

### Triage forward and verification gate

`submit_report()` builds a `RawEventPayload`-shaped dict and calls
`IngestionService.ingest(..., source=IngestSource.CITIZEN)` directly
in-process — `ingestion/normalizer.py` already forced
`authenticated=False` for citizen-sourced events before this module existed.
`RecommendationService.build_card()` now reads that flag:

```python
unauthenticated_hold = mode in {COMPLETE, AUTO} and gov.tier != "3" and not row.authenticated
include_dispatch = mode in {COMPLETE, AUTO} and gov.tier != "3" and row.authenticated
```

An unauthenticated card renders fully (impact, propagation, hotspot
context — a commander still needs to see severity to decide) but
`dispatch` stays `None`, `dispatch_pending=True`, and
`provenance["dispatch"] = "awaiting_citizen_verification"` (distinct from
the pre-existing `"pending"` skeleton-mode string, so the dashboard can
tell the two states apart). `POST /citizen/verify/{report_id}` flips
`NormalizedEventRow.authenticated=True` and calls
`build_card(event_id, refresh=True)`, which now includes dispatch. A new
`ActionCard.source: str` field (defaulted to `"astram"` for backward
compatibility with existing cached cards) surfaces the originating event's
`source` so a verified citizen card is directly assertable as
`source == "citizen"` without a second API call.

`POST /citizen/reject/{report_id}` is audit-only — it updates the report's
own status and never touches the underlying event or any card.

### Pre-alert matcher (`citizen/service.py::check_pre_alerts`)

A background task (`main.py::_citizen_pre_alert_loop`, mirroring M14's
existing `_governance_probe_loop` structure exactly) runs every 10s. It
skips entirely if there are no active subscriptions, otherwise pulls
`HotspotService.get_observed()` (already cached, 300s TTL) and
`PropagationService.get_active()` and diffs their corridors/H3 cells against
`corridor_subscriptions` rows, publishing a `DashboardDelta(scope=CITIZEN)`
per match via the existing `dashboard_bus` (M15's in-process WS fanout,
reused rather than inventing a new channel).

### Photo handling (`citizen/exif.py`)

`strip_exif_except_gps()` re-encodes the uploaded image keeping only the
GPS IFD, dropping all other EXIF (camera make/model/serial, etc.) before
the bytes are stored — matches the spec's "strip EXIF PII except GPS"
requirement. Validated to round-trip correctly (GPS readable after
stripping) during implementation.

---

## API

| Endpoint | Behavior |
|---|---|
| `POST /citizen/report` | multipart: `photo`, `lat`/`lon` (optional), `description` (optional) → `CitizenReport` with snap, cause hint, ICT quote |
| `GET /citizen/report/{report_id}` | status + ICT quote snapshot |
| `POST /citizen/verify/{report_id}` | `{commander_id}` → promotes event, returns refreshed `ActionCard` with dispatch enabled |
| `POST /citizen/reject/{report_id}` | `{reason_code, commander_id?}` → audit only |
| `POST /citizen/subscribe` | `{user_ref, corridors[], h3_cells[]}` → subscription id |
| `DELETE /citizen/subscribe/{id}` | soft-delete (`active=false`) |
| `GET /citizen/photo/{report_id}` | streams the stored photo bytes |

---

## Storage

Three new tables (`backend/src/grid_unlocked/db/models.py`):

- `corridor_centroids` — `corridor` (PK), `lat`, `lon`, `sample_count`. Seeded once from `data/astram_events.csv` at startup (`citizen/centroid_seed.py`), gated by an idempotency check mirroring `features/priors_loader.py`.
- `citizen_reports` — snap result, cause hint + confidence, ICT quote snapshot, `photo_bytes` (`LargeBinary`), verification state. `corridors_json`/`h3_cells_json`-style list-as-text columns are not used here, but the table follows the same conventions as `FeatureSnapshotRow`/`ActionCardRow` elsewhere.
- `corridor_subscriptions` — `user_ref`, `corridors_json`, `h3_cells_json` (list-as-JSON-text, matching the existing convention — no array column type exists anywhere in this codebase), `active` (soft-delete flag).

---

## Source files

| File | Responsibility |
|---|---|
| `citizen/schemas.py` | `CitizenReport`, `CitizenReportStatus`, verify/reject/subscribe request-response models |
| `citizen/centroid_seed.py` | One-time corridor-centroid seeding from the ASTraM CSV |
| `citizen/geo.py` | `nearest_corridor()` — haversine-nearest centroid lookup |
| `citizen/cause_hint.py` | Keyword regex → 17-class cause vocabulary |
| `citizen/exif.py` | EXIF GPS extraction + PII-stripping (Pillow) |
| `citizen/repository.py` | DB access — reports, centroids, subscriptions, cross-module `NormalizedEventRow.authenticated` flip |
| `citizen/service.py` | `CitizenService` — submit/verify/reject/subscribe/pre-alert orchestration |
| `citizen/router.py` | `POST/GET /citizen/...` FastAPI routes |

Modified: `ingestion/vocab.py` (alias fix), `recommendations/schemas.py` (`ActionCard.source`), `recommendations/service.py` (authenticated gate), `dashboard/schemas.py` (`DeltaScope.CITIZEN`), `db/models.py` + `db/session.py` (new tables), `main.py` (router include + centroid seeding + pre-alert loop), `pyproject.toml` (`pillow`, `python-multipart` added as explicit dependencies — Pillow was previously only a transitive dependency via matplotlib, fragile to rely on for a load-bearing feature).

---

## Tests

`backend/tests/test_citizen.py` — 17 tests:

- Corridor snap / H3 cell consistency against an independently-built centroid table (not hardcoded labels — verified during implementation that nearest-centroid does not always recover a CSV row's own corridor, so the test asserts internal consistency between the seeded table and `nearest_corridor()`, not "row corridor == own centroid").
- Missing GPS + missing EXIF → 400; EXIF-only fallback path; outside-bbox → 400.
- ICT quote present in the same response as submission (no follow-up poll needed).
- Unverified citizen event: `dispatch is None`, `dispatch_pending is True`, `provenance.dispatch == "awaiting_citizen_verification"`, `source == "citizen"`.
- Verify promotes the event and enables dispatch; reject is audit-only and leaves the event unauthenticated.
- Photo size/type validation.
- Subscribe/unsubscribe round-trip, including the "must provide corridors or h3_cells" 400 and idempotent double-unsubscribe → 404.
- Pre-alert matcher fires via `check_pre_alerts()` directly (not the real 10s loop, for test speed) against a synthetically clustered set of ingested events.
- **Regression** — `unknown_obstruction` passes `normalize_cause()` without raising; every cause `infer_cause_hint()` can emit is a real `VALID_CAUSES` member.
- **Regression** — `build_card()`'s authenticated gate, isolated from the citizen flow entirely (ingested directly via `/ingest/astram` with `authenticated=false`) — confirms the fix is general, not citizen-specific.
- Corridor-centroid seeding idempotency.

A genuine bug was found and fixed during implementation, before any test
was written against it: a duplicate index declaration
(`h3_cell: Mapped[str] = mapped_column(..., index=True)` *and* an explicit
`Index("ix_citizen_reports_h3_cell", "h3_cell")` in `__table_args__` with
the same auto-generated name) broke `init_db()` — harmless on a single
`create_all()` call, but `test_ingestion.py`'s fixture calls `init_db()`
twice (once via the autouse fixture, once directly), and the second
`CREATE INDEX` collided. This silently broke a pre-existing, previously
green test file the moment the new table was added — caught by running the
full suite before considering the module done, not just the new test file.

Full backend suite: 194 passed (181 pre-existing + this module's 17, minus
the 6 `test_dashboard.py` failures already present on `master` before this
module, unrelated to M17 — reproduced identically on an unmodified
checkout).

---

## Known limitations (MVP, deliberate scope reductions)

- `D-M17-01` — Photo storage is a DB `LargeBinary` column, not
  S3-compatible object storage per the spec's literal wording. Decided
  explicitly with the user rather than building a local-disk or real S3
  stand-in.
- `D-M17-02` — No real authentication. Commander/citizen identity is a
  free-text field with no token verification, consistent with every other
  "commander_id" usage in this codebase (M09/M14 have the same property).
- `D-M17-03` — Pre-alert matching is a 10s polling loop against M05/M04's
  existing pull-only state, not a true push hook fired the instant a
  cluster or ripple changes. Confirmed with the user as the right tradeoff
  to avoid modifying M04/M05 internals for this module.
- `D-M17-04` — Corridor snap is nearest-centroid, not nearest-polygon — no
  corridor boundary geometry exists anywhere in this codebase or the source
  CSV. Accuracy is bounded by how compact/non-overlapping real corridor
  regions are.
- `D-M17-05` — ICT p80 in the fallback (non-M03) path is a fixed `p50 ×
  1.6` heuristic — the corridor×cause prior table only stores a median, not
  quantiles.
- Rate limiting (a soft M14 dependency in the spec) is entirely out of
  scope for this MVP pass — no primitive exists anywhere in the codebase to
  build on, and the spec didn't give detailed requirements to scope it
  properly.
- Junction is always `null` — no junction-level geometry exists anywhere.

---

## Next

- **M18** CitizenApp — frontend route group consuming the endpoints built
  here (`/citizen/report`, `/citizen/report/{id}`, `/citizen/subscribe`).
  Replaces M15's `/analytics` citizen-triage placeholder.
- **M16** FieldOfficerApp — independent of M17, can proceed in either order.
- Phase 2: vision-only geolocation when GPS/EXIF are both absent; real
  S3-compatible photo storage; push-based (not polling) pre-alert triggers
  once M04/M05 grow their own event hooks for other reasons.
