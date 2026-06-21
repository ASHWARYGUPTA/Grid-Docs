"""M13 — ReplayLearningService Router.

Public endpoints:
  POST /learning/retrain                       — trigger a buffer+train+eval job
  GET  /learning/buffer/manifest/{job_id}       — 80/20 stats, stratification table
  GET  /learning/eval/{job_id}                  — accuracy, anchor slice, gate result
  POST /learning/promote/{model_version}        — promote a staged model to production
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db.session import get_session
from grid_unlocked.learning.schemas import (
    BufferManifestResponse,
    EvalResponse,
    LatestJobResponse,
    PromoteRequest,
    PromoteResponse,
    RetrainRequest,
    RetrainResponse,
)
from grid_unlocked.learning.service import LearningService

router = APIRouter(prefix="/learning", tags=["learning"])


async def _service(session: AsyncSession = Depends(get_session)) -> LearningService:
    return LearningService(session)


@router.post("/retrain", response_model=RetrainResponse)
async def retrain(
    req: RetrainRequest = RetrainRequest(),
    service: LearningService = Depends(_service),
) -> RetrainResponse:
    """Build a replay buffer, retrain closure + ICT models, and evaluate
    against the promotion gates. Synchronous — returns once complete."""
    return await service.start_retrain(req.trigger)


@router.get("/jobs/latest", response_model=LatestJobResponse)
async def latest_job(service: LearningService = Depends(_service)) -> LatestJobResponse:
    return await service.get_latest_job()


@router.get("/buffer/manifest/{job_id}", response_model=BufferManifestResponse)
async def buffer_manifest(
    job_id: str, service: LearningService = Depends(_service)
) -> BufferManifestResponse:
    return await service.get_manifest(job_id)


@router.get("/eval/{job_id}", response_model=EvalResponse)
async def eval_result(job_id: str, service: LearningService = Depends(_service)) -> EvalResponse:
    return await service.get_eval(job_id)


@router.post("/promote/{model_version}", response_model=PromoteResponse)
async def promote(
    model_version: str,
    req: PromoteRequest,
    service: LearningService = Depends(_service),
) -> PromoteResponse:
    """Promote a staged model to production — requires gates to pass.
    M14's /governance/promotion/approve is the human sign-off layer on top."""
    return await service.promote(model_version, req.operator_id)
