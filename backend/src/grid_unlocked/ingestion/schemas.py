from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class IngestSource(StrEnum):
    ASTRAM = "astram"
    PLANNED_PORTAL = "planned_portal"
    FIELD = "field"
    CITIZEN = "citizen"


class RawEventPayload(BaseModel):
    """Flexible ingest payload — ASTraM webhook, portal, field, or citizen triage."""

    model_config = ConfigDict(extra="allow")

    event_id: str | None = Field(default=None, alias="id")
    event_type: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    address: str | None = None
    event_cause: str | None = None
    requires_road_closure: bool | None = None
    start_datetime: datetime | str | None = None
    end_datetime: datetime | str | None = None
    status: str | None = None
    authenticated: bool | str | None = None
    created_date: datetime | str | None = None
    closed_datetime: datetime | str | None = None
    corridor: str | None = None
    zone: str | None = None
    junction: str | None = None
    police_station: str | None = None
    priority: str | None = None
    description: str | None = None
    veh_type: str | None = None
    source: str | None = None


class NormalizedEvent(BaseModel):
    event_id: str
    source: IngestSource
    event_type: str
    is_planned: bool
    event_cause: str
    status: str
    authenticated: bool

    latitude: float
    longitude: float
    address: str | None = None
    corridor: str | None = None
    zone: str | None = None
    junction: str | None = None
    police_station: str | None = None
    priority: str | None = None

    requires_road_closure: bool = False
    start_datetime: datetime
    end_datetime: datetime | None = None
    created_date: datetime | None = None
    closed_datetime: datetime | None = None
    reporting_lag_minutes: float | None = None

    description: str | None = None
    veh_type: str | None = None
    anomaly_flags: list[str] = Field(default_factory=list)

    ingested_at: datetime | None = None
    updated_at: datetime | None = None


class IngestAck(BaseModel):
    event_id: str
    status: str
    normalized: bool
    anomaly_flags: list[str] = Field(default_factory=list)
    latency_ms: float


class IngestHealth(BaseModel):
    status: str
    total_events: int
    total_rejects: int
    active_events: int
    last_ingested_at: datetime | None
    error_rate_pct: float
    reporting_lag_p95_minutes: float | None


class EventNormalizedMessage(BaseModel):
    type: str = "EventNormalized"
    event: NormalizedEvent


class EventClosedMessage(BaseModel):
    type: str = "EventClosed"
    event_id: str
    closed_datetime: datetime | None
    requires_road_closure: bool
    status: str
    payload: dict[str, Any] = Field(default_factory=dict)
