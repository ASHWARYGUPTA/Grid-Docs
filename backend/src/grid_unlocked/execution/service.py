"""M10 — ExecutionService.

Core business logic for the AgenticExecutionBroker:
  - Shadow mode gate: block all execution when shadow_mode=True
  - Idempotency: keyed by approval_token — double-approve → single execution
  - Enqueue: fire-and-forget ≤200 ms handoff
  - Retry: exponential backoff 2s / 4s / 8s, max 3 attempts
  - DLQ: dead_letter after all retries exhausted
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db import session as _session_module
from grid_unlocked.execution.queue import (
    CommandQueue,
    QueuedCommand,
    get_command_queue,
    set_command_queue,
)
from grid_unlocked.execution.repository import ExecutionRepository
from grid_unlocked.execution.schemas import (
    AuditEntry,
    AuditQueryResponse,
    CommandType,
    ExecuteDispatchRequest,
    ExecutionEnqueueResponse,
    ExecutionRecord,
    ExecutionStatus,
    ExecutionStatusResponse,
    RetryResponse,
)
from grid_unlocked.execution.station_client import MockStationClient
from grid_unlocked.recommendations.governance import get_governance

logger = logging.getLogger(__name__)

# Retry schedule: attempt 1→2s, 2→4s, 3→8s
_RETRY_DELAYS = [2.0, 4.0, 8.0]
_MAX_ATTEMPTS = 3


# ---------------------------------------------------------------------------
# Setup — called once at app lifespan startup
# ---------------------------------------------------------------------------


async def setup_command_queue(station_client: MockStationClient | None = None) -> CommandQueue:
    """Initialise the singleton CommandQueue with the background processor."""
    client = station_client or MockStationClient()

    async def _processor(cmd: QueuedCommand) -> None:
        await _process_command(cmd, client)

    q = CommandQueue(_processor)
    set_command_queue(q)
    await q.start()
    return q


# ---------------------------------------------------------------------------
# Background processor (called by queue worker)
# ---------------------------------------------------------------------------


async def _process_command(cmd: QueuedCommand, client: MockStationClient) -> None:
    """Execute one command with retry logic, writing audit entries throughout."""
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        async with _session_module.SessionLocal() as session:
            repo = ExecutionRepository(session)
            await repo.update_queue_status(
                cmd.execution_id,
                ExecutionStatus.PROCESSING,
                attempt_count=attempt,
            )

        try:
            if cmd.command_type == CommandType.DISPATCH:
                resp = await client.dispatch_unit(
                    cmd.station_id, cmd.event_id, cmd.card_id, cmd.recommendation_id
                )
            else:
                resp = await client.reserve_barricades(
                    cmd.station_id, cmd.event_id, cmd.barricade_count
                )

            request_payload = {
                "execution_id": cmd.execution_id,
                "event_id": cmd.event_id,
                "card_id": cmd.card_id,
                "command_type": cmd.command_type,
                "station_id": cmd.station_id,
                "approval_token": cmd.approval_token,
            }

            if resp.status_code == 200:
                # SUCCESS
                async with _session_module.SessionLocal() as session:
                    repo = ExecutionRepository(session)
                    await repo.append_audit(
                        execution_id=cmd.execution_id,
                        approval_token=cmd.approval_token,
                        card_id=cmd.card_id,
                        event_id=cmd.event_id,
                        command_type=CommandType(cmd.command_type),
                        attempt_number=attempt,
                        station_id=cmd.station_id or resp.body.get("station_id"),
                        request_payload=request_payload,
                        response_code=resp.status_code,
                        response_body=resp.body,
                        outcome="acknowledged",
                    )
                    await repo.update_queue_status(
                        cmd.execution_id,
                        ExecutionStatus.ACKNOWLEDGED,
                        attempt_count=attempt,
                    )
                logger.info(
                    "Execution %s acknowledged on attempt %d (%.1f ms)",
                    cmd.execution_id,
                    attempt,
                    resp.latency_ms,
                )
                return

            # FAILURE — log and decide whether to retry or DLQ
            error_detail = str(resp.body)
            async with _session_module.SessionLocal() as session:
                repo = ExecutionRepository(session)
                is_final = attempt >= _MAX_ATTEMPTS
                outcome = "dead_letter" if is_final else "failed"
                await repo.append_audit(
                    execution_id=cmd.execution_id,
                    approval_token=cmd.approval_token,
                    card_id=cmd.card_id,
                    event_id=cmd.event_id,
                    command_type=CommandType(cmd.command_type),
                    attempt_number=attempt,
                    station_id=cmd.station_id,
                    request_payload=request_payload,
                    response_code=resp.status_code,
                    response_body=resp.body,
                    outcome=outcome,
                    error_detail=error_detail,
                )
                if is_final:
                    await repo.update_queue_status(
                        cmd.execution_id,
                        ExecutionStatus.DEAD_LETTER,
                        attempt_count=attempt,
                    )
                    logger.error(
                        "Execution %s moved to DLQ after %d attempts",
                        cmd.execution_id,
                        attempt,
                    )
                    # D-M10-04: Ops alert (PagerDuty/Slack) deferred to Phase 1.5
                    return
                else:
                    delay = _RETRY_DELAYS[attempt - 1]
                    retry_at = datetime.now(UTC) + timedelta(seconds=delay)
                    await repo.update_queue_status(
                        cmd.execution_id,
                        ExecutionStatus.RETRYING,
                        attempt_count=attempt,
                        next_retry_at=retry_at,
                    )

            logger.warning(
                "Execution %s failed on attempt %d (HTTP %d) — retrying in %.0fs",
                cmd.execution_id,
                attempt,
                resp.status_code,
                _RETRY_DELAYS[attempt - 1],
            )
            await asyncio.sleep(_RETRY_DELAYS[attempt - 1])

        except Exception as exc:
            logger.exception("Unexpected error in execution %s attempt %d", cmd.execution_id, attempt)
            async with _session_module.SessionLocal() as session:
                repo = ExecutionRepository(session)
                is_final = attempt >= _MAX_ATTEMPTS
                await repo.append_audit(
                    execution_id=cmd.execution_id,
                    approval_token=cmd.approval_token,
                    card_id=cmd.card_id,
                    event_id=cmd.event_id,
                    command_type=CommandType(cmd.command_type),
                    attempt_number=attempt,
                    station_id=cmd.station_id,
                    request_payload={"execution_id": cmd.execution_id},
                    response_code=None,
                    response_body=None,
                    outcome="dead_letter" if is_final else "failed",
                    error_detail=str(exc),
                )
                if is_final:
                    await repo.update_queue_status(
                        cmd.execution_id, ExecutionStatus.DEAD_LETTER, attempt_count=attempt
                    )
                    return
            if attempt < _MAX_ATTEMPTS:
                await asyncio.sleep(_RETRY_DELAYS[attempt - 1])


# ---------------------------------------------------------------------------
# ExecutionService — called from API router and M09 approve()
# ---------------------------------------------------------------------------


class ExecutionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ExecutionRepository(session)

    async def enqueue_dispatch(self, req: ExecuteDispatchRequest) -> ExecutionEnqueueResponse:
        """
        Main entry point: enqueue a dispatch command (and a barricade reservation
        command, if requested) post-approval.

        1. Shadow gate — block if shadow_mode=True.
        2. Idempotency — return existing record if approval_token already queued.
        3. Create queue row(s) → enqueue to background worker (fire-and-forget).
        4. Return response within ≤200 ms P95.
        """
        t0 = time.perf_counter()

        gov = get_governance()
        if gov.shadow_mode:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="M10 execution blocked: shadow_mode=true. Approve does not trigger real dispatch.",
            )
        if gov.tier == "3":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="M10 execution disabled in Tier 3 continuity mode. Manual dispatch SOP applies.",
            )

        dispatch_result = await self._enqueue_command(req, CommandType.DISPATCH)

        barricade_execution_id: str | None = None
        if req.barricade_count > 0:
            barricade_result = await self._enqueue_command(req, CommandType.BARRICADE)
            barricade_execution_id = barricade_result.execution_id

        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        return ExecutionEnqueueResponse(
            execution_id=dispatch_result.execution_id,
            approval_token=req.approval_token,
            status=dispatch_result.status,
            enqueue_ms=elapsed,
            message=dispatch_result.message,
            barricade_execution_id=barricade_execution_id,
        )

    async def _enqueue_command(
        self, req: ExecuteDispatchRequest, command_type: CommandType
    ) -> ExecutionEnqueueResponse:
        """Enqueue a single command (dispatch or barricade), idempotent on
        (approval_token, command_type)."""
        t0 = time.perf_counter()

        # Idempotency check — D-M10-03 note: with Redis Streams this would be atomic
        existing = await self.repo.get_queue_row_by_token(req.approval_token, command_type)
        if existing:
            elapsed = round((time.perf_counter() - t0) * 1000, 2)
            return ExecutionEnqueueResponse(
                execution_id=existing.execution_id,
                approval_token=req.approval_token,
                status=ExecutionStatus(existing.status),
                enqueue_ms=elapsed,
                message=f"Idempotent: execution {existing.execution_id} already enqueued (status={existing.status})",
            )

        execution_id = f"EXEC-{uuid.uuid4().hex[:12].upper()}"

        # Create persistent queue row before enqueue (ensures auditability even if worker crashes)
        await self.repo.create_queue_row(
            execution_id=execution_id,
            approval_token=req.approval_token,
            card_id=req.card_id,
            event_id=req.event_id,
            command_type=command_type,
        )

        cmd = QueuedCommand(
            execution_id=execution_id,
            approval_token=req.approval_token,
            card_id=req.card_id,
            event_id=req.event_id,
            command_type=command_type,
            station_id=req.station_id,
            barricade_count=req.barricade_count,
            recommendation_id=req.recommendation_id,
        )

        # Fire-and-forget — caller returns immediately
        queue = get_command_queue()
        await queue.enqueue(cmd)

        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        logger.info(
            "Enqueued %s %s for card %s (%.1f ms)",
            command_type.value,
            execution_id,
            req.card_id,
            elapsed,
        )

        label = "Dispatch" if command_type == CommandType.DISPATCH else "Barricade reservation"
        return ExecutionEnqueueResponse(
            execution_id=execution_id,
            approval_token=req.approval_token,
            status=ExecutionStatus.PENDING,
            enqueue_ms=elapsed,
            message=f"{label} command enqueued — execution_id={execution_id}. Station ACK async.",
        )

    async def get_status(self, execution_id: str) -> ExecutionStatusResponse:
        row = await self.repo.get_queue_row(execution_id)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution {execution_id} not found",
            )
        entries = await self.repo.list_audit(execution_id=execution_id)
        return ExecutionStatusResponse(
            execution_id=execution_id,
            card_id=row.card_id,
            event_id=row.event_id,
            status=ExecutionStatus(row.status),
            attempt_count=row.attempt_count,
            audit_entries=entries,
            message=self._status_message(ExecutionStatus(row.status), row.attempt_count),
        )

    async def manual_retry(self, execution_id: str) -> RetryResponse:
        """Admin-initiated retry for dead-letter executions."""
        row = await self.repo.get_queue_row(execution_id)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution {execution_id} not found",
            )
        if row.status not in {ExecutionStatus.DEAD_LETTER, ExecutionStatus.FAILED}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Execution {execution_id} is in state '{row.status}' — only DEAD_LETTER/FAILED can be retried",
            )

        # Reset attempt count and re-enqueue
        await self.repo.update_queue_status(
            execution_id, ExecutionStatus.PENDING, attempt_count=0
        )
        cmd = QueuedCommand(
            execution_id=execution_id,
            approval_token=row.approval_token,
            card_id=row.card_id,
            event_id=row.event_id,
            command_type=row.command_type,
            station_id=None,
            barricade_count=0,
            recommendation_id=None,
        )
        queue = get_command_queue()
        await queue.enqueue(cmd)

        return RetryResponse(
            execution_id=execution_id,
            status=ExecutionStatus.PENDING,
            message=f"Execution {execution_id} re-enqueued for retry",
        )

    async def get_audit(
        self,
        event_id: str | None = None,
        card_id: str | None = None,
        limit: int = 100,
    ) -> AuditQueryResponse:
        entries = await self.repo.list_audit(event_id=event_id, card_id=card_id, limit=limit)
        return AuditQueryResponse(entries=entries, count=len(entries))

    @staticmethod
    def _status_message(s: ExecutionStatus, attempts: int) -> str:
        return {
            ExecutionStatus.PENDING: "Command queued — awaiting worker pickup",
            ExecutionStatus.PROCESSING: f"Processing (attempt {attempts})",
            ExecutionStatus.ACKNOWLEDGED: "Station acknowledged dispatch",
            ExecutionStatus.FAILED: f"Failed on attempt {attempts} — retry scheduled",
            ExecutionStatus.RETRYING: f"Retrying (attempt {attempts}/{_MAX_ATTEMPTS})",
            ExecutionStatus.DEAD_LETTER: f"Dead-lettered after {attempts} attempts — manual retry required",
        }.get(s, "Unknown status")
