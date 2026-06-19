# Grid Unlocked — Tech Stack & Infrastructure

**Version:** 1.0 · June 2026  
**Scope:** Local dev (Docker) vs production target (documented, not implemented yet)

---

## Overview

| Layer | Technology | Status |
|---|---|---|
| API | **FastAPI** + **Uvicorn** | Implemented (M01) |
| Language | **Python 3.12** | Implemented |
| Package manager | **uv** | Implemented |
| Primary DB | **PostgreSQL 16 + PostGIS** | Docker dev · prod target |
| Cache / pub-sub | **Redis 7** | Docker dev · prod target |
| Local-only fallback | **SQLite** (aiosqlite) | Bare-metal dev + unit tests |
| ML — classification | **LightGBM** | Planned (M03) |
| ML — survival | **lifelines** (Cox PH) | Planned (M03) |
| ML — clustering | **scikit-learn** (DBSCAN) | Planned (M05) |
| Graph | **NetworkX** + OSM extract | Planned (M02/M04) |
| Geospatial | **H3**, **PostGIS** | Planned (M02/M05) |
| Optimization | **OR-Tools** (MILP) | Planned (M07) |
| Model registry | **MLflow** | Planned (M13) |
| Event bus (async) | **Redis Streams** | Phase 1.5 (in-process bus in MVP) |
| Frontend | **React / Next.js** + MapLibre | Planned (M15/M16/M18) |
| Containers | **Docker** + **Compose** | Local dev |

---

## Databases & Stores

### PostgreSQL + PostGIS (primary)

**Used by:** M01 events, M02 priors/graph, M13 training manifests, audit logs

| Data | Table / object | Module |
|---|---|---|
| Normalized incidents | `normalized_events` | M01 |
| Ingest dead letters | `ingest_rejects` | M01 |
| Corridor×cause priors | `corridor_cause_priors` | M02 |
| OSM graph edges | `osm_graph_edges` | M02 |
| Feature snapshots (offline) | `feature_snapshots` | M02, M13 |
| Model promotion audit | `model_registry` | M13 |

PostGIS enables zone polygon joins, H3-adjacent spatial queries, and junction snapping.

### Redis (hot path)

**Used by:** M02 feature cache, M05 active-event geo index, M15 WebSocket fanout (Phase 1.5)

| Key pattern | TTL | Purpose |
|---|---|---|
| `feature:{event_id}` | 24 h | Materialized FeatureVector |
| `centrality:{node_id}` | 30 d | OSM betweenness cache |
| `active_events:geo` | — | GEO index for 2 km simultaneous count |
| `governance:tier` | 1 h | Tier 1/2/3 cache |

### SQLite (dev / tests only)

Default when running `uv run` without Docker. Unit tests use in-memory SQLite. **Not for production.**

---

## Backend Python Dependencies

### Installed now

```
fastapi, uvicorn, pydantic, pydantic-settings
sqlalchemy, aiosqlite, asyncpg
python-dateutil, httpx
```

### Adding with M02–M07 (ML phase)

```
lightgbm, lifelines, scikit-learn, h3, networkx, redis, ortools, mlflow, pandas, numpy
```

Install when implementing each module to keep the base image lean during M01.

---

## Communication Patterns

| Pattern | Dev (Docker) | Production (target) |
|---|---|---|
| Sync REST | FastAPI routes | Same + API gateway |
| Async events | In-process bus (MVP) | Redis Streams → Kafka (scale) |
| Live UI | WebSocket (M15) | WebSocket + CDN |
| ML batch | Local / MLflow | MLflow on object storage |

---

## Local Dev — Docker Compose

```
┌─────────────────────────────────────────────────────────┐
│  docker compose (localhost)                              │
│                                                          │
│  ┌──────────┐   ┌──────────┐   ┌──────────────────┐  │
│  │ postgres │   │  redis   │   │  api (FastAPI)   │  │
│  │ + PostGIS│   │   :6379  │   │  :8000           │  │
│  │  :5432   │   └────┬─────┘   └────────┬─────────┘  │
│  └────┬─────┘        │                  │             │
│       └──────────────┴──────────────────┘             │
└─────────────────────────────────────────────────────────┘
```

```bash
# From repo root
docker compose up --build
# API: http://localhost:8000/docs
# Postgres: localhost:5432  (grid / grid / grid_unlocked)
# Redis: localhost:6379
```

Environment variables: see `.env.example`.

---

## Production (target — not implemented)

| Component | Dev | Production (planned) |
|---|---|---|
| Postgres | Single Compose container | Managed RDS / Cloud SQL + PostGIS |
| Redis | Single Compose container | ElastiCache / Memorystore |
| API | 1 container, `--reload` | K8s / ECS, multiple replicas, no reload |
| Secrets | `.env` file | Vault / SSM / K8s secrets |
| ML models | Local filesystem | S3 + MLflow registry |
| Event bus | In-process | Redis Streams or Kafka |
| TLS | None | Terminated at load balancer |
| ASTraM webhook | CSV replay | Signed production webhook |

Production Dockerfile will drop `--reload`, use multi-stage build, non-root user, and health checks only.

---

## External Integrations (by phase)

| System | Phase | Protocol |
|---|---|---|
| ASTraM incidents | MVP (CSV replay) → 1.5 (webhook) | REST webhook |
| OSM road graph | M02 | Static file / quarterly ETL |
| Police station APIs | 1.5 (M10) | REST |
| VMS / LED boards | 1.5 (M11) | Webhook |
| BMTC GTFS-RT | 2 (M12) | GTFS-RT feed |
| ASTraM citizen push | 1.5 (M18) | Push bridge |

---

## What you need installed locally

### Option A — Docker (recommended)

- Docker Engine 24+
- Docker Compose v2

### Option B — Bare metal

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Optional: local Postgres 16 + Redis 7 if not using SQLite

---

## Related docs

- [ARCHITECTURE.md](ARCHITECTURE.md) — module layers and data flow
- [IMPLEMENTATION_MODULES.md](IMPLEMENTATION_MODULES.md) — per-module contracts
- [ML_MODELS_PRD.md](ML_MODELS_PRD.md) — ML stack details
