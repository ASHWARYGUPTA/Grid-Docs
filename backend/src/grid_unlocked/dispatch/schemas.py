from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class EquipType(StrEnum):
    PATROL = "patrol"
    HEAVY_TOW = "heavy_tow"
    TRAFFIC = "traffic"


class DispatchSource(StrEnum):
    MILP = "MILP"
    GREEDY_FALLBACK = "GREEDY_FALLBACK"


class GovernanceTier(StrEnum):
    TIER1 = "1"
    TIER2 = "2"
    TIER3 = "3"


class DispatchUnit(BaseModel):
    unit_id: str
    station_id: str
    station_name: str
    equip_type: EquipType
    latitude: float
    longitude: float
    on_shift: bool = True


class UnitOverride(BaseModel):
    unit_id: str
    station_id: str
    equip_type: EquipType
    latitude: float
    longitude: float
    station_name: str = "override"


class RecommendRequest(BaseModel):
    event_id: str
    active_incident_ids: list[str] | None = None
    available_units: list[UnitOverride] | None = None
    tier: GovernanceTier = GovernanceTier.TIER1
    force_greedy: bool = False


class Assignment(BaseModel):
    unit_id: str
    station_id: str
    event_id: str
    equip_type: EquipType
    eta_min: float
    pair_cost: float
    rci: float
    cascade_risk: float
    needs_heavy_tow: bool


class AstramShadowCompare(BaseModel):
    event_id: str
    astram_priority: str | None
    astram_rank: int
    grid_rci_rank: int
    priority_structural: bool


class DispatchRecommendation(BaseModel):
    recommendation_id: str
    source: DispatchSource
    assignments: list[Assignment]
    tier_at_decision: GovernanceTier
    solver_ms: float
    latency_ms: float
    milp_attempted: bool
    milp_feasible: bool | None = None
    late_milp_logged: bool = False
    roster_stale: bool = False
    astram_shadow: list[AstramShadowCompare] = Field(default_factory=list)
    created_at: datetime


class DispatchStatus(BaseModel):
    recommendation_id: str
    source: DispatchSource
    complete: bool
    solver_ms: float | None = None
    late_milp_logged: bool = False
