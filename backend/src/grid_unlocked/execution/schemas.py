"""M10 — AgenticExecutionBroker Schemas.

Pydantic models for execution commands, status machine, and audit responses.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Execution state machine
# ---------------------------------------------------------------------------


class ExecutionStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"


class CommandType(StrEnum):
    DISPATCH = "dispatch"
    BARRICADE = "barricade"  # D-M10-02: real BTP asset API in Phase 1.5


# ---------------------------------------------------------------------------
# Request / trigger schemas
# ---------------------------------------------------------------------------


class ExecuteDispatchRequest(BaseModel):
    """Internal trigger sent by M09 approve() when not in shadow mode."""

    approval_token: str
    card_id: str
    event_id: str
    recommendation_id: str | None = None
    barricade_count: int = Field(default=0, ge=0)
    station_id: str | None = None  # nearest station from dispatch recommendation
    commander_id: str


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ExecutionRecord(BaseModel):
    """Current state of a queued command."""

    execution_id: str
    approval_token: str
    card_id: str
    event_id: str
    command_type: CommandType
    status: ExecutionStatus
    attempt_count: int
    created_at: datetime
    updated_at: datetime
    next_retry_at: datetime | None = None


class AuditEntry(BaseModel):
    """Single immutable audit log entry (one per attempt)."""

    id: int
    execution_id: str
    approval_token: str
    card_id: str
    event_id: str
    command_type: CommandType
    attempt_number: int
    station_id: str | None
    request_payload: str  # raw JSON string
    response_code: int | None
    response_body: str | None  # raw JSON string
    outcome: str  # acknowledged | failed | dead_letter
    error_detail: str | None
    executed_at: datetime


class ExecutionStatusResponse(BaseModel):
    """Response for GET /execute/status/{execution_id}."""

    execution_id: str
    card_id: str
    event_id: str
    status: ExecutionStatus
    attempt_count: int
    audit_entries: list[AuditEntry]
    message: str


class ExecutionEnqueueResponse(BaseModel):
    """Response for POST /execute/dispatch."""

    execution_id: str
    approval_token: str
    status: ExecutionStatus
    enqueue_ms: float
    message: str


class RetryResponse(BaseModel):
    """Response for POST /execute/retry/{execution_id}."""

    execution_id: str
    status: ExecutionStatus
    message: str


class AuditQueryResponse(BaseModel):
    """Response for GET /execute/audit."""

    entries: list[AuditEntry]
    count: int


class MockStationAckResponse(BaseModel):
    """Hackathon demo endpoint response — POST /mock/station/ack."""

    unit_id: str
    station_id: str
    status: str
    ack_id: str
    message: str
