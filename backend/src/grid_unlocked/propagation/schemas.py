from pydantic import BaseModel, Field


class GcdhParams(BaseModel):
    lambda_: float = Field(alias="lambda", serialization_alias="lambda")
    k: float
    epsilon: float
    max_hops: int

    model_config = {"populate_by_name": True}


class RippleRequest(BaseModel):
    event_id: str
    seed_rci: float | None = None
    max_hops: int | None = Field(default=None, ge=1, le=5)
    epsilon: float | None = Field(default=None, ge=0.001, le=0.1)


class PropagationNode(BaseModel):
    node_id: str
    corridor: str | None = None
    risk: float
    hop: int
    parent_edge: str | None = None


class PropagationMap(BaseModel):
    event_id: str
    seed_node_id: str
    seed_rci: float
    nodes: list[PropagationNode]
    cascade_risk: float
    gcdh_params: GcdhParams
    latency_ms: float
