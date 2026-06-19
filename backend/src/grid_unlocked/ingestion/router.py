from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db.session import get_session
from grid_unlocked.ingestion.schemas import IngestAck, IngestHealth, IngestSource, NormalizedEvent
from grid_unlocked.ingestion.service import IngestionService

router = APIRouter(prefix="/ingest", tags=["ingestion"])


async def _ingest(
    payload: dict[str, Any],
    source: IngestSource,
    session: AsyncSession,
) -> IngestAck:
    service = IngestionService(session)
    result = await service.ingest(payload, source=source)
    if isinstance(result, tuple):
        _, reason = result
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=reason)
    return result


@router.post("/astram", response_model=IngestAck)
async def ingest_astram(
    payload: dict[str, Any],
    session: AsyncSession = Depends(get_session),
) -> IngestAck:
    return await _ingest(payload, IngestSource.ASTRAM, session)


@router.post("/planned", response_model=IngestAck)
async def ingest_planned(
    payload: dict[str, Any],
    session: AsyncSession = Depends(get_session),
) -> IngestAck:
    payload = {**payload, "event_type": payload.get("event_type", "planned")}
    return await _ingest(payload, IngestSource.PLANNED_PORTAL, session)


@router.post("/field", response_model=IngestAck)
async def ingest_field(
    payload: dict[str, Any],
    session: AsyncSession = Depends(get_session),
) -> IngestAck:
    return await _ingest(payload, IngestSource.FIELD, session)


@router.post("/citizen", response_model=IngestAck)
async def ingest_citizen(
    payload: dict[str, Any],
    session: AsyncSession = Depends(get_session),
) -> IngestAck:
    return await _ingest(payload, IngestSource.CITIZEN, session)


events_router = APIRouter(tags=["events"])


@events_router.get("/events/{event_id}", response_model=NormalizedEvent)
async def get_event(
    event_id: str,
    session: AsyncSession = Depends(get_session),
) -> NormalizedEvent:
    service = IngestionService(session)
    event = await service.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="event not found")
    return event


health_router = APIRouter(tags=["health"])


@health_router.get("/health/ingest", response_model=IngestHealth)
async def ingest_health(session: AsyncSession = Depends(get_session)) -> IngestHealth:
    service = IngestionService(session)
    return await service.health()
