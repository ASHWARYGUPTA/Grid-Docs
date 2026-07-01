import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db.models import DispatchRecommendationRow, NormalizedEventRow
from grid_unlocked.dispatch.schemas import DispatchRecommendation


class DispatchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_active_event_ids(self, limit: int = 20) -> list[str]:
        rows = (
            await self.session.scalars(
                select(NormalizedEventRow.event_id)
                .where(NormalizedEventRow.status == "active")
                .order_by(NormalizedEventRow.start_datetime.desc())
                .limit(limit)
            )
        ).all()
        return list(rows)

    async def get_event_rows(self, event_ids: list[str]) -> list[NormalizedEventRow]:
        if not event_ids:
            return []
        rows = (
            await self.session.scalars(
                select(NormalizedEventRow).where(NormalizedEventRow.event_id.in_(event_ids))
            )
        ).all()
        by_id = {r.event_id: r for r in rows}
        return [by_id[eid] for eid in event_ids if eid in by_id]

    async def save_recommendation(self, rec: DispatchRecommendation) -> None:
        self.session.add(
            DispatchRecommendationRow(
                recommendation_id=rec.recommendation_id,
                source=rec.source.value,
                tier_at_decision=rec.tier_at_decision.value,
                recommendation_json=rec.model_dump_json(),
                solver_ms=rec.solver_ms,
                latency_ms=rec.latency_ms,
                created_at=rec.created_at,
            )
        )
        await self.session.commit()

    async def get_recommendation(self, recommendation_id: str) -> DispatchRecommendation | None:
        row = await self.session.get(DispatchRecommendationRow, recommendation_id)
        if not row:
            return None
        return DispatchRecommendation.model_validate(json.loads(row.recommendation_json))
