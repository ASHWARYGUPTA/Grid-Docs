from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db.session import get_session
from grid_unlocked.field.schemas import (
    AckRequest,
    AckResponse,
    ClosureRequest,
    ClosureResponse,
    FieldPacket,
)
from grid_unlocked.field.service import FieldService
from grid_unlocked.governance.schemas import GovernanceTierResponse

router = APIRouter(prefix="/field", tags=["field"])


async def _service(session: AsyncSession = Depends(get_session)) -> FieldService:
    return FieldService(session)


@router.get("/packet/{recommendation_id}", response_model=FieldPacket)
async def get_packet(
    recommendation_id: str, service: FieldService = Depends(_service)
) -> FieldPacket:
    return await service.get_packet(recommendation_id)


@router.post("/ack/{recommendation_id}", response_model=AckResponse)
async def ack(
    recommendation_id: str, body: AckRequest, service: FieldService = Depends(_service)
) -> AckResponse:
    return await service.ack(recommendation_id, body.officer_id)


@router.post("/close/{event_id}", response_model=ClosureResponse)
async def close(
    event_id: str, body: ClosureRequest, service: FieldService = Depends(_service)
) -> ClosureResponse:
    return await service.close(event_id, body)


@router.get("/tier", response_model=GovernanceTierResponse)
async def tier(service: FieldService = Depends(_service)) -> GovernanceTierResponse:
    return await service.get_tier()
