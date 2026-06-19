from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from grid_unlocked.config import settings
from grid_unlocked.db.models import (  # noqa: F401 — register all tables with Base.metadata
    ActionCardRow,
    ApprovalRecordRow,
    Base,
    CausePriorRow,
    CorridorCausePriorRow,
    DispatchRecommendationRow,
    FeatureSnapshotRow,
    HourBiasWeightRow,
    ImpactScoreRow,
    IngestRejectRow,
    NormalizedEventRow,
    PlannedPackageRow,
)

engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
