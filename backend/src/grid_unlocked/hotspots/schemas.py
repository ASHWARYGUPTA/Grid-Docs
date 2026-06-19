from enum import StrEnum

from pydantic import BaseModel, Field


class HotspotLayer(StrEnum):
    OBSERVED = "observed"
    PREDICTED = "predicted"


class HotspotCluster(BaseModel):
    cluster_id: str
    layer: HotspotLayer
    centroid_lat: float
    centroid_lon: float
    density: int
    cause_entropy: float
    h3_cells: list[str]
    corridors: list[str]
    persistence_score: float = 0.0
    label: str | None = None


class ObservedHotspotsResponse(BaseModel):
    clusters: list[HotspotCluster]
    refreshed_at: str
    latency_ms: float
    source: str


class PredictedZoneForecast(BaseModel):
    corridor: str
    zone: str | None = None
    expected_count: float
    baseline_count: float
    lift_pct: float


class PredictedHotspotsResponse(BaseModel):
    horizon_hours: int
    forecasts: list[PredictedZoneForecast]
    refreshed_at: str
    latency_ms: float
    source: str


class AnomalyAlert(BaseModel):
    alert_id: str
    corridor: str
    zone: str | None = None
    observed_rate_per_hour: float
    baseline_rate_per_hour: float
    sigma: float
    detected_at: str


class AnomaliesResponse(BaseModel):
    alerts: list[AnomalyAlert]
    window_hours: int = 24


class CellHistorySummary(BaseModel):
    h3_res7: str
    total_events: int
    events_30d: int
    persistence_score: float
    top_causes: list[dict[str, int | str]]
    top_corridors: list[dict[str, int | str]]
    centroid_lat: float
    centroid_lon: float
