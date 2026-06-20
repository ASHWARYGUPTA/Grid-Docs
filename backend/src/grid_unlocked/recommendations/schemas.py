from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from grid_unlocked.diversions.schemas import DiversionRoute
from grid_unlocked.dispatch.schemas import Assignment, DispatchSource
from grid_unlocked.impact.schemas import ImpactScore, ModelVersions, SeverityBand


class CardStatus(StrEnum):
    PARTIAL = "partial"
    COMPLETE = "complete"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"


class AlertPriority(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class CardMode(StrEnum):
    SKELETON = "skeleton"
    COMPLETE = "complete"
    AUTO = "auto"


class PropagationSummary(BaseModel):
    cascade_risk: float
    seed_rci: float
    affected_nodes: int
    max_hop: int


class HotspotContext(BaseModel):
    nearby_cluster_count: int
    cell_event_count_24h: int | None = None
    h3_res7: str | None = None


class DispatchSection(BaseModel):
    recommendation_id: str
    source: DispatchSource
    assignments: list[Assignment]
    solver_ms: float
    provenance: str


class PlannedSection(BaseModel):
    template_id: str
    barricade_count: int
    staffing_min: int
    staffing_max: int
    barricade_staging_required: bool


class GovernanceInfo(BaseModel):
    tier: str
    shadow_mode: bool
    manual_mode: bool = False


class EvidenceBundle(BaseModel):
    top_features: list[dict[str, float | str]]
    model_versions: ModelVersions
    diversion_routes: list[DiversionRoute]


class ActionCard(BaseModel):
    card_id: str
    event_id: str
    status: CardStatus
    alert_priority: AlertPriority
    impact: ImpactScore
    propagation: PropagationSummary
    hotspot_context: HotspotContext
    diversions: list[DiversionRoute]
    auto_suggest_diversion: bool
    dispatch: DispatchSection | None = None
    dispatch_pending: bool = False
    planned: PlannedSection | None = None
    evidence: EvidenceBundle
    governance: GovernanceInfo
    provenance: dict[str, str]
    skeleton_ms: float
    latency_ms: float
    field_packet_link: str | None = None
    created_at: datetime
    updated_at: datetime


class ApproveRequest(BaseModel):
    commander_id: str
    override_codes: list[str] = Field(default_factory=list)


class RejectRequest(BaseModel):
    commander_id: str
    reason_code: str
    notes: str | None = None


class ApprovalResult(BaseModel):
    card_id: str
    action: str
    shadow_mode: bool
    execution_enqueued: bool
    approval_token: str | None = None
    message: str


class QueueItem(BaseModel):
    event_id: str
    card_id: str | None
    rci: float
    p_closure: float
    severity_band: SeverityBand
    alert_priority: AlertPriority
    corridor: str | None
    status: CardStatus | None = None


class QueueResponse(BaseModel):
    items: list[QueueItem]
    count: int
