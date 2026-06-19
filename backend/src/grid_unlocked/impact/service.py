import time
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.features.service import FeatureService
from grid_unlocked.impact.registry import registry
from grid_unlocked.impact.repository import ImpactRepository
from grid_unlocked.impact.schemas import (
    FeatureExplanation,
    ImpactScore,
    ModelVersions,
    SeverityBand,
)


class ImpactService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.features = FeatureService(session)
        self.repo = ImpactRepository(session)

    async def score(self, event_id: str) -> ImpactScore:
        event_row = await self.features.repo.get_event_row(event_id)
        if not event_row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Event {event_id} not found")

        features = await self.features.get_features(event_id)
        if not features:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Features not materialized for {event_id}",
            )

        t0 = time.perf_counter()
        result = registry.score(
            features,
            is_planned=event_row.is_planned,
            event_cause=event_row.event_cause,
            corridor=event_row.corridor,
        )
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        await self.repo.log_score(event_id, result)

        return ImpactScore(
            event_id=event_id,
            p_closure=result.p_closure,
            ict_p20_h=result.ict_p20_h,
            ict_p50_h=result.ict_p50_h,
            ict_p80_h=result.ict_p80_h,
            rci=result.rci,
            severity_band=SeverityBand(result.severity_band),
            priority_structural=features.is_named_corridor,
            staging_recommended=result.staging_recommended,
            model_versions=ModelVersions(
                closure=result.closure_version,
                ict=result.ict_version,
                source=result.source,
            ),
            latency_ms=latency_ms,
            scored_at=datetime.now(UTC),
        )

    async def score_batch(self, event_ids: list[str]) -> list[ImpactScore]:
        scores: list[ImpactScore] = []
        for event_id in event_ids:
            try:
                scores.append(await self.score(event_id))
            except HTTPException:
                continue
        return scores

    async def explain(self, event_id: str) -> FeatureExplanation:
        event_row = await self.features.repo.get_event_row(event_id)
        if not event_row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Event {event_id} not found")

        features = await self.features.get_features(event_id)
        if not features:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Features not materialized for {event_id}",
            )

        top = registry.explain(
            features,
            is_planned=event_row.is_planned,
            event_cause=event_row.event_cause,
            corridor=event_row.corridor,
        )
        versions = registry.versions
        return FeatureExplanation(
            event_id=event_id,
            top_features=top,
            model_version=versions["closure"],
        )

    def get_model_versions(self) -> ModelVersions:
        v = registry.versions
        return ModelVersions(closure=v["closure"], ict=v["ict"], source=v["source"])
