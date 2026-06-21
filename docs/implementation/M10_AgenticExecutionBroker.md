# M10 — AgenticExecutionBroker (Implementation Record)

**Version:** 1.0
**Backend path:** `backend/src/grid_unlocked/execution/`
**Status:** Implemented (MVP, stubbed station APIs per spec)
**Spec reference:** [IMPLEMENTATION_MODULES.md § M10](../IMPLEMENTATION_MODULES.md)

---

## Purpose

M10 is the **post-approval actuation layer**. It consumes M09 `approve()` events and
fires dispatch + barricade-reservation commands at police station APIs (mocked in the
hackathon phase) asynchronously, with a full immutable audit trail, idempotency,
retry/backoff, and a dead-letter queue. It never generates recommendations — that is
M09/M07's job — and never talks to VMS boards (M11).

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/execute/dispatch` | Internal — triggered by M09 `approve()` when `shadow_mode=false` |
| GET | `/execute/status/{execution_id}` | Current status machine state + audit history |
| POST | `/execute/retry/{execution_id}` | Admin manual retry for `DEAD_LETTER` / `FAILED` |
| GET | `/execute/audit?event_id=&card_id=` | Immutable audit query |
| POST | `/mock/station/ack` | Hackathon demo endpoint — fake station ACK payload |

---

## Core behavior

### Enqueue (`enqueue_dispatch`)

1. **Shadow gate** — `shadow_mode=true` → 403. `tier="3"` → 503 (manual SOP).
2. **Idempotency** — lookup existing `execution_queue` row by `approval_token`; if
   found, return the same `execution_id` (double-approve → single execution).
3. Create a persistent `execution_queue` row (`status=pending`) **before** enqueueing,
   so the audit trail survives a worker crash.
4. Fire-and-forget enqueue onto the in-process `asyncio.Queue` — caller returns
   immediately. Measured P95 well under the 200 ms contract (test asserts < 200 ms).

### Background worker (`_process_command`)

- Pulls one `QueuedCommand` at a time from the singleton `CommandQueue`.
- Up to 3 attempts, exponential backoff `[2s, 4s, 8s]`.
- Every attempt appends one immutable `execution_audit` row (request payload, response
  code/body, outcome) regardless of success/failure.
- Success → `status=acknowledged`. Final failed attempt → `status=dead_letter`.
  Intermediate failures → `status=retrying` with `next_retry_at`.
- Two command kinds are modeled: `dispatch` (calls `MockStationClient.dispatch_unit`)
  and `barricade` (calls `MockStationClient.reserve_barricades`).

### Manual retry

- Only `DEAD_LETTER` / `FAILED` executions can be retried (409 otherwise).
- Resets `attempt_count=0`, re-enqueues with the same `execution_id`.

---

## Status machine

`pending → processing → acknowledged`
`pending → processing → failed → retrying → processing → … → dead_letter`

---

## Integration

| Module | Usage |
|---|---|
| M09 | `approve()` builds `ExecuteDispatchRequest` from the `ActionCard` (`dispatch.assignments[0].station_id`, `planned.barricade_count`) and calls `M10ExecutionService.enqueue_dispatch()` directly (in-process call, not HTTP) |
| M14 (stub) | Shadow mode + tier gate via `get_governance()` |
| M06 | Barricade count sourced from `PlannedEventPackage.barricade_count` |
| Station APIs (Phase 1.5) | `MockStationClient` stands in for `StationHttpClient` |

---

## Source files

| File | Responsibility |
|---|---|
| `schemas.py` | `ExecuteDispatchRequest`, status enum, audit/response contracts |
| `queue.py` | `CommandQueue` — singleton `asyncio.Queue` + background worker |
| `station_client.py` | `MockStationClient` — simulated station dispatch + barricade reservation |
| `repository.py` | `execution_queue` / `execution_audit` persistence (audit rows are insert-only) |
| `service.py` | `ExecutionService` — enqueue/status/retry/audit; `_process_command` retry/DLQ state machine |
| `router.py` | FastAPI routes + `/mock/station/ack` demo endpoint |

---

## Database

### `execution_queue` (mutable state machine)

| Column | Notes |
|---|---|
| `execution_id` | PK (`EXEC-…`) |
| `approval_token` | Indexed — idempotency key |
| `card_id`, `event_id` | Indexed |
| `command_type` | `dispatch` \| `barricade` |
| `status` | `pending` / `processing` / `acknowledged` / `failed` / `retrying` / `dead_letter` |
| `attempt_count`, `next_retry_at` | |

### `execution_audit` (immutable, insert-only — 7y retention per spec)

| Column | Notes |
|---|---|
| `id` | PK autoincrement |
| `execution_id`, `approval_token`, `card_id`, `event_id` | Indexed |
| `attempt_number`, `station_id` | |
| `request_payload`, `response_code`, `response_body` | Raw JSON strings |
| `outcome` | `acknowledged` / `failed` / `dead_letter` |
| `error_detail`, `executed_at` | |

---

## Tests

| File | Count | Coverage |
|---|---|---|
| `test_execution.py` | 13 | Shadow block, idempotent double-approve, DLQ after 3 failures, audit completeness, enqueue latency < 200 ms, retry-then-succeed, audit response shape, mock ack endpoint, 404 on unknown id, **barricade command enqueues + executes independently of dispatch**, **barricade_count=0 enqueues no barricade command**, **manual retry after DLQ reaches acknowledged**, **retry on non-DLQ execution returns 409** |
| `test_integration.py` | +1 | M09 → M10 end-to-end: approve with `shadow_mode=false` enqueues dispatch, station ACK reflected in `/execute/status` |

---

## Known limitations (MVP, all explicitly deferred to Phase 1.5 per spec)

- `D-M10-01` — `MockStationClient` stands in for real BTP station HTTP API (auth, cert pinning).
- `D-M10-02` — Barricade reservation hits the mock client only; no real BTP asset API.
- `D-M10-03` — Queue transport is an in-process `asyncio.Queue`, not durable across restarts (Redis Streams in Phase 1.5).
- `D-M10-04` — Dead-letter executions are persisted but do not page an on-call channel (no PagerDuty/Slack hook yet).
- `D-M10-05` — No M16 WebSocket push on station ACK; status must be polled via `GET /execute/status/{id}`.

---

## Fixed during M10 completion pass

- **Barricade reservation was previously dead code.** `enqueue_dispatch` always created
  a `command_type=dispatch` row even when `barricade_count > 0`, so
  `MockStationClient.reserve_barricades()` was never invoked or audited. M09's
  `approve()` now enqueues a second `barricade` command when the planned package
  specifies `barricade_count > 0`, each with its own `execution_id`, audit trail, and
  independent retry/DLQ lifecycle.

---

## Next

- **M11** VMSRouter — push approved diversions to LED/VMS boards (same retry/DLQ shape as M10).
- **Phase 1.5** — swap `MockStationClient` for real station HTTP integration once
  post-approval command reliability thresholds are met (promotion gate per spec).
