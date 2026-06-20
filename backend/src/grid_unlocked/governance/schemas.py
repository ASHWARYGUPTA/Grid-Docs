"""M14 — GovernanceConsole Schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Tier(StrEnum):
    TIER1 = "1"
    TIER2 = "2"
    TIER3 = "3"


# ---------------------------------------------------------------------------
# Tier / shadow mode
# ---------------------------------------------------------------------------


class GovernanceTierResponse(BaseModel):
    """Response for GET /governance/tier."""

    tier: Tier
    shadow_mode: bool
    manual_mode: bool
    flags: dict[str, bool] = Field(default_factory=dict)
    updated_at: datetime
    updated_by: str | None = None


class OverrideTierRequest(BaseModel):
    tier: Tier
    reason: str
    operator_id: str


class ShadowModeRequest(BaseModel):
    enabled: bool
    operator_id: str


class TierTransition(BaseModel):
    id: int
    from_tier: Tier
    to_tier: Tier
    reason: str
    operator_id: str | None  # None = automatic transition
    created_at: datetime


class TierTransitionsResponse(BaseModel):
    transitions: list[TierTransition]
    count: int


# ---------------------------------------------------------------------------
# Health rollup
# ---------------------------------------------------------------------------


class ModuleHealth(BaseModel):
    module: str
    status: str  # healthy | degraded | down
    detail: str
    metrics: dict[str, float | int | str | bool] = Field(default_factory=dict)


class HealthRollup(BaseModel):
    overall_status: str  # healthy | degraded | down
    tier: Tier
    shadow_mode: bool
    modules: list[ModuleHealth]
    checked_at: datetime


# ---------------------------------------------------------------------------
# Promotion checklist (M13 sign-off — stubbed until M13 exists)
# ---------------------------------------------------------------------------


class PromotionChecklistItem(BaseModel):
    item: str
    complete: bool
    detail: str


class PromotionChecklistResponse(BaseModel):
    model_version: str
    items: list[PromotionChecklistItem]
    all_complete: bool


class PromotionApproveRequest(BaseModel):
    model_version: str
    operator_id: str


class PromotionApproveResponse(BaseModel):
    model_version: str
    approved: bool
    message: str


# ---------------------------------------------------------------------------
# Cascade drills
# ---------------------------------------------------------------------------


class DrillRequest(BaseModel):
    drill_type: str = "cascade"
    concurrent_closures: int = Field(default=5, ge=1, le=20)
    force_milp_timeout: bool = True


class DrillResult(BaseModel):
    id: int
    drill_type: str
    passed: bool
    concurrent_closures: int
    fallback_rate: float
    max_latency_ms: float
    deadline_ms: int
    detail: str
    created_at: datetime
