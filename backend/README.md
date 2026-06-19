# Grid Unlocked — Backend

Python API for Grid Unlocked (M01 IngestionGateway and downstream modules).

## Setup

### Docker (recommended — Postgres + Redis)

From repo root:

```bash
docker compose up --build
```

### Bare metal (SQLite)

```bash
cd backend
uv sync
```

## Run API

```bash
uv run uvicorn grid_unlocked.main:app --reload
```

Open http://localhost:8000/docs for Swagger UI.

## Endpoints (M01 + M02)

| Method | Path | Module |
|---|---|---|
| POST | `/ingest/astram` | M01 |
| GET | `/events/{event_id}` | M01 |
| GET | `/health/ingest` | M01 |
| GET | `/features/{event_id}` | M02 |
| POST | `/features/batch` | M02 |
| GET | `/priors/corridor-cause/{corridor}/{cause}` | M02 |
| GET | `/graph/centrality/{node_id}` | M02 |
| GET | `/graph/neighbors/{node_id}` | M02 |

## CSV replay (demo)

```bash
uv run python scripts/replay_csv.py
```

## Tests

```bash
uv run pytest
```

## Project layout

```
backend/
├── src/grid_unlocked/
│   ├── main.py              # FastAPI app
│   ├── config.py
│   ├── db/                  # SQLAlchemy models + session
│   ├── ingestion/           # M01 IngestionGateway
│   └── features/            # M02 FeatureGraphService
│       ├── router.py        # API routes
│       ├── service.py       # Orchestration
│       ├── normalizer.py    # ASTraM → NormalizedEvent
│       ├── validator.py     # Bbox, schema, anomalies
│       ├── repository.py    # SQLite persistence
│       └── bus.py             # In-process EventNormalized pub/sub
├── tests/
└── scripts/
```
