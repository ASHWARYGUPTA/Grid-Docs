from datetime import datetime

from pydantic import BaseModel, Field


class ChecklistItem(BaseModel):
    id: str
    category: str
    description: str
    required: bool = True


class AnalogEvent(BaseModel):
    event_id: str
    corridor: str | None
    cause: str
    closure: bool
    ict_h: float | None
    start_datetime: datetime | None


class DiversionRef(BaseModel):
    junction_id: str
    description: str
    route_summary: str
    rank: int


class ImpactOverlay(BaseModel):
    p_closure: float
    ict_p20_h: float
    ict_p50_h: float
    ict_p80_h: float
    rci: float
    severity_band: str
    severity_ordinal: int
    source: str


class TemplateDefinition(BaseModel):
    template_id: str
    cause: str
    corridor: str | None = None
    dow_mask: list[int] = Field(default_factory=list)
    hour_bin: str
    duration_class: str
    staffing_min: int
    staffing_max: int
    barricade_count: int
    barricade_matrix_ref: str
    deployment_lead_time_hours: int
    checklist: list[ChecklistItem]


class PackageRequest(BaseModel):
    event_id: str
    force_refresh: bool = False


class PlannedEventPackage(BaseModel):
    event_id: str
    template_id: str
    cause: str
    corridor: str | None
    hours_until_start: float
    estimated_duration_h: float | None
    staffing_min: int
    staffing_max: int
    barricade_count: int
    barricade_staging_required: bool
    deployment_lead_time_hours: int
    checklist: list[ChecklistItem]
    analog_events: list[AnalogEvent]
    diversion_refs: list[DiversionRef]
    impact_overlay: ImpactOverlay
    compliance_items: list[str]
    low_confidence_template: bool = False
    cached: bool = False
    latency_ms: float
    generated_at: datetime
