from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db.session import get_session
from grid_unlocked.dispatch.schemas import DispatchRecommendation, DispatchStatus, RecommendRequest
from grid_unlocked.dispatch.service import DispatchService

router = APIRouter(prefix="/dispatch", tags=["dispatch"])


async def _service(session: AsyncSession = Depends(get_session)) -> DispatchService:
    return DispatchService(session)


@router.post("/recommend", response_model=DispatchRecommendation)
async def dispatch_recommend(
    body: RecommendRequest,
    service: DispatchService = Depends(_service),
) -> DispatchRecommendation:
    return await service.recommend(body)


@router.get("/status/{recommendation_id}", response_model=DispatchStatus)
async def dispatch_status(
    recommendation_id: str,
    service: DispatchService = Depends(_service),
) -> DispatchStatus:
    return await service.status(recommendation_id)


@router.get("/roster")
async def dispatch_roster(service: DispatchService = Depends(_service)) -> dict:
    return service.list_roster()
