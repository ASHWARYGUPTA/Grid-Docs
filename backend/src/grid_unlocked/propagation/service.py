from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.citizen.repository import CitizenRepository
from grid_unlocked.config import settings
from grid_unlocked.features.graph_stub import parse_node_id
from grid_unlocked.features.service import FeatureService
from grid_unlocked.impact.registry import registry
from grid_unlocked.propagation.cache import propagation_cache
from grid_unlocked.propagation.gcdh import run_gcdh
from grid_unlocked.propagation.schemas import GcdhParams, PropagationMap, RippleRequest


class PropagationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.features = FeatureService(session)
        self.citizen_repo = CitizenRepository(session)

    async def _centroid_map(self) -> dict[str, tuple[float, float]]:
        centroids = await self.citizen_repo.get_all_centroids()
        return {name: (lat, lon) for (name, lat, lon) in centroids}

    @staticmethod
    def _enrich_map(
        pmap: PropagationMap, centroid_map: dict[str, tuple[float, float]]
    ) -> PropagationMap:
        enriched_nodes = []
        for node in pmap.nodes:
            corridor = node.corridor or parse_node_id(node.node_id)
            point = centroid_map.get(corridor) if corridor else None
            if point is None:
                enriched_nodes.append(node)
                continue
            lat, lon = point
            enriched_nodes.append(node.model_copy(update={"lat": lat, "lng": lon}))
        return pmap.model_copy(update={"nodes": enriched_nodes})

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
        centroid_map = await self._centroid_map()
        return self._enrich_map(pmap, centroid_map)

    async def get_active(self) -> list[PropagationMap]:
        active = await propagation_cache.list_active()
        if not active:
            from grid_unlocked.db.models import NormalizedEventRow
            from sqlalchemy import select
            
            rows = (
                await self.session.scalars(
                    select(NormalizedEventRow)
                    .where(NormalizedEventRow.status == "active")
                    .order_by(NormalizedEventRow.start_datetime.desc())
                    .limit(50)
                )
            ).all()
            
            for row in rows:
                try:
                    await self.ripple(RippleRequest(event_id=row.event_id))
                except Exception:
                    pass
            active = await propagation_cache.list_active()
            
        if not active:
            return active
        centroid_map = await self._centroid_map()
        return [self._enrich_map(p, centroid_map) for p in active]

    async def on_event_closed(self, event_id: str) -> None:
        await propagation_cache.delete(event_id)
