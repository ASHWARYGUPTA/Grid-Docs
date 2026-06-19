from grid_unlocked.hotspots.cusum import cusum_tracker
from grid_unlocked.ingestion.bus import event_bus
from grid_unlocked.ingestion.schemas import EventNormalizedMessage


async def _handle_normalized(message: EventNormalizedMessage) -> None:
    corridor = message.event.corridor or "Non-corridor"
    cusum_tracker.record(corridor, message.event.start_datetime)


_registered = False


def register_hotspot_subscribers() -> None:
    global _registered
    if _registered:
        return
    event_bus.subscribe_normalized(_handle_normalized)
    _registered = True
