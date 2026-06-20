import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.config import settings
from grid_unlocked.db.session import SessionLocal, get_session, init_db
from grid_unlocked.execution.service import setup_command_queue
from grid_unlocked.execution.queue import get_command_queue
from grid_unlocked.features.router import router as features_router
from grid_unlocked.features.service import FeatureService
from grid_unlocked.features.subscriber import register_feature_subscribers
from grid_unlocked.governance.service import GovernanceService
from grid_unlocked.ingestion.router import events_router, health_router, router
from grid_unlocked.redis_client import close_redis, ping_redis

logger = logging.getLogger(__name__)

# M14 — health probe cycle interval (spec: "probe cycle 30 s")
_GOVERNANCE_PROBE_INTERVAL_S = 30


async def _governance_probe_loop() -> None:
    """Background task: re-evaluate automatic tier transitions every 30s."""
    while True:
        try:
            await asyncio.sleep(_GOVERNANCE_PROBE_INTERVAL_S)
            async with SessionLocal() as session:
                await GovernanceService(session).evaluate_auto_transition()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("M14 governance probe cycle failed")


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

    # M14 — seed governance_state from settings defaults and warm the cache
    async with SessionLocal() as session:
        await GovernanceService(session).bootstrap()
    probe_task = asyncio.create_task(_governance_probe_loop(), name="m14-governance-probe")

    # M10 — start background command queue worker
    queue = await setup_command_queue()

    yield

    # M10 — graceful shutdown
    await queue.stop()
    probe_task.cancel()
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
        description="Grid Unlocked API — M01–M11, M13, M14 (Ingestion through VMSRouter, plus ReplayLearningService + GovernanceConsole)",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allow_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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
    from grid_unlocked.execution.router import mock_router as execution_mock_router, router as execution_router

    app.include_router(execution_router)
    app.include_router(execution_mock_router)
    from grid_unlocked.vms.router import mock_router as vms_mock_router, router as vms_router

    app.include_router(vms_router)
    app.include_router(vms_mock_router)
    from grid_unlocked.governance.router import router as governance_router

    app.include_router(governance_router)
    from grid_unlocked.learning.router import router as learning_router

    app.include_router(learning_router)
    from grid_unlocked.dashboard.router import router as dashboard_router

    app.include_router(dashboard_router)

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
