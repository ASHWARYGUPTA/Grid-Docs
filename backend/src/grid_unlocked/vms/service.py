"""M11 — VmsService.

Core business logic for VMSRouter:
  - Shadow mode gate
  - Corridor → board registry lookup (D-M11-04: commander override deferred)
  - Template rendering per board
  - Parallel fanout with asyncio.gather (≤500 ms P95)
  - Per-delivery retry: 3× exp backoff (1s / 2s / 4s)
  - DLQ after retries exhausted
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db import session as _session_module
from grid_unlocked.recommendations.governance import get_governance
from grid_unlocked.vms.board_registry import VmsBoard, get_boards_for_corridor
from grid_unlocked.vms.mock_webhook import MockWebhookClient
from grid_unlocked.vms.repository import VmsRepository
from grid_unlocked.vms.schemas import (
    BoardDelivery,
    VmsDeliveryStatus,
    VmsPushRequest,
    VmsPushResponse,
    VmsRetryResponse,
    VmsStatusResponse,
)
from grid_unlocked.vms.templates import render_from_route

logger = logging.getLogger(__name__)

_RETRY_DELAYS = [1.0, 2.0, 4.0]
_MAX_ATTEMPTS = 3

# Module-level webhook client — swapped in tests
_webhook_client: MockWebhookClient = MockWebhookClient()


def set_webhook_client(client: MockWebhookClient) -> None:
    global _webhook_client
    _webhook_client = client


# ---------------------------------------------------------------------------
# Per-delivery retry processor (runs as asyncio background task)
# ---------------------------------------------------------------------------


async def _deliver_to_board(
    delivery_id: str,
    board: VmsBoard,
    board_text: str,
    push_id: str,
    event_id: str,
) -> None:
    """Background task: attempt delivery with retry until ACK or DLQ."""
    await asyncio.sleep(0.05)
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        async with _session_module.SessionLocal() as session:
            repo = VmsRepository(session)
            await repo.update(delivery_id, status=VmsDeliveryStatus.PROCESSING, retry_count=attempt)

        try:
            resp = await _webhook_client.post_to_board(
                board_id=board.board_id,
                board_name=board.name,
                endpoint=board.endpoint,
                board_text=board_text,
                push_id=push_id,
                event_id=event_id,
            )

            if resp.status_code == 200:
                async with _session_module.SessionLocal() as session:
                    repo = VmsRepository(session)
                    await repo.update(
                        delivery_id,
                        status=VmsDeliveryStatus.DELIVERED,
                        retry_count=attempt,
                        ack_id=resp.body.get("ack_id"),
                        response_code=resp.status_code,
                    )
                logger.info("VMS delivery %s → board %s ✓ (attempt %d)", delivery_id, board.board_id, attempt)
                return

            # Failure path
            is_final = attempt >= _MAX_ATTEMPTS
            async with _session_module.SessionLocal() as session:
                repo = VmsRepository(session)
                await repo.update(
                    delivery_id,
                    status=VmsDeliveryStatus.DEAD_LETTER if is_final else VmsDeliveryStatus.RETRYING,
                    retry_count=attempt,
                    response_code=resp.status_code,
                    error_detail=str(resp.body),
                    dead_letter=is_final,
                )
            if is_final:
                logger.error("VMS delivery %s → board %s DLQ after %d attempts", delivery_id, board.board_id, attempt)
                # D-M11-07: ops alert deferred to Phase 1.5
                return
            logger.warning("VMS delivery %s failed (HTTP %d), retry in %.0fs", delivery_id, resp.status_code, _RETRY_DELAYS[attempt - 1])
            await asyncio.sleep(_RETRY_DELAYS[attempt - 1])

        except Exception as exc:
            logger.exception("Unexpected error in VMS delivery %s attempt %d", delivery_id, attempt)
            is_final = attempt >= _MAX_ATTEMPTS
            async with _session_module.SessionLocal() as session:
                repo = VmsRepository(session)
                await repo.update(
                    delivery_id,
                    status=VmsDeliveryStatus.DEAD_LETTER if is_final else VmsDeliveryStatus.RETRYING,
                    retry_count=attempt,
                    error_detail=str(exc),
                    dead_letter=is_final,
                )
            if is_final:
                return
            await asyncio.sleep(_RETRY_DELAYS[attempt - 1])


# ---------------------------------------------------------------------------
# VmsService — called from API router and M09 approve()
# ---------------------------------------------------------------------------


class VmsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = VmsRepository(session)

    async def push(self, req: VmsPushRequest) -> VmsPushResponse:
        """
        Fanout VMS push to all corridor boards.

        1. Shadow gate
        2. Idempotency — skip if push_id already exists
        3. Derive boards from corridor
        4. Render board text per board
        5. Create delivery rows
        6. Parallel fanout (fire-and-forget background tasks)
        7. Return initial delivery list within ≤500 ms
        """
        t0 = time.perf_counter()

        gov = get_governance()
        if gov.shadow_mode:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="M11 VMS push blocked: shadow_mode=true.",
            )

        # Idempotency — check if push_id already dispatched
        existing = await self.repo.list_by_push(req.push_id)
        if existing:
            elapsed = round((time.perf_counter() - t0) * 1000, 2)
            deliveries = [VmsRepository.to_board_delivery(r) for r in existing]
            return VmsPushResponse(
                push_id=req.push_id,
                event_id=req.event_id,
                card_id=req.card_id,
                board_count=len(deliveries),
                deliveries=deliveries,
                fanout_ms=elapsed,
                message=f"Idempotent: push {req.push_id} already dispatched to {len(deliveries)} boards",
            )

        # Derive boards from corridor
        boards = get_boards_for_corridor(req.corridor)
        if not boards:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"No VMS boards mapped for corridor '{req.corridor}'",
            )

        # Use best-ranked route for board text (rank 1); fallback to empty
        best_route = req.routes[0] if req.routes else {}
        board_text = render_from_route(best_route) if best_route else "DIVERSION ALERT\nSEE ALTERNATE ROUTE\nFOLLOW SIGNS"

        # Create delivery rows + launch background tasks
        deliveries: list[BoardDelivery] = []
        for board in boards:
            delivery_id = f"VDEL-{uuid.uuid4().hex[:10].upper()}"
            row = await self.repo.create_delivery(
                delivery_id=delivery_id,
                push_id=req.push_id,
                event_id=req.event_id,
                card_id=req.card_id,
                board_id=board.board_id,
                board_name=board.name,
                board_text=board_text,
            )
            deliveries.append(VmsRepository.to_board_delivery(row))

            # Fire-and-forget background delivery task
            asyncio.create_task(
                _deliver_to_board(
                    delivery_id=delivery_id,
                    board=board,
                    board_text=board_text,
                    push_id=req.push_id,
                    event_id=req.event_id,
                ),
                name=f"vms-deliver-{delivery_id}",
            )

        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        logger.info(
            "VMS push %s: fanout to %d boards for corridor '%s' (%.1f ms)",
            req.push_id, len(boards), req.corridor, elapsed,
        )

        return VmsPushResponse(
            push_id=req.push_id,
            event_id=req.event_id,
            card_id=req.card_id,
            board_count=len(boards),
            deliveries=deliveries,
            fanout_ms=elapsed,
            message=f"VMS push dispatched to {len(boards)} boards — delivery async.",
        )

    async def get_status(self, delivery_id: str) -> VmsStatusResponse:
        row = await self.repo.get_delivery(delivery_id)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Delivery {delivery_id} not found",
            )
        return VmsStatusResponse(
            delivery_id=delivery_id,
            board_id=row.board_id,
            board_name=row.board_name,
            board_text=row.board_text,
            status=VmsDeliveryStatus(row.status),
            retry_count=row.retry_count,
            ack_id=row.ack_id,
            message=self._status_msg(VmsDeliveryStatus(row.status), row.retry_count),
        )

    async def retry(self, delivery_id: str) -> VmsRetryResponse:
        row = await self.repo.get_delivery(delivery_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Delivery {delivery_id} not found")
        if row.status not in {VmsDeliveryStatus.DEAD_LETTER, VmsDeliveryStatus.FAILED}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Delivery {delivery_id} is '{row.status}' — only DEAD_LETTER/FAILED can be retried",
            )
        await self.repo.update(delivery_id, status=VmsDeliveryStatus.PENDING, retry_count=0, dead_letter=False)

        from grid_unlocked.vms.board_registry import get_board
        board = get_board(row.board_id)
        if board:
            asyncio.create_task(
                _deliver_to_board(delivery_id, board, row.board_text, row.push_id, row.event_id),
                name=f"vms-retry-{delivery_id}",
            )
        return VmsRetryResponse(
            delivery_id=delivery_id,
            status=VmsDeliveryStatus.PENDING,
            message=f"Delivery {delivery_id} re-queued for retry",
        )

    @staticmethod
    def _status_msg(s: VmsDeliveryStatus, retries: int) -> str:
        return {
            VmsDeliveryStatus.PENDING: "Queued — awaiting fanout",
            VmsDeliveryStatus.PROCESSING: f"Delivering (attempt {retries})",
            VmsDeliveryStatus.DELIVERED: "Board acknowledged delivery",
            VmsDeliveryStatus.FAILED: f"Failed on attempt {retries} — retry scheduled",
            VmsDeliveryStatus.RETRYING: f"Retrying (attempt {retries}/{_MAX_ATTEMPTS})",
            VmsDeliveryStatus.DEAD_LETTER: f"Dead-lettered after {retries} attempts — manual retry required",
        }.get(s, "Unknown status")
