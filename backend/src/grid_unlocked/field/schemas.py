from datetime import datetime

from pydantic import BaseModel, Field


class FieldAssignmentSummary(BaseModel):
    unit_id: str
    station_id: str
    equip_type: str
    eta_min: float
    rci: float
    cascade_risk: float
    needs_heavy_tow: bool


class FieldDiversionSummary(BaseModel):
    junction_id: str
    description: str
    route_summary: str
    eta_delta_min: float
    capacity_class: str
    available: bool = True


class FieldIctBands(BaseModel):
    ict_p20_h: float
    ict_p50_h: float
    ict_p80_h: float
    severity_band: str


class FieldPacket(BaseModel):
    recommendation_id: str
    event_id: str
    source: str
    tier_at_decision: str
    assignments: list[FieldAssignmentSummary]
    impact: FieldIctBands
    top_diversion: FieldDiversionSummary | None = None
    navigation_deep_link: str
    event_status: str
    already_closed: bool
    acknowledged: bool
    acknowledged_at: datetime | None = None
    provenance: dict[str, str]
    generated_at: datetime


class AckRequest(BaseModel):
    officer_id: str


class AckResponse(BaseModel):
    recommendation_id: str
    acknowledged: bool
    acknowledged_at: datetime


class ClosureRequest(BaseModel):
    closed_datetime: datetime
    barricades_used: int = Field(ge=0)
    officers_used: int = Field(ge=1)
    diversion_activated: bool
    notes: str | None = None
    officer_id: str


class ClosureResponse(BaseModel):
    event_id: str
    closure_id: str
    event_closed: bool
    closed_datetime: datetime
    queued_offline: bool = False
