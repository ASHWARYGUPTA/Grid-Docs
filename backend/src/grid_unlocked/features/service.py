from grid_unlocked.features.cache import feature_cache
from grid_unlocked.features.graph_stub import get_centrality, get_neighbors
from grid_unlocked.features.materializer import materialize_features
from grid_unlocked.features.priors_loader import priors_need_seed, seed_priors_from_csv
from grid_unlocked.features.repository import FeatureRepository
from grid_unlocked.features.schemas import (
    CorridorCausePrior,
    FeatureVector,
    GraphCentrality,
    GraphNeighbors,
)
from grid_unlocked.ingestion.repository import row_to_schema
from grid_unlocked.ingestion.schemas import EventClosedMessage, EventNormalizedMessage, NormalizedEvent
from sqlalchemy.ext.asyncio import AsyncSession


class FeatureService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = FeatureRepository(session)

    async def ensure_priors_seeded(self) -> dict[str, int] | None:
        if await priors_need_seed(self.session):
            return await seed_priors_from_csv(self.session)
        return None

    async def on_event_normalized(self, message: EventNormalizedMessage) -> FeatureVector:
        features = await self.materialize_and_cache(message.event)
        return features

    async def on_event_closed(self, message: EventClosedMessage) -> None:
        await feature_cache.delete(message.event_id)

    async def materialize_and_cache(self, event: NormalizedEvent) -> FeatureVector:
        features = await materialize_features(event, self.repo)
        await feature_cache.set(features)
        await self.repo.save_snapshot(features)
        return features

    async def get_features(self, event_id: str) -> FeatureVector | None:
        cached = await feature_cache.get(event_id)
        if cached:
            return cached

        row = await self.repo.get_event_row(event_id)
        if not row:
            snapshot = await self.repo.get_snapshot(event_id)
            return snapshot

        event = row_to_schema(row)
        return await self.materialize_and_cache(event)

    async def get_features_batch(self, event_ids: list[str]) -> list[FeatureVector]:
        results: list[FeatureVector] = []
        for event_id in event_ids:
            fv = await self.get_features(event_id)
            if fv:
                results.append(fv)
        return results

    async def get_prior(self, corridor: str, cause: str) -> CorridorCausePrior | None:
        prior = await self.repo.get_corridor_cause_prior_api(corridor, cause)
        if prior:
            return prior
        closure, ict, count, _ = await self.repo.get_corridor_cause_prior(corridor, cause)
        return CorridorCausePrior(
            corridor=corridor,
            cause=cause,
            closure_rate=closure,
            median_ict_h=ict,
            sample_count=count,
        )

    def get_graph_centrality(self, node_id: str) -> GraphCentrality:
        return get_centrality(node_id)

    def get_graph_neighbors(self, node_id: str, hops: int) -> GraphNeighbors:
        return get_neighbors(node_id, hops=hops)
