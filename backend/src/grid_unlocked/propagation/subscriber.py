from grid_unlocked.db.session import SessionLocal
from grid_unlocked.ingestion.bus import event_bus
from grid_unlocked.ingestion.schemas import EventClosedMessage
from grid_unlocked.propagation.service import PropagationService


async def _handle_closed(message: EventClosedMessage) -> None:
    async with SessionLocal() as session:
        service = PropagationService(session)
        await service.on_event_closed(message.event_id)


_registered = False


def register_propagation_subscribers() -> None:
    global _registered
    if _registered:
        return
    event_bus.subscribe_closed(_handle_closed)
    _registered = True
