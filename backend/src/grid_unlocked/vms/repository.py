"""M11 — VmsRepository.

Handles all DB reads and writes for the vms_deliveries table.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db.models import VmsDeliveryRow
from grid_unlocked.vms.schemas import BoardDelivery, VmsDeliveryStatus


class VmsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_delivery(
        self,
        delivery_id: str,
        push_id: str,
        event_id: str,
        card_id: str,
        board_id: str,
        board_name: str,
        board_text: str,
    ) -> VmsDeliveryRow:
        row = VmsDeliveryRow(
            delivery_id=delivery_id,
            push_id=push_id,
            event_id=event_id,
            card_id=card_id,
            board_id=board_id,
            board_name=board_name,
            board_text=board_text,
            status=VmsDeliveryStatus.PENDING.value,
            retry_count=0,
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get_delivery(self, delivery_id: str) -> VmsDeliveryRow | None:
        return await self.session.get(VmsDeliveryRow, delivery_id)

    async def list_by_push(self, push_id: str) -> list[VmsDeliveryRow]:
        rows = await self.session.scalars(
            select(VmsDeliveryRow)
            .where(VmsDeliveryRow.push_id == push_id)
            .order_by(VmsDeliveryRow.created_at)
        )
        return list(rows.all())

    async def update(
        self,
        delivery_id: str,
        *,
        status: VmsDeliveryStatus,
        retry_count: int | None = None,
        ack_id: str | None = None,
        response_code: int | None = None,
        error_detail: str | None = None,
        dead_letter: bool = False,
    ) -> None:
        row = await self.session.get(VmsDeliveryRow, delivery_id)
        if not row:
            return
        row.status = status.value
        row.updated_at = datetime.now(UTC)
        if retry_count is not None:
            row.retry_count = retry_count
        if ack_id is not None:
            row.ack_id = ack_id
        if response_code is not None:
            row.response_code = response_code
        if error_detail is not None:
            row.error_detail = error_detail
        if dead_letter:
            row.dead_letter = True
        await self.session.commit()

    @staticmethod
    def to_board_delivery(row: VmsDeliveryRow) -> BoardDelivery:
        return BoardDelivery(
            delivery_id=row.delivery_id,
            board_id=row.board_id,
            board_name=row.board_name,
            board_text=row.board_text,
            status=VmsDeliveryStatus(row.status),
            retry_count=row.retry_count,
            ack_id=row.ack_id,
            response_code=row.response_code,
            error_detail=row.error_detail,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
