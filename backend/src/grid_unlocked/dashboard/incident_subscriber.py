"""Stream A — fan a `DashboardDelta(scope=incident)` out to /ws/dashboard the
moment ingestion normalizes a new event. Lightweight payload (no RCI: scored
async by impact subscriber). Failures are logged, never propagated, so fan-out
never breaks ingest."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from grid_unlocked.dashboard.bus import dashboard_bus
from grid_unlocked.dashboard.schemas import DashboardDelta, DeltaScope
from grid_unlocked.ingestion.bus import event_bus
from grid_unlocked.ingestion.schemas import EventNormalizedMessage

logger = logging.getLogger(__name__)


async def _handle_normalized(message: EventNormalizedMessage) -> None:
    event = message.event
    try:
        await dashboard_bus.publish(
            DashboardDelta(
                scope=DeltaScope.INCIDENT,
                event_id=event.event_id,
                payload={
                    "corridor": event.corridor,
                    "junction": event.junction,
                    "event_type": event.event_type,
                    "cause": event.event_cause,
                    "lat": event.latitude,
                    "lng": event.longitude,
                    "status": event.status,
                },
                emitted_at=datetime.now(UTC),
            )
        )
    except Exception:
        logger.exception("incident_subscriber: failed to publish incident delta")


_registered = False


def register_incident_subscribers() -> None:
    global _registered
    if _registered:
        return
    event_bus.subscribe_normalized(_handle_normalized)
    _registered = True
