from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db.models import FieldAcknowledgementRow, FieldClosureRow


class FieldRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_ack(self, recommendation_id: str) -> FieldAcknowledgementRow | None:
        return await self.session.get(FieldAcknowledgementRow, recommendation_id)

    async def upsert_ack(
        self, recommendation_id: str, officer_id: str, acknowledged_at: datetime
    ) -> FieldAcknowledgementRow:
        row = await self.session.get(FieldAcknowledgementRow, recommendation_id)
        if row is None:
            row = FieldAcknowledgementRow(
                recommendation_id=recommendation_id,
                officer_id=officer_id,
                acknowledged_at=acknowledged_at,
            )
            self.session.add(row)
        else:
            row.officer_id = officer_id
            row.acknowledged_at = acknowledged_at
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def save_closure(self, row: FieldClosureRow) -> None:
        self.session.add(row)
        await self.session.commit()

    async def get_closure_by_event(self, event_id: str) -> FieldClosureRow | None:
        return await self.session.scalar(
            select(FieldClosureRow).where(FieldClosureRow.event_id == event_id)
        )
