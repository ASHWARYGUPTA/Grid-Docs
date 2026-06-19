from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db.models import NormalizedEventRow
from grid_unlocked.hotspots.dbscan import EventPoint


class HotspotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_observable_events(self, recent_hours: int = 24) -> list[EventPoint]:
        cutoff = datetime.now(UTC) - timedelta(hours=recent_hours)
        rows = (
            await self.session.scalars(
                select(NormalizedEventRow).where(
                    or_(
                        NormalizedEventRow.status == "active",
                        NormalizedEventRow.start_datetime >= cutoff,
                    )
                )
            )
        ).all()

        return [
            EventPoint(
                row.event_id,
                row.latitude,
                row.longitude,
                row.event_cause,
                row.corridor,
            )
            for row in rows
        ]
