"""M14 governance stub — tier and shadow flags until GovernanceConsole ships."""

from __future__ import annotations

from dataclasses import dataclass

from grid_unlocked.config import settings


@dataclass(frozen=True)
class GovernanceState:
    tier: str
    shadow_mode: bool
    manual_mode: bool


def get_governance() -> GovernanceState:
    return GovernanceState(
        tier=settings.governance_tier,
        shadow_mode=settings.governance_shadow_mode,
        manual_mode=settings.governance_tier == "3",
    )
