# M11 — VMSRouter (Implementation Record)

**Version:** 1.0
**Backend path:** `backend/src/grid_unlocked/vms/`
**Status:** Implemented (MVP, stubbed webhook vendor per spec)
**Spec reference:** [IMPLEMENTATION_MODULES.md § M11](../IMPLEMENTATION_MODULES.md)

---

## Purpose

M11 converts M08 diversion routes into board-friendly LED/VMS text and fans the
message out to all boards mapped to the affected corridor — asynchronously, with
delivery confirmation, retry/backoff, and a dead-letter queue per board. It never
computes diversions (M08's job) and never talks to police stations (M10).

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/vms/push` | Internal — triggered by M09 `approve()` when `shadow_mode=false` and the card has diversion routes |
| GET | `/vms/status/{delivery_id}` | Current per-board delivery state |
| POST | `/vms/retry/{delivery_id}` | Admin manual retry for `DEAD_LETTER` / `FAILED` |
| POST | `/mock/vms/receive` | Hackathon demo endpoint — captures payload, returns fake vendor ACK |

---

## Core behavior

### Board resolution (`board_registry.get_boards_for_corridor`)

- Corridor string → list of `VmsBoard` via a hardcoded keyword map
  (`ORR East 1/2`, `Whitefield`, `Koramangala`, `Sarjapur`, `HSR`, `Banashankari`).
- Unmapped/unknown corridor falls back to two default boards rather than 422,
  so a push never silently fails just because a corridor string didn't match.
- `D-M11-03` — Phase 1.5 swaps this for a real `vms_board_registry` DB table.
- `D-M11-04` — commander-specified `board_ids` override is deferred; MVP always
  derives boards from corridor.

### Template rendering (`templates.render_from_route`)

- 3-line format: `DIVERSION ALERT` / `USE ALT: <abbreviated route>` /
  `+Xmin | <CAPACITY> CAPACITY`.
- Bengaluru road-name abbreviations (`Outer Ring Road` → `ORR`, etc.) keep line 2
  short; hard truncation safety net keeps the inline (`" | "`-joined) text ≤120 chars.
- Falls back to a generic `DIVERSION ALERT / SEE ALTERNATE ROUTE / FOLLOW SIGNS`
  message when `routes=[]` (M08 found no scenarios) instead of erroring.
- `D-M11-02` — Kannada/English bilingual rendering deferred to Phase 1.5.

### Push (`VmsService.push`)

1. **Shadow gate** — `shadow_mode=true` → 403.
2. **Idempotency** — lookup existing `vms_deliveries` rows by `push_id`; if found,
   return the same delivery set (double-approve → no duplicate fanout).
3. Resolve boards for `corridor`, render board text once from the top-ranked route.
4. Create one `vms_deliveries` row per board, then launch one
   `asyncio.create_task` per board (`_deliver_to_board`) — true parallel fanout,
   not sequential.
5. Return the initial (`pending`) delivery list immediately — P95 well under the
   500 ms contract (test asserts < 500 ms; confirmation is async).

### Per-board delivery worker (`_deliver_to_board`)

- Up to 3 attempts, exponential backoff `[1s, 2s, 4s]`.
- Success (`HTTP 200`) → `status=delivered`, stores vendor `ack_id`.
- Final failed attempt → `status=dead_letter` (`dead_letter=true`).
  Intermediate failures → `status=retrying`.
- Each board's delivery is independent — one board's DLQ does not block or retry
  others in the same push.

### Manual retry

- Only `DEAD_LETTER` / `FAILED` deliveries can be retried (409 otherwise).
- Resets `retry_count=0`, `dead_letter=false`, relaunches the same delivery task.

---

## Status machine

`pending → processing → delivered`
`pending → processing → retrying → processing → … → dead_letter`

---

## Integration

| Module | Usage |
|---|---|
| M09 | `approve()` — when `shadow_mode=false` and `card.diversions` is non-empty, builds `VmsPushRequest` (routes serialized from `ActionCard.diversions`, corridor read from the normalized event row via `FeatureService.repo.get_event_row`) and calls `M11VmsService.push()` directly (in-process call, same pattern as M10) |
| M08 | Diversion routes (`DiversionRoute.model_dump()`) are the only route source — M11 never recomputes them |
| M14 (stub) | Shadow mode gate via `get_governance()` |
| Webhook vendor (Phase 1.5) | `MockWebhookClient` stands in for the real VMS board vendor HTTP API |

M10 and M11 fire independently and in parallel off the same `approve()` call — a
failure in one is non-fatal to the other (each wrapped in its own `try/except` in
`recommendations/service.py`).

---

## Source files

| File | Responsibility |
|---|---|
| `schemas.py` | `VmsPushRequest`, status enum, delivery/response contracts |
| `board_registry.py` | Corridor → `VmsBoard` list (hardcoded MVP inventory) |
| `templates.py` | Route → ≤120 char, ≤3 line board text |
| `mock_webhook.py` | `MockWebhookClient` — simulated VMS vendor webhook receiver |
| `repository.py` | `vms_deliveries` persistence |
| `service.py` | `VmsService` — push/status/retry; `_deliver_to_board` retry/DLQ state machine |
| `router.py` | FastAPI routes + `/mock/vms/receive` demo endpoint |

---

## Database

### `vms_deliveries`

| Column | Notes |
|---|---|
| `delivery_id` | PK (`VDEL-…`) |
| `push_id` | Indexed — idempotency key (typically the M09 approval token) |
| `event_id`, `card_id` | Indexed |
| `board_id`, `board_name`, `board_text` | Rendered per-board payload |
| `status` | `pending` / `processing` / `delivered` / `failed` / `retrying` / `dead_letter` |
| `retry_count`, `dead_letter` | |
| `ack_id`, `response_code`, `error_detail` | Vendor response capture |
| `created_at`, `updated_at` | |

Composite index `(push_id, status)` for fast "how is this push doing" queries.

---

## Tests

| File | Count | Coverage |
|---|---|---|
| `test_vms.py` | 13 | Shadow block, idempotent double-push, DLQ after 3 failures, all-corridor-boards targeted, fanout latency < 500 ms, retry-then-deliver, manual retry after DLQ, 409 on non-DLQ retry, board text ≤120 chars/≤3 lines, empty-routes fallback text, mock receive endpoint, 404 on unknown delivery, unmapped-corridor fallback |
| `test_integration.py` | +1 | M09 → M11 end-to-end: approve on an unplanned incident with M08 diversions, `shadow_mode=false`, fans out and each board reaches `delivered` with an `ack_id` |

---

## Known limitations (MVP, all explicitly deferred to Phase 1.5 per spec)

- `D-M11-01` — `MockWebhookClient` stands in for the real VMS board vendor HTTP API.
- `D-M11-02` — English-only board text; Kannada bilingual templates not yet built.
- `D-M11-03` — Board registry is a hardcoded Python dict, not a DB-backed `vms_board_registry` table.
- `D-M11-04` — No commander-specified `board_ids` override in the approve request; boards are always corridor-derived.
- `D-M11-06` — M11 push fires in parallel with M10 dispatch on approval, not sequentially gated on M10 ACK.
- `D-M11-07` — No per-board delivery latency metrics surfaced to an M14 health dashboard (M14 does not exist yet).

---

## Completed during this pass

`schemas.py`, `board_registry.py`, `templates.py`, `repository.py`, `service.py`,
and `mock_webhook.py` already existed but were **never reachable** — there was no
`router.py`, no `main.py` registration, and M09's `approve()` only ever called M10.
This pass added:

- `router.py` — the four public endpoints (`/vms/push`, `/vms/status/{id}`,
  `/vms/retry/{id}`, `/mock/vms/receive`).
- `main.py` wiring — both routers registered, app description bumped to M01–M11.
- M09 `approve()` integration — fires `M11VmsService.push()` whenever the
  approved card has non-empty `diversions`, independent of and non-fatal to M10.
- `MockWebhookClient.with_failure_rate()` helper for test symmetry with M10's
  `MockStationClient`.
- The full `test_vms.py` suite (13 tests) plus one M09→M11 integration test —
  previously there were zero tests for this module.

---

## Next

- **Phase 1.5** — swap `MockWebhookClient` for real VMS vendor HTTP integration
  and `board_registry` for a DB-backed table, once M10's post-approval reliability
  promotion gate is met (M10 and M11 share the same promotion criteria per spec).
- **M14** GovernanceConsole — replace the config stub with a live tier/shadow API
  and surface M10/M11 delivery health.
- **M15/M16** — push delivery status to the command dashboard / field packet
  instead of requiring `GET /vms/status/{id}` polling.
