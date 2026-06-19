from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.config import settings
from grid_unlocked.db.session import get_session
from grid_unlocked.propagation.schemas import GcdhParams, PropagationMap, RippleRequest
from grid_unlocked.propagation.service import PropagationService

router = APIRouter(prefix="/propagation", tags=["propagation"])


async def _service(session: AsyncSession = Depends(get_session)) -> PropagationService:
    return PropagationService(session)


@router.post("/ripple", response_model=PropagationMap)
async def propagation_ripple(
    body: RippleRequest,
    service: PropagationService = Depends(_service),
) -> PropagationMap:
    return await service.ripple(body)


@router.get("/active", response_model=list[PropagationMap])
async def propagation_active(
    service: PropagationService = Depends(_service),
) -> list[PropagationMap]:
    return await service.get_active()


@router.get("/config", response_model=GcdhParams)
async def propagation_config() -> GcdhParams:
    return GcdhParams(
        **{
            "lambda": settings.gcdh_lambda,
            "k": settings.gcdh_k,
            "epsilon": settings.gcdh_epsilon,
            "max_hops": settings.gcdh_max_hops,
        }
    )
