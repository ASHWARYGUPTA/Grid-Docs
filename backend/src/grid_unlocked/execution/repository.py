"""M10 — ExecutionRepository.

Handles all DB reads and writes for execution_queue and execution_audit tables.
Both tables are append-or-update only — audit rows are never mutated after insert.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db.models import ExecutionAuditRow, ExecutionQueueRow
from grid_unlocked.execution.schemas import (
    AuditEntry,
    CommandType,
    ExecutionRecord,
    ExecutionStatus,
)


class ExecutionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Queue rows
    # ------------------------------------------------------------------

    async def create_queue_row(
        self,
        execution_id: str,
        approval_token: str,
        card_id: str,
        event_id: str,
        command_type: CommandType,
    ) -> ExecutionQueueRow:
        row = ExecutionQueueRow(
            execution_id=execution_id,
            approval_token=approval_token,
            card_id=card_id,
            event_id=event_id,
            command_type=command_type.value,
            status=ExecutionStatus.PENDING.value,
            attempt_count=0,
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get_queue_row(self, execution_id: str) -> ExecutionQueueRow | None:
        return await self.session.get(ExecutionQueueRow, execution_id)

    async def get_queue_row_by_token(
        self, approval_token: str, command_type: CommandType
    ) -> ExecutionQueueRow | None:
        return await self.session.scalar(
            select(ExecutionQueueRow)
            .where(ExecutionQueueRow.approval_token == approval_token)
            .where(ExecutionQueueRow.command_type == command_type.value)
            .limit(1)
        )

    async def update_queue_status(
        self,
        execution_id: str,
        status: ExecutionStatus,
        *,
        attempt_count: int | None = None,
        next_retry_at: datetime | None = None,
    ) -> None:
        row = await self.session.get(ExecutionQueueRow, execution_id)
        if not row:
            return
        row.status = status.value
        row.updated_at = datetime.now(UTC)
        if attempt_count is not None:
            row.attempt_count = attempt_count
        if next_retry_at is not None:
            row.next_retry_at = next_retry_at
        await self.session.commit()

    async def to_execution_record(self, row: ExecutionQueueRow) -> ExecutionRecord:
        return ExecutionRecord(
            execution_id=row.execution_id,
            approval_token=row.approval_token,
            card_id=row.card_id,
            event_id=row.event_id,
            command_type=CommandType(row.command_type),
            status=ExecutionStatus(row.status),
            attempt_count=row.attempt_count,
            created_at=row.created_at,
            updated_at=row.updated_at,
            next_retry_at=row.next_retry_at,
        )

    # ------------------------------------------------------------------
    # Audit rows (immutable — insert only)
    # ------------------------------------------------------------------

    async def append_audit(
        self,
        *,
        execution_id: str,
        approval_token: str,
        card_id: str,
        event_id: str,
        command_type: CommandType,
        attempt_number: int,
        station_id: str | None,
        request_payload: dict,
        response_code: int | None,
        response_body: dict | str | None,
        outcome: str,
        error_detail: str | None = None,
    ) -> ExecutionAuditRow:
        resp_str: str | None = None
        if isinstance(response_body, dict):
            resp_str = json.dumps(response_body)
        elif isinstance(response_body, str):
            resp_str = response_body

        row = ExecutionAuditRow(
            execution_id=execution_id,
            approval_token=approval_token,
            card_id=card_id,
            event_id=event_id,
            command_type=command_type.value,
            attempt_number=attempt_number,
            station_id=station_id,
            request_payload=json.dumps(request_payload),
            response_code=response_code,
            response_body=resp_str,
            outcome=outcome,
            error_detail=error_detail,
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def list_audit(
        self,
        *,
        execution_id: str | None = None,
        event_id: str | None = None,
        card_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        q = select(ExecutionAuditRow)
        if execution_id:
            q = q.where(ExecutionAuditRow.execution_id == execution_id)
        if event_id:
            q = q.where(ExecutionAuditRow.event_id == event_id)
        if card_id:
            q = q.where(ExecutionAuditRow.card_id == card_id)
        q = q.order_by(ExecutionAuditRow.executed_at.desc()).limit(limit)

        rows = (await self.session.scalars(q)).all()
        return [self._to_audit_entry(r) for r in rows]

    @staticmethod
    def _to_audit_entry(row: ExecutionAuditRow) -> AuditEntry:
        return AuditEntry(
            id=row.id,
            execution_id=row.execution_id,
            approval_token=row.approval_token,
            card_id=row.card_id,
            event_id=row.event_id,
            command_type=CommandType(row.command_type),
            attempt_number=row.attempt_number,
            station_id=row.station_id,
            request_payload=row.request_payload,
            response_code=row.response_code,
            response_body=row.response_body,
            outcome=row.outcome,
            error_detail=row.error_detail,
            executed_at=row.executed_at,
        )
