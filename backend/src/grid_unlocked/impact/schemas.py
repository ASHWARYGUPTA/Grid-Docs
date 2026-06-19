from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class SeverityBand(StrEnum):
    GREEN = "Green"
    YELLOW = "Yellow"
    ORANGE = "Orange"
    RED = "Red"


class ImpactScoreRequest(BaseModel):
    event_id: str


class ImpactBatchRequest(BaseModel):
    event_ids: list[str] = Field(min_length=1, max_length=50)


class ModelVersions(BaseModel):
    closure: str
    ict: str
    source: str


class ImpactScore(BaseModel):
    event_id: str
    p_closure: float
    ict_p20_h: float
    ict_p50_h: float
    ict_p80_h: float
    rci: float
    severity_band: SeverityBand
    priority_structural: bool
    staging_recommended: bool
    model_versions: ModelVersions
    latency_ms: float
    scored_at: datetime


class FeatureExplanation(BaseModel):
    event_id: str
    top_features: list[dict[str, float | str]]
    model_version: str
