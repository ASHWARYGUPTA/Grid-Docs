from datetime import datetime

from pydantic import BaseModel, Field


class ActiveIncident(BaseModel):
    event_id: str
    corridor: str | None = None
    junction: str | None = None
    event_type: str
    event_cause: str
    lat: float
    lng: float
    rci: float | None = None
    p_closure: float | None = None
    severity_band: str | None = None
    status: str
    ingested_at: datetime


class ActiveIncidentsResponse(BaseModel):
    incidents: list[ActiveIncident] = Field(default_factory=list)


class CorridorCentroid(BaseModel):
    name: str
    lat: float
    lon: float
    sample_count: int


class CorridorsResponse(BaseModel):
    corridors: list[CorridorCentroid] = Field(default_factory=list)
