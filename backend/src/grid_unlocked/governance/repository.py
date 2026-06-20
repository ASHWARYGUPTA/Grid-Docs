"""M14 — GovernanceRepository.

Handles DB reads/writes for governance_state (singleton), tier_transitions
(immutable audit), and drill_results.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db.models import (
    DrillResultRow,
    GovernanceStateRow,
    TierTransitionRow,
)

_SINGLETON_ID = 1


class GovernanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # governance_state singleton
    # ------------------------------------------------------------------

    async def get_state(self) -> GovernanceStateRow | None:
        return await self.session.get(GovernanceStateRow, _SINGLETON_ID)

    async def ensure_seeded(self, *, default_tier: str, default_shadow_mode: bool) -> GovernanceStateRow:
        row = await self.get_state()
        if row:
            return row
        row = GovernanceStateRow(
            id=_SINGLETON_ID,
            tier=default_tier,
            shadow_mode=default_shadow_mode,
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def update_state(
        self,
        *,
        tier: str | None = None,
        shadow_mode: bool | None = None,
        updated_by: str | None = None,
    ) -> GovernanceStateRow:
        row = await self.get_state()
        if not row:
            row = GovernanceStateRow(id=_SINGLETON_ID, tier="1", shadow_mode=True)
            self.session.add(row)
        if tier is not None:
            row.tier = tier
        if shadow_mode is not None:
            row.shadow_mode = shadow_mode
        row.updated_by = updated_by
        row.updated_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    # ------------------------------------------------------------------
    # tier_transitions (immutable)
    # ------------------------------------------------------------------

    async def log_transition(
        self,
        *,
        from_tier: str,
        to_tier: str,
        reason: str,
        operator_id: str | None,
    ) -> TierTransitionRow:
        row = TierTransitionRow(
            from_tier=from_tier,
            to_tier=to_tier,
            reason=reason,
            operator_id=operator_id,
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def list_transitions(self, limit: int = 50) -> list[TierTransitionRow]:
        rows = await self.session.scalars(
            select(TierTransitionRow).order_by(TierTransitionRow.created_at.desc()).limit(limit)
        )
        return list(rows.all())

    # ------------------------------------------------------------------
    # drill_results
    # ------------------------------------------------------------------

    async def save_drill(
        self, *, drill_type: str, result: dict, passed: bool
    ) -> DrillResultRow:
        row = DrillResultRow(
            drill_type=drill_type,
            result_json=json.dumps(result),
            passed=passed,
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get_last_drill(self, drill_type: str = "cascade") -> DrillResultRow | None:
        return await self.session.scalar(
            select(DrillResultRow)
            .where(DrillResultRow.drill_type == drill_type)
            .order_by(DrillResultRow.created_at.desc())
            .limit(1)
        )
