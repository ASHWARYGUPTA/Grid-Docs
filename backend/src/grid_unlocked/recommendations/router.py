from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db.session import get_session
from grid_unlocked.recommendations.schemas import (
    ActionCard,
    ApprovalResult,
    ApproveRequest,
    CardMode,
    QueueResponse,
    RejectRequest,
)
from grid_unlocked.recommendations.service import RecommendationService

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


async def _service(session: AsyncSession = Depends(get_session)) -> RecommendationService:
    return RecommendationService(session)


@router.get("/queue", response_model=QueueResponse)
async def recommendation_queue(
    severity: str | None = Query(default=None, alias="severity"),
    service: RecommendationService = Depends(_service),
) -> QueueResponse:
    return await service.queue(severity_min=severity)


@router.get("/{event_id}", response_model=ActionCard)
async def get_recommendation(
    event_id: str,
    mode: CardMode = Query(default=CardMode.COMPLETE),
    refresh: bool = Query(default=False),
    service: RecommendationService = Depends(_service),
) -> ActionCard:
    return await service.build_card(event_id, mode=mode, refresh=refresh)


@router.post("/{event_id}/refresh", response_model=ActionCard)
async def refresh_recommendation(
    event_id: str,
    mode: CardMode = Query(default=CardMode.COMPLETE),
    service: RecommendationService = Depends(_service),
) -> ActionCard:
    return await service.build_card(event_id, mode=mode, refresh=True)


@router.post("/{card_id}/approve", response_model=ApprovalResult)
async def approve_recommendation(
    card_id: str,
    body: ApproveRequest,
    service: RecommendationService = Depends(_service),
) -> ApprovalResult:
    return await service.approve(card_id, body.commander_id, body.override_codes)


@router.post("/{card_id}/reject", response_model=ApprovalResult)
async def reject_recommendation(
    card_id: str,
    body: RejectRequest,
    service: RecommendationService = Depends(_service),
) -> ApprovalResult:
    return await service.reject(card_id, body.commander_id, body.reason_code, body.notes)
