import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db.models import (
    CitizenReportRow,
    CorridorCentroidRow,
    CorridorSubscriptionRow,
    NormalizedEventRow,
)


class CitizenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_all_centroids(self) -> list[tuple[str, float, float]]:
        rows = await self.session.execute(select(CorridorCentroidRow))
        return [(r.corridor, r.lat, r.lon) for r in rows.scalars().all()]

    async def save_report(self, row: CitizenReportRow) -> CitizenReportRow:
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get_report(self, report_id: str) -> CitizenReportRow | None:
        return await self.session.get(CitizenReportRow, report_id)

    async def update_status(
        self,
        report_id: str,
        status: str,
        *,
        event_id: str | None = None,
        verified_by: str | None = None,
        rejected_by: str | None = None,
        reject_reason_code: str | None = None,
    ) -> CitizenReportRow | None:
        row = await self.session.get(CitizenReportRow, report_id)
        if row is None:
            return None
        row.status = status
        if event_id is not None:
            row.event_id = event_id
        if verified_by is not None:
            row.verified_by = verified_by
        if rejected_by is not None:
            row.rejected_by = rejected_by
        if reject_reason_code is not None:
            row.reject_reason_code = reject_reason_code
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def set_event_authenticated(self, event_id: str, authenticated: bool) -> None:
        row = await self.session.get(NormalizedEventRow, event_id)
        if row is not None:
            row.authenticated = authenticated
            await self.session.commit()

    async def create_subscription(self, row: CorridorSubscriptionRow) -> CorridorSubscriptionRow:
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def deactivate_subscription(self, subscription_id: str) -> bool:
        row = await self.session.get(CorridorSubscriptionRow, subscription_id)
        if row is None or not row.active:
            return False
        row.active = False
        await self.session.commit()
        return True

    async def list_active_subscriptions(self) -> list[CorridorSubscriptionRow]:
        rows = await self.session.execute(
            select(CorridorSubscriptionRow).where(CorridorSubscriptionRow.active.is_(True))
        )
        return list(rows.scalars().all())


def decode_json_list(value: str) -> list[str]:
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return []
    return decoded if isinstance(decoded, list) else []
