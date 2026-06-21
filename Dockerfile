# Grid Unlocked — local dev API image (production Dockerfile will differ)
FROM python:3.12-slim-bookworm

WORKDIR /app/backend

# LightGBM / OR-Tools runtime libs (needed when ML deps are added)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Dependency + source layer (uv needs src/ to build the local package)
COPY backend/pyproject.toml backend/uv.lock ./
COPY backend/src ./src
COPY readme.md /app/readme.md
RUN uv sync --frozen --no-dev

# Static data
COPY data /app/data

# M03 trained ML artifacts (closure classifier + ICT survival model)
COPY backend/models /app/backend/models

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend/src \
    GRID_ASTRAM_CSV_PATH=/app/data/astram_events.csv \
    GRID_MODELS_DIR=/app/backend/models/v1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uv", "run", "uvicorn", "grid_unlocked.main:app", "--host", "0.0.0.0", "--port", "8000"]
