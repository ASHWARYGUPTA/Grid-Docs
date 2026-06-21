"""M11 — VMSRouter Router.

Public endpoints:
  POST /vms/push                  — internal trigger from M09 approve()
  GET  /vms/status/{delivery_id}  — current per-board delivery state
  POST /vms/retry/{delivery_id}   — admin manual retry (dead-letter recovery)
  POST /mock/vms/receive          — hackathon demo endpoint (captures payload)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db.session import get_session
from grid_unlocked.vms.schemas import (
    MockVmsReceiveResponse,
    VmsPushRequest,
    VmsPushResponse,
    VmsRetryResponse,
    VmsStatusResponse,
)
from grid_unlocked.vms.service import VmsService

router = APIRouter(prefix="/vms", tags=["vms"])
mock_router = APIRouter(prefix="/mock", tags=["vms-mock"])


async def _service(session: AsyncSession = Depends(get_session)) -> VmsService:
    return VmsService(session)


@router.post("/push", response_model=VmsPushResponse)
async def vms_push(
    req: VmsPushRequest,
    service: VmsService = Depends(_service),
) -> VmsPushResponse:
    """
    Internal endpoint — triggered by M09 approve() when not in shadow mode.
    Fans out to all corridor boards fire-and-forget; returns within ≤500 ms P95.
    """
    return await service.push(req)


@router.get("/status/{delivery_id}", response_model=VmsStatusResponse)
async def get_vms_status(
    delivery_id: str,
    service: VmsService = Depends(_service),
) -> VmsStatusResponse:
    """Current delivery state for a single board within a push."""
    return await service.get_status(delivery_id)


@router.post("/retry/{delivery_id}", response_model=VmsRetryResponse)
async def retry_vms_delivery(
    delivery_id: str,
    service: VmsService = Depends(_service),
) -> VmsRetryResponse:
    """Admin-only: re-queue a DEAD_LETTER or FAILED board delivery."""
    return await service.retry(delivery_id)


# ---------------------------------------------------------------------------
# Mock / demo endpoint
# ---------------------------------------------------------------------------


@mock_router.post("/vms/receive", response_model=MockVmsReceiveResponse)
async def mock_vms_receive(payload: dict | None = None) -> MockVmsReceiveResponse:
    """
    Hackathon demo endpoint — simulates a VMS board vendor webhook receiver.
    Captures the pushed text and returns a plausible ACK for UI/Swagger demo.

    In the live flow this endpoint is called internally by MockWebhookClient;
    it is also exposed for direct demo testing.
    """
    board_id = (payload or {}).get("board_id", "VMS-DEMO")
    board_text = (payload or {}).get("board_text", "")
    return MockVmsReceiveResponse(
        ack_id=f"VMSACK-{board_id}-{uuid.uuid4().hex[:6].upper()}",
        board_id=board_id,
        received_text=board_text,
        status="displayed",
        message=f"Board {board_id} updated successfully",
    )
