from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.config import settings
from grid_unlocked.features.service import FeatureService
from grid_unlocked.impact.registry import registry
from grid_unlocked.propagation.cache import propagation_cache
from grid_unlocked.propagation.gcdh import run_gcdh
from grid_unlocked.propagation.schemas import GcdhParams, PropagationMap, RippleRequest


class PropagationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.features = FeatureService(session)

    def default_params(self, max_hops: int | None = None, epsilon: float | None = None) -> GcdhParams:
        return GcdhParams(
            **{
                "lambda": settings.gcdh_lambda,
                "k": settings.gcdh_k,
                "epsilon": epsilon if epsilon is not None else settings.gcdh_epsilon,
                "max_hops": max_hops if max_hops is not None else settings.gcdh_max_hops,
            }
        )

    async def ripple(self, request: RippleRequest) -> PropagationMap:
        event_row = await self.features.repo.get_event_row(request.event_id)
        if not event_row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Event {request.event_id} not found")

        features = await self.features.get_features(request.event_id)
        if not features:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Features not materialized for {request.event_id}",
            )

        seed_rci = request.seed_rci
        if seed_rci is None:
            scored = registry.score(
                features,
                is_planned=event_row.is_planned,
                event_cause=event_row.event_cause,
                corridor=event_row.corridor,
            )
            seed_rci = scored.rci

        params = self.default_params(max_hops=request.max_hops, epsilon=request.epsilon)
        pmap = run_gcdh(
            event_id=request.event_id,
            seed_node_id=features.graph_node_id,
            seed_rci=seed_rci,
            params=params,
        )
        await propagation_cache.set(pmap)
        return pmap

    async def get_active(self) -> list[PropagationMap]:
        return await propagation_cache.list_active()

    async def on_event_closed(self, event_id: str) -> None:
        await propagation_cache.delete(event_id)
