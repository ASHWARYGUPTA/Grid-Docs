"""M11 — VMSRouter Schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class VmsDeliveryStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class VmsPushRequest(BaseModel):
    """Internal trigger — called from M09 approve() or directly via API."""

    push_id: str  # idempotency key — typically approval_token
    event_id: str
    card_id: str
    corridor: str | None = None
    routes: list[dict] = Field(default_factory=list)  # serialised DiversionRoute list
    commander_id: str


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class BoardDelivery(BaseModel):
    """Status for a single board within a push."""

    delivery_id: str
    board_id: str
    board_name: str
    board_text: str  # rendered ≤120 char English template
    status: VmsDeliveryStatus
    retry_count: int
    ack_id: str | None = None
    response_code: int | None = None
    error_detail: str | None = None
    created_at: datetime
    updated_at: datetime


class VmsPushResponse(BaseModel):
    """Response for POST /vms/push — one entry per targeted board."""

    push_id: str
    event_id: str
    card_id: str
    board_count: int
    deliveries: list[BoardDelivery]
    fanout_ms: float
    message: str


class VmsStatusResponse(BaseModel):
    """Response for GET /vms/status/{delivery_id}."""

    delivery_id: str
    board_id: str
    board_name: str
    board_text: str
    status: VmsDeliveryStatus
    retry_count: int
    ack_id: str | None
    message: str


class VmsRetryResponse(BaseModel):
    delivery_id: str
    status: VmsDeliveryStatus
    message: str


class MockVmsReceiveResponse(BaseModel):
    """Response from POST /mock/vms/receive — simulates board vendor ACK."""

    ack_id: str
    board_id: str
    received_text: str
    status: str
    message: str
