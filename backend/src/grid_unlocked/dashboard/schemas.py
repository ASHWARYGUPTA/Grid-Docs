from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class DeltaScope(StrEnum):
    CARD = "card"
    TIER = "tier"
    HOTSPOT = "hotspot"


class DashboardDelta(BaseModel):
    type: str = "dashboard.delta"
    scope: DeltaScope
    event_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    emitted_at: datetime
