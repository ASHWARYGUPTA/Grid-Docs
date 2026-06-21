"""M12 — TransitImpactService Schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AffectedRoute(BaseModel):
    route_id: str
    name: str
    occupancy: int
    predicted_delay_min: float
    overlap_fraction: float


class TransitImpactIndex(BaseModel):
    event_id: str
    corridor: str | None
    tier: str
    degraded: bool
    advisory_only: bool = True
    passenger_delay_index: float
    transfer_overload_risk: float
    affected_routes: list[AffectedRoute]
    advisory_message: str | None = None
    cached: bool
    latency_ms: float
    generated_at: datetime


class AffectedRoutesResponse(BaseModel):
    corridor: str | None
    routes: list[AffectedRoute]


class MockTransitDemoResponse(BaseModel):
    corridor: str
    passenger_delay_index: float
    affected_routes: list[AffectedRoute]
    message: str
