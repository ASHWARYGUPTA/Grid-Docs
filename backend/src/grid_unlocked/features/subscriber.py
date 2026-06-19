import asyncio

from grid_unlocked.db.session import SessionLocal
from grid_unlocked.features.service import FeatureService
from grid_unlocked.ingestion.bus import event_bus
from grid_unlocked.ingestion.schemas import EventClosedMessage, EventNormalizedMessage


async def _materialize(message: EventNormalizedMessage) -> None:
    async with SessionLocal() as session:
        service = FeatureService(session)
        await service.on_event_normalized(message)


async def _handle_normalized(message: EventNormalizedMessage) -> None:
    asyncio.create_task(_materialize(message))


async def _handle_closed(message: EventClosedMessage) -> None:
    async with SessionLocal() as session:
        service = FeatureService(session)
        await service.on_event_closed(message)


_registered = False


def register_feature_subscribers() -> None:
    global _registered
    if _registered:
        return
    event_bus.subscribe_normalized(_handle_normalized)
    event_bus.subscribe_closed(_handle_closed)
    _registered = True
