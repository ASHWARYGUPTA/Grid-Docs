from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db.session import get_session
from grid_unlocked.impact.schemas import (
    FeatureExplanation,
    ImpactBatchRequest,
    ImpactScore,
    ImpactScoreRequest,
    ModelVersions,
)
from grid_unlocked.impact.service import ImpactService

router = APIRouter(prefix="/impact", tags=["impact"])
models_router = APIRouter(prefix="/models", tags=["models"])


async def _service(session: AsyncSession = Depends(get_session)) -> ImpactService:
    return ImpactService(session)


@router.post("/score", response_model=ImpactScore)
async def score_impact(
    body: ImpactScoreRequest,
    service: ImpactService = Depends(_service),
) -> ImpactScore:
    return await service.score(body.event_id)


@router.post("/score/batch", response_model=list[ImpactScore])
async def score_impact_batch(
    body: ImpactBatchRequest,
    service: ImpactService = Depends(_service),
) -> list[ImpactScore]:
    return await service.score_batch(body.event_ids)


@router.get("/explain/{event_id}", response_model=FeatureExplanation)
async def explain_impact(
    event_id: str,
    service: ImpactService = Depends(_service),
) -> FeatureExplanation:
    return await service.explain(event_id)


@models_router.get("/versions", response_model=ModelVersions)
async def model_versions() -> ModelVersions:
    from grid_unlocked.impact.registry import registry

    registry.load()
    v = registry.versions
    return ModelVersions(closure=v["closure"], ict=v["ict"], source=v["source"])
