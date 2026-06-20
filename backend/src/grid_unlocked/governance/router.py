"""M14 — GovernanceConsole Router.

Public endpoints:
  GET  /governance/tier                       — current tier + shadow mode
  POST /governance/override-tier              — admin manual tier override
  POST /governance/shadow-mode                 — admin shadow mode toggle
  GET  /governance/transitions                 — tier change audit log
  GET  /governance/health                      — per-module health rollup
  GET  /governance/promotion/checklist/{ver}   — M13 promotion checklist
  POST /governance/promotion/approve           — sign-off (requires complete checklist)
  POST /governance/drills/cascade              — trigger a cascade drill
  GET  /governance/drills/cascade/last         — last drill result
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db.session import get_session
from grid_unlocked.governance.schemas import (
    DrillRequest,
    DrillResult,
    GovernanceTierResponse,
    HealthRollup,
    OverrideTierRequest,
    PromotionApproveRequest,
    PromotionApproveResponse,
    PromotionChecklistResponse,
    ShadowModeRequest,
    TierTransitionsResponse,
)
from grid_unlocked.governance.service import GovernanceService

router = APIRouter(prefix="/governance", tags=["governance"])


async def _service(session: AsyncSession = Depends(get_session)) -> GovernanceService:
    return GovernanceService(session)


@router.get("/tier", response_model=GovernanceTierResponse)
async def get_tier(service: GovernanceService = Depends(_service)) -> GovernanceTierResponse:
    return await service.get_tier()


@router.post("/override-tier", response_model=GovernanceTierResponse)
async def override_tier(
    req: OverrideTierRequest, service: GovernanceService = Depends(_service)
) -> GovernanceTierResponse:
    """Manual tier override with mandatory reason + operator_id (immutable audit)."""
    return await service.override_tier(req.tier, req.reason, req.operator_id)


@router.post("/shadow-mode", response_model=GovernanceTierResponse)
async def set_shadow_mode(
    req: ShadowModeRequest, service: GovernanceService = Depends(_service)
) -> GovernanceTierResponse:
    return await service.set_shadow_mode(req.enabled, req.operator_id)


@router.get("/transitions", response_model=TierTransitionsResponse)
async def list_transitions(
    limit: int = 50, service: GovernanceService = Depends(_service)
) -> TierTransitionsResponse:
    return await service.list_transitions(limit=limit)


@router.get("/health", response_model=HealthRollup)
async def health(service: GovernanceService = Depends(_service)) -> HealthRollup:
    return await service.health()


@router.get("/promotion/checklist/{model_version}", response_model=PromotionChecklistResponse)
async def promotion_checklist(
    model_version: str, service: GovernanceService = Depends(_service)
) -> PromotionChecklistResponse:
    return await service.promotion_checklist(model_version)


@router.post("/promotion/approve", response_model=PromotionApproveResponse)
async def approve_promotion(
    req: PromotionApproveRequest, service: GovernanceService = Depends(_service)
) -> PromotionApproveResponse:
    return await service.approve_promotion(req)


@router.post("/drills/cascade", response_model=DrillResult)
async def run_cascade_drill(
    req: DrillRequest = DrillRequest(), service: GovernanceService = Depends(_service)
) -> DrillResult:
    return await service.run_cascade_drill(req)


@router.get("/drills/cascade/last", response_model=DrillResult)
async def last_cascade_drill(service: GovernanceService = Depends(_service)) -> DrillResult:
    result = await service.last_drill("cascade")
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No drills have been run yet")
    return result
