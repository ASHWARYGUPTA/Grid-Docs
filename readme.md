# Grid Unlocked

Intelligent event-driven traffic management layer for ASTraM (Bengaluru Traffic Police).

## Repository layout

```
Grid Unlocked/
├── docs/               # PRD, architecture, tech stack, EDA
├── backend/            # Python API (uv) — M01+ modules
├── data/               # ASTraM corpus (astram_events.csv)
├── Dockerfile          # API container
├── docker-compose.yml  # Local dev: Postgres + Redis + API
└── readme.md
```

## Tech stack (summary)

| Component | Local dev (Docker) | Production (planned) |
|---|---|---|
| API | FastAPI + Uvicorn | Same, behind load balancer |
| Database | PostgreSQL 16 + PostGIS | Managed Postgres + PostGIS |
| Cache | Redis 7 | ElastiCache / Memorystore |
| ML | LightGBM, lifelines, scikit-learn | MLflow + object storage |
| Optimization | OR-Tools | Same |
| Package mgr | uv | uv in container |

Full details: [docs/TECH_STACK.md](docs/TECH_STACK.md)

## Run locally with Docker (recommended)

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| API + Swagger | http://localhost:8000/docs |
| Health | http://localhost:8000/health |
| Ingest metrics | http://localhost:8000/health/ingest |
| Postgres | `localhost:5432` — user `grid` / pass `grid` / db `grid_unlocked` |
| Redis | `localhost:6379` |

Copy `.env.example` to `.env` if running the API outside Docker.

## Run without Docker (SQLite)

```bash
cd backend
uv sync
uv run uvicorn grid_unlocked.main:app --reload
```

Uses SQLite by default; Redis optional until M02.

## Documentation

| Document | Description |
|---|---|
| [docs/TECH_STACK.md](docs/TECH_STACK.md) | Stack, databases, dev vs prod |
| [docs/implementation/](docs/implementation/) | **Built modules** — M01, M02 implementation records + audit |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design |
| [docs/PRD_Event_Driven_Traffic.md](docs/PRD_Event_Driven_Traffic.md) | Product requirements |
| [docs/IMPLEMENTATION_MODULES.md](docs/IMPLEMENTATION_MODULES.md) | Module contracts |

## Hackathon scope

Real-time hotspots, predicted hotspots, auto station assignment, diversion detection, AI recommendations, citizen reporting, and post-event learning — as an intelligence layer on ASTraM.
