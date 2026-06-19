# M01 — IngestionGateway (Implementation Record)

**Version:** 0.1  
**Backend path:** `backend/src/grid_unlocked/ingestion/`  
**Status:** Implemented (MVP)  
**Spec reference:** [IMPLEMENTATION_MODULES.md § M01](../IMPLEMENTATION_MODULES.md)

---

## Purpose

M01 is the single ingress point for all incident feeds. It validates raw payloads, normalizes them into a canonical `NormalizedEvent`, persists them, and publishes domain events for downstream modules (M02, M13).

ASTraM remains the system-of-record. M01 mirrors events; it does not replace ASTraM.

---

## What is implemented

### API endpoints


| Method | Path                 | Description                                            |
| ------ | -------------------- | ------------------------------------------------------ |
| POST   | `/ingest/astram`     | ASTraM webhook / CSV replay payloads                   |
| POST   | `/ingest/planned`    | Planned event portal (forces `event_type=planned`)     |
| POST   | `/ingest/field`      | Field officer BOT supplemental reports                 |
| POST   | `/ingest/citizen`    | Citizen triage from M17 (`authenticated=false`)        |
| GET    | `/events/{event_id}` | Fetch normalized event by ID                           |
| GET    | `/health/ingest`    | Ingest metrics (counts, error rate, reporting lag P95) |


### Event bus (in-process)


| Event             | Trigger                        | Consumers                       |
| ----------------- | ------------------------------ | ------------------------------- |
| `EventNormalized` | Successful validation + upsert | M02 (feature materialization)   |
| `EventClosed`     | Status transitions to `closed` | M13 (future), M02 cache cleanup |


Published via `ingestion/bus.py` — in-process pub/sub until Redis Streams in Phase 1.5.

### Normalization pipeline

```
Raw payload → validator → normalizer → repository.upsert → event_bus.publish
                    ↓ (on failure)
              ingest_rejects (dead letter)
```

### Validation rules


| Rule             | Implementation                                                                    |
| ---------------- | --------------------------------------------------------------------------------- |
| Required fields  | `latitude`, `longitude`, `event_cause`, `start_datetime`                          |
| Bengaluru bbox   | lat 12.8–13.3, lon 77.3–77.8 (reject if outside)                                  |
| Cause vocabulary | 17 canonical classes via `vocab.py` + `CAUSE_ALIASES`                             |
| Drop `test_demo` | Dead-letter, never published downstream                                           |
| Corridor         | Accepted if in 22-corridor list; invalid/null allowed (stored as null)            |
| Reporting lag    | `created_date - start_datetime` → `reporting_lag_minutes`                         |
| Anomaly flags    | `coordinates_outside_bbox`, `closed_before_start`, `planned_duration_exceeds_72h` |


### Source-specific behavior


| Source           | `authenticated` default | Notes                               |
| ---------------- | ----------------------- | ----------------------------------- |
| `astram`         | From payload            | Standard path                       |
| `planned_portal` | From payload            | `event_type` defaulted to `planned` |
| `field`          | From payload            | Same normalization as ASTraM        |
| `citizen`        | **Always `false`**      | Until commander verifies via M17    |


### Idempotent upsert

Duplicate `event_id` deliveries update the existing row (no duplicate records). Closed-status transitions emit `EventClosed`.

---

## Source files


| File            | Responsibility                                       |
| --------------- | ---------------------------------------------------- |
| `router.py`     | FastAPI routes                                       |
| `service.py`    | Orchestration, latency tracking, event publishing    |
| `normalizer.py` | Raw → `NormalizedEvent`, CSV row mapping             |
| `validator.py`  | Bbox, cause, datetime parsing, anomaly detection     |
| `repository.py` | SQLAlchemy upsert, dead-letter, health stats         |
| `schemas.py`    | Pydantic models (`NormalizedEvent`, `IngestAck`, …)  |
| `vocab.py`      | 17 causes, 22 corridors, source enums                |
| `bus.py`        | In-process event bus                                 |
| `csv_replay.py` | Demo: replay `data/astram_events.csv` through ingest |


---

## Database tables


| Table               | Purpose                                                         |
| ------------------- | --------------------------------------------------------------- |
| `normalized_events` | Primary event store (indexed: corridor, status, start_datetime) |
| `ingest_rejects`    | Dead-letter queue with raw payload + violation reason           |


**Engine:** PostgreSQL + PostGIS in Docker; SQLite for bare-metal dev and unit tests.

---

## Scripts & demo

```bash
# Replay 100 rows from ASTraM CSV
cd backend && uv run python scripts/replay_csv.py
```

CSV path: `data/astram_events.csv` (config: `GRID_ASTRAM_CSV_PATH`).

---

## Tests (9)

File: `backend/tests/test_ingestion.py`


| Test                             | Verifies                                      |
| -------------------------------- | --------------------------------------------- |
| `test_ingest_astram_success`     | Happy-path ingest ACK                         |
| `test_get_event_after_ingest`    | GET /events/{id}                              |
| `test_bbox_rejection`            | Out-of-city coordinates → 422                 |
| `test_test_demo_dropped`         | test_demo cause → 422                         |
| `test_idempotent_upsert`         | Duplicate delivery updates status             |
| `test_citizen_unauthenticated`   | Citizen source forces `authenticated=false`   |
| `test_health_endpoint`           | /health/ingest metrics                        |
| `test_cause_alias_normalization` | `Fog / Low Visibility` → `fog_low_visibility` |
| `test_reporting_lag_computed`    | reporting_lag_minutes populated               |


---

## Deferred (not yet implemented)

Items from the full M01 spec in `IMPLEMENTATION_MODULES.md` that are **not** in the current codebase:


| Capability                                                      | Planned phase |
| --------------------------------------------------------------- | ------------- |
| BBMP zone polygon imputation when `zone` is null                | Phase 1.5     |
| OSM junction reverse-geocode when `junction` is null            | Phase 1.5     |
| `active_events` materialized view                               | Phase 1.5     |
| Webhook signature verification                                  | Phase 1.5     |
| Rate limiting on ingest endpoints                               | Phase 1.5     |
| Tier 2/3 degradation behavior (ASTraM-only, read-only snapshot) | Phase 1.5     |


---

## Configuration


| Env var                | Default                           | Purpose               |
| ---------------------- | --------------------------------- | --------------------- |
| `GRID_DATABASE_URL`    | SQLite local / Postgres in Docker | Event persistence     |
| `GRID_ASTRAM_CSV_PATH` | `data/astram_events.csv`          | CSV replay source     |
| `GRID_BBOX_`*          | Bengaluru bounds                  | Geographic validation |


---

## Integration points

```
External feeds ──► M01 ──► normalized_events (DB)
                    │
                    ├── EventNormalized ──► M02 FeatureGraphService
                    └── EventClosed     ──► M13 ReplayLearning (future)
```

**Next consumer:** M02 subscribes to `EventNormalized` and materializes features automatically.