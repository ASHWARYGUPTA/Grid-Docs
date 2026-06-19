from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db.models import ImpactScoreRow
from grid_unlocked.impact.registry import ScoreResult


class ImpactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def log_score(self, event_id: str, result: ScoreResult) -> None:
        self.session.add(
            ImpactScoreRow(
                event_id=event_id,
                p_closure=result.p_closure,
                ict_p20_h=result.ict_p20_h,
                ict_p50_h=result.ict_p50_h,
                ict_p80_h=result.ict_p80_h,
                rci=result.rci,
                severity_band=result.severity_band,
                source=result.source,
                closure_model_version=result.closure_version,
                ict_model_version=result.ict_version,
                staging_recommended=result.staging_recommended,
                scored_at=datetime.now(UTC),
            )
        )
        await self.session.commit()
