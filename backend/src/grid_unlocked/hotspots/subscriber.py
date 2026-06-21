from datetime import UTC, datetime

import h3

from grid_unlocked.dashboard.bus import dashboard_bus
from grid_unlocked.dashboard.schemas import DashboardDelta, DeltaScope
from grid_unlocked.hotspots.cusum import cusum_tracker
from grid_unlocked.ingestion.bus import event_bus
from grid_unlocked.ingestion.schemas import EventNormalizedMessage


async def _handle_normalized(message: EventNormalizedMessage) -> None:
    event = message.event
    corridor = event.corridor or "Non-corridor"
    cusum_tracker.record(corridor, event.start_datetime)
    h3_res7 = h3.latlng_to_cell(event.latitude, event.longitude, 7)
    await dashboard_bus.publish(
        DashboardDelta(
            scope=DeltaScope.HOTSPOT,
            event_id=event.event_id,
            payload={"corridor": corridor, "h3_res7": h3_res7},
            emitted_at=datetime.now(UTC),
        )
    )


_registered = False


def register_hotspot_subscribers() -> None:
    global _registered
    if _registered:
        return
    event_bus.subscribe_normalized(_handle_normalized)
    _registered = True
