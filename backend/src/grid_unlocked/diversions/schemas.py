from pydantic import BaseModel, Field


class RouteWaypoint(BaseModel):
    node_id: str
    corridor: str | None = None


class DiversionRoute(BaseModel):
    rank: int
    junction_id: str
    description: str
    route_summary: str
    path: list[str]
    eta_delta_min: float
    capacity_class: str = Field(description="low | medium | high")
    gridlock_cycle_detected: bool = False
    edge_disjoint: bool = True


class AtlasEntry(BaseModel):
    junction_id: str
    source_corridor: str
    closed_node_id: str | None
    routes: list[DiversionRoute]
    cached: bool = True
    latency_ms: float


class ComputeRequest(BaseModel):
    junction_id: str | None = None
    corridor: str | None = None
    closed_node_id: str | None = None
    k: int = Field(default=3, ge=1, le=5)


class ValidateRequest(BaseModel):
    path: list[str] = Field(min_length=1)
    closed_node_id: str | None = None


class ValidateResult(BaseModel):
    valid: bool
    gridlock_cycle_detected: bool
    reenters_closed_zone: bool
    capacity_exceeded: bool
    notes: list[str] = Field(default_factory=list)


class ScenarioResponse(BaseModel):
    event_id: str
    corridor: str | None
    junction_id: str
    p_closure: float
    is_peak_hour: bool
    auto_suggest: bool
    routes: list[DiversionRoute]
    latency_ms: float
