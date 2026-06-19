from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.config import settings
from grid_unlocked.db.session import SessionLocal, get_session, init_db
from grid_unlocked.execution.service import setup_command_queue
from grid_unlocked.execution.queue import get_command_queue
from grid_unlocked.features.router import router as features_router
from grid_unlocked.features.service import FeatureService
from grid_unlocked.features.subscriber import register_feature_subscribers
from grid_unlocked.ingestion.router import events_router, health_router, router
from grid_unlocked.redis_client import close_redis, ping_redis


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    register_feature_subscribers()
    from grid_unlocked.impact.registry import registry
    from grid_unlocked.propagation.subscriber import register_propagation_subscribers

    register_propagation_subscribers()
    from grid_unlocked.hotspots.subscriber import register_hotspot_subscribers

    register_hotspot_subscribers()
    registry.load()
    from grid_unlocked.hotspots.service import HotspotService

    HotspotService.warm()
    async with SessionLocal() as session:
        service = FeatureService(session)
        await service.ensure_priors_seeded()

    # M10 — start background command queue worker
    queue = await setup_command_queue()

    yield

    # M10 — graceful shutdown
    await queue.stop()
    await close_redis()


async def _check_db(session: AsyncSession) -> bool:
    try:
        await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="Grid Unlocked API — M01–M10 (Ingestion through AgenticExecutionBroker)",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.include_router(router)
    app.include_router(events_router)
    app.include_router(health_router)
    app.include_router(features_router)
    from grid_unlocked.impact.router import models_router, router as impact_router

    app.include_router(impact_router)
    app.include_router(models_router)
    from grid_unlocked.propagation.router import router as propagation_router

    app.include_router(propagation_router)
    from grid_unlocked.hotspots.router import router as hotspots_router

    app.include_router(hotspots_router)
    from grid_unlocked.planned.router import router as planned_router, templates_router

    app.include_router(planned_router)
    app.include_router(templates_router)
    from grid_unlocked.dispatch.router import router as dispatch_router

    app.include_router(dispatch_router)
    from grid_unlocked.diversions.router import router as diversions_router

    app.include_router(diversions_router)
    from grid_unlocked.recommendations.router import router as recommendations_router

    app.include_router(recommendations_router)
    from grid_unlocked.execution.router import mock_router, router as execution_router

    app.include_router(execution_router)
    app.include_router(mock_router)

    @app.get("/health", tags=["health"])
    async def system_health() -> dict:
        db_ok = False
        async for session in get_session():
            db_ok = await _check_db(session)
            break
        redis_ok = await ping_redis()
        backend = "postgres" if settings.uses_postgres else "sqlite"
        status = "healthy" if db_ok and redis_ok else "degraded"
        return {
            "status": status,
            "database": backend,
            "database_ok": db_ok,
            "redis_ok": redis_ok,
        }

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("grid_unlocked.main:app", host="0.0.0.0", port=8000, reload=True)
