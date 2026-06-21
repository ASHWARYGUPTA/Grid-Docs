from collections.abc import AsyncGenerator
from urllib.parse import urlparse, urlunparse, urlencode, parse_qs

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from grid_unlocked.config import settings
from grid_unlocked.db.models import (  # noqa: F401 — register all tables with Base.metadata
    ActionCardRow,
    ApprovalRecordRow,
    Base,
    CausePriorRow,
    CitizenReportRow,
    CorridorCausePriorRow,
    CorridorCentroidRow,
    CorridorSubscriptionRow,
    DispatchRecommendationRow,
    FeatureSnapshotRow,
    FieldAcknowledgementRow,
    FieldClosureRow,
    HourBiasWeightRow,
    ImpactScoreRow,
    IngestRejectRow,
    NormalizedEventRow,
    PlannedPackageRow,
    TransitImpactCacheRow,
)


def _make_engine():
    """Build the async engine, handling asyncpg's SSL incompatibility with
    the ?sslmode=require query param that Neon (and other managed Postgres
    providers) include in their connection strings.

    asyncpg does not accept `sslmode` as a connection argument — it raises
    TypeError: connect() got an unexpected keyword argument 'sslmode'.
    The correct approach is to strip the param from the URL and pass
    ssl=True via connect_args instead.
    """
    db_url = settings.database_url
    connect_args: dict = {}

    if db_url.startswith("postgresql"):
        parsed = urlparse(db_url)
        qs = parse_qs(parsed.query)

        # Pull out sslmode and decide whether to enable SSL
        sslmode = qs.pop("sslmode", [None])[0]
        needs_ssl = sslmode in ("require", "verify-ca", "verify-full")

        # Rebuild the URL without sslmode
        clean_query = urlencode({k: v[0] for k, v in qs.items()})
        clean_url = urlunparse(parsed._replace(query=clean_query))

        if needs_ssl:
            connect_args["ssl"] = True

        return create_async_engine(clean_url, echo=False, connect_args=connect_args)

    return create_async_engine(db_url, echo=False)


engine = _make_engine()
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
