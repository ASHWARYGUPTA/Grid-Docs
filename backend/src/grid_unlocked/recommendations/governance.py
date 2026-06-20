"""Synchronous governance read used by every hot path (M07/M09/M10/M11).

Backed by M14 GovernanceConsole's in-process cache (grid_unlocked.governance.service),
which mirrors the durable `governance_state` DB row. No I/O here by design —
every caller in this codebase calls get_governance() synchronously with no
session, so the cache (not the DB) is the read path. If M14 has never written
to the cache (e.g. before app startup bootstrap), the cache defaults to
Tier 3 + shadow_mode=True — the spec's documented last-resort degradation
behavior ("M14 itself is Tier 3 last-resort").
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GovernanceState:
    tier: str
    shadow_mode: bool
    manual_mode: bool


def get_governance() -> GovernanceState:
    from grid_unlocked.governance.service import read_cached_state

    cached = read_cached_state()
    return GovernanceState(
        tier=cached.tier,
        shadow_mode=cached.shadow_mode,
        manual_mode=cached.manual_mode,
    )
