"""M10 — AgenticExecutionBroker Router.

Public endpoints:
  POST /execute/dispatch          — internal trigger from M09 approve()
  GET  /execute/status/{id}       — current execution state + audit history
  POST /execute/retry/{id}        — admin manual retry (dead-letter recovery)
  GET  /execute/audit             — immutable audit query by event/card
  POST /mock/station/ack          — hackathon demo endpoint (returns fake unit_id)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db.session import get_session
from grid_unlocked.execution.schemas import (
    AuditQueryResponse,
    ExecuteDispatchRequest,
    ExecutionEnqueueResponse,
    ExecutionStatusResponse,
    MockStationAckResponse,
    RetryResponse,
)
from grid_unlocked.execution.service import ExecutionService

router = APIRouter(prefix="/execute", tags=["execution"])
mock_router = APIRouter(prefix="/mock", tags=["execution-mock"])


async def _service(session: AsyncSession = Depends(get_session)) -> ExecutionService:
    return ExecutionService(session)


@router.post("/dispatch", response_model=ExecutionEnqueueResponse)
async def execute_dispatch(
    req: ExecuteDispatchRequest,
    service: ExecutionService = Depends(_service),
) -> ExecutionEnqueueResponse:
    """
    Internal endpoint — triggered by M09 approve() when not in shadow mode.
    Enqueues command fire-and-forget; returns within ≤200 ms P95.
    """
    return await service.enqueue_dispatch(req)


@router.get("/status/{execution_id}", response_model=ExecutionStatusResponse)
async def get_execution_status(
    execution_id: str,
    service: ExecutionService = Depends(_service),
) -> ExecutionStatusResponse:
    """Current status + full audit trail for an execution command."""
    return await service.get_status(execution_id)


@router.post("/retry/{execution_id}", response_model=RetryResponse)
async def retry_execution(
    execution_id: str,
    service: ExecutionService = Depends(_service),
) -> RetryResponse:
    """Admin-only: re-enqueue a DEAD_LETTER or FAILED execution."""
    return await service.manual_retry(execution_id)


@router.get("/audit", response_model=AuditQueryResponse)
async def execution_audit(
    event_id: str | None = Query(default=None),
    card_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    service: ExecutionService = Depends(_service),
) -> AuditQueryResponse:
    """Immutable audit log — filterable by event_id or card_id."""
    return await service.get_audit(event_id=event_id, card_id=card_id, limit=limit)


# ---------------------------------------------------------------------------
# Mock / demo endpoint
# ---------------------------------------------------------------------------


@mock_router.post("/station/ack", response_model=MockStationAckResponse)
async def mock_station_ack(payload: dict = None) -> MockStationAckResponse:
    """
    Hackathon demo endpoint — simulates police station dispatch acknowledgement.
    Returns a plausible response for UI toast/audit log demonstration.

    In the live flow this endpoint is called internally by MockStationClient;
    it is also exposed for direct demo testing via the UI / Swagger.
    """
    unit_id = f"MOCK-HAL-{uuid.uuid4().hex[:4].upper()}"
    return MockStationAckResponse(
        unit_id=unit_id,
        station_id="HAL",
        status="acknowledged",
        ack_id=f"ACK-{uuid.uuid4().hex[:8].upper()}",
        message=f"Unit {unit_id} dispatched from HAL Airport Road station",
    )
