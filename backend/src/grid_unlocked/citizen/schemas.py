from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class CitizenReportStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class CitizenReport(BaseModel):
    report_id: str
    status: CitizenReportStatus
    h3_cell: str
    corridor: str | None = None
    junction: str | None = None
    ict_p50: float
    ict_p80: float
    p_closure: float
    cause_hint: str
    cause_confidence: float
    event_id: str | None = None
    has_photo: bool = False
    created_at: datetime


class CitizenReportStatusResponse(BaseModel):
    report_id: str
    status: CitizenReportStatus
    ict_p50: float
    ict_p80: float
    p_closure: float
    corridor: str | None = None
    h3_cell: str
    created_at: datetime


class CitizenVerifyRequest(BaseModel):
    commander_id: str


class CitizenRejectRequest(BaseModel):
    reason_code: str
    commander_id: str | None = None


class SubscriptionRequest(BaseModel):
    user_ref: str
    corridors: list[str] = Field(default_factory=list)
    h3_cells: list[str] = Field(default_factory=list)


class SubscriptionResponse(BaseModel):
    subscription_id: str
    user_ref: str
    corridors: list[str]
    h3_cells: list[str]
    created_at: datetime


class CitizenPreAlertPayload(BaseModel):
    subscription_id: str
    alert_type: Literal["hotspot", "propagation"]
    severity_band: str
