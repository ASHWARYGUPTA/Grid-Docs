import pytest
from sqlalchemy.pool import StaticPool

from grid_unlocked.config import settings
from grid_unlocked.db.session import init_db
from grid_unlocked.features.priors_loader import priors_need_seed, seed_priors_from_csv


@pytest.fixture(autouse=True)
async def test_db(monkeypatch):
    monkeypatch.setattr(settings, "database_url", "sqlite+aiosqlite:///:memory:")
    from grid_unlocked.db import session as session_module
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    session_module.engine = create_async_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_module.SessionLocal = async_sessionmaker(
        session_module.engine, expire_on_commit=False
    )

    await init_db()
    async with session_module.SessionLocal() as session:
        if await priors_need_seed(session):
            await seed_priors_from_csv(session)
    yield
    await session_module.engine.dispose()
