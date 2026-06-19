from datetime import datetime

from pydantic import BaseModel, Field


class FeatureVector(BaseModel):
    event_id: str
    graph_node_id: str

    # Temporal (IST)
    hour_ist: int
    dow: int
    hour_sin: float
    hour_cos: float
    dow_sin: float
    dow_cos: float
    is_peak_hour: bool
    is_weekend: bool
    reporting_bias_weight: float

    # Graph / spatial
    betweenness_norm: float
    degree_norm: float
    h3_res7: str
    h3_res9: str
    is_named_corridor: bool

    # Historical priors (leakage-safe)
    corridor_cause_closure_rate: float
    corridor_cause_median_ict_h: float
    duration_prior_h: float
    cause_median_resolution_global_h: float
    low_confidence_priors: bool = False

    # Vehicle / context
    veh_complexity_score: float
    simultaneous_events_2km: int

    materialized_at: datetime
    cache_hit: bool = False


class FeatureBatchRequest(BaseModel):
    event_ids: list[str] = Field(min_length=1, max_length=100)


class CorridorCausePrior(BaseModel):
    corridor: str
    cause: str
    closure_rate: float
    median_ict_h: float
    sample_count: int


class GraphCentrality(BaseModel):
    node_id: str
    betweenness: float
    betweenness_norm: float
    degree: int
    degree_norm: float
    corridor: str | None = None
    edge_weights: list[dict[str, float | str]] = Field(default_factory=list)


class GraphNeighbors(BaseModel):
    node_id: str
    hops: int
    nodes: list[GraphCentrality]
