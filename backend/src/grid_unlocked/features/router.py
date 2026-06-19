from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db.session import get_session
from grid_unlocked.features.schemas import (
    CorridorCausePrior,
    FeatureBatchRequest,
    FeatureVector,
    GraphCentrality,
    GraphNeighbors,
)
from grid_unlocked.features.service import FeatureService

router = APIRouter(tags=["features"])


def _service(session: AsyncSession) -> FeatureService:
    return FeatureService(session)


@router.get("/features/{event_id}", response_model=FeatureVector)
async def get_features(
    event_id: str,
    session: AsyncSession = Depends(get_session),
) -> FeatureVector:
    service = _service(session)
    features = await service.get_features(event_id)
    if features is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="features not found")
    return features


@router.post("/features/batch", response_model=list[FeatureVector])
async def get_features_batch(
    body: FeatureBatchRequest,
    session: AsyncSession = Depends(get_session),
) -> list[FeatureVector]:
    service = _service(session)
    return await service.get_features_batch(body.event_ids)


@router.get("/priors/corridor-cause/{corridor}/{cause}", response_model=CorridorCausePrior)
async def get_corridor_cause_prior(
    corridor: str,
    cause: str,
    session: AsyncSession = Depends(get_session),
) -> CorridorCausePrior:
    service = _service(session)
    prior = await service.get_prior(corridor, cause)
    if prior is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="prior not found")
    return prior


@router.get("/graph/centrality/{node_id}", response_model=GraphCentrality)
async def get_graph_centrality(node_id: str) -> GraphCentrality:
    from grid_unlocked.features.graph_stub import get_centrality

    return get_centrality(node_id)


@router.get("/graph/neighbors/{node_id}", response_model=GraphNeighbors)
async def get_graph_neighbors(
    node_id: str,
    hops: int = Query(default=3, ge=1, le=5),
) -> GraphNeighbors:
    from grid_unlocked.features.graph_stub import get_neighbors

    return get_neighbors(node_id, hops=hops)
