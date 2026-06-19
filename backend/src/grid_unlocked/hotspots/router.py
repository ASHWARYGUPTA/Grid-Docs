from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db.session import get_session
from grid_unlocked.hotspots.schemas import (
    AnomaliesResponse,
    CellHistorySummary,
    ObservedHotspotsResponse,
    PredictedHotspotsResponse,
)
from grid_unlocked.hotspots.service import HotspotService

router = APIRouter(prefix="/hotspots", tags=["hotspots"])


async def _service(session: AsyncSession = Depends(get_session)) -> HotspotService:
    return HotspotService(session)


@router.get("/observed", response_model=ObservedHotspotsResponse)
async def hotspots_observed(service: HotspotService = Depends(_service)) -> ObservedHotspotsResponse:
    return await service.get_observed()


@router.get("/predicted", response_model=PredictedHotspotsResponse)
async def hotspots_predicted(
    horizon_hours: int = Query(default=4, ge=1, le=24),
    service: HotspotService = Depends(_service),
) -> PredictedHotspotsResponse:
    return await service.get_predicted(horizon_hours)


@router.get("/anomalies", response_model=AnomaliesResponse)
async def hotspots_anomalies(
    window_hours: int = Query(default=24, ge=1, le=168),
    service: HotspotService = Depends(_service),
) -> AnomaliesResponse:
    return service.get_anomalies(window_hours)


@router.get("/cell/{h3_res7}", response_model=CellHistorySummary)
async def hotspot_cell_history(
    h3_res7: str,
    service: HotspotService = Depends(_service),
) -> CellHistorySummary:
    return service.get_cell_history(h3_res7)
