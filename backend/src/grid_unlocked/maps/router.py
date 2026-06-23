from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db.session import get_session
from grid_unlocked.maps.schemas import ActiveIncidentsResponse, CorridorsResponse
from grid_unlocked.maps.service import MapsService

router = APIRouter(prefix="/api/v1", tags=["maps"])


async def _service(session: AsyncSession = Depends(get_session)) -> MapsService:
    return MapsService(session)


@router.get("/incidents/active", response_model=ActiveIncidentsResponse)
async def incidents_active(
    limit: int = Query(default=100, ge=1, le=500),
    service: MapsService = Depends(_service),
) -> ActiveIncidentsResponse:
    return await service.active_incidents(limit=limit)


@router.get("/corridors", response_model=CorridorsResponse)
async def corridors(
    service: MapsService = Depends(_service),
) -> CorridorsResponse:
    return await service.corridors()
