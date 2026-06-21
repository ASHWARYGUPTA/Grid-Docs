"""M12 — TransitImpactService Router.

Public endpoints:
  GET /transit/impact/{event_id}          — TransitImpactIndex for an event
  GET /transit/routes/affected?corridor=  — route list with passenger estimates
  GET /mock/transit/demo                  — hackathon demo: canned index
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db.session import get_session
from grid_unlocked.transit.schemas import (
    AffectedRoutesResponse,
    MockTransitDemoResponse,
    TransitImpactIndex,
)
from grid_unlocked.transit.service import TransitImpactService

router = APIRouter(prefix="/transit", tags=["transit"])
mock_router = APIRouter(prefix="/mock", tags=["transit-mock"])


async def _service(session: AsyncSession = Depends(get_session)) -> TransitImpactService:
    return TransitImpactService(session)


@router.get("/impact/{event_id}", response_model=TransitImpactIndex)
async def get_transit_impact(
    event_id: str, service: TransitImpactService = Depends(_service)
) -> TransitImpactIndex:
    """Advisory-only passenger-delay index for the event's corridor."""
    return await service.compute_impact(event_id)


@router.get("/routes/affected", response_model=AffectedRoutesResponse)
async def get_affected_routes(
    corridor: str | None = None, service: TransitImpactService = Depends(_service)
) -> AffectedRoutesResponse:
    """BMTC routes overlapping the given corridor (no event/ICT lookup)."""
    return service.get_affected_routes(corridor)


@mock_router.get("/transit/demo", response_model=MockTransitDemoResponse)
async def mock_transit_demo(
    service: TransitImpactService = Depends(_service),
) -> MockTransitDemoResponse:
    """Hackathon demo endpoint — canned index, no DB/event lookup."""
    return service.get_mock_demo()
