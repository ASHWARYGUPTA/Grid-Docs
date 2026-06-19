from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db.session import get_session
from grid_unlocked.diversions.schemas import (
    AtlasEntry,
    ComputeRequest,
    ScenarioResponse,
    ValidateRequest,
    ValidateResult,
)
from grid_unlocked.diversions.service import DiversionService

router = APIRouter(prefix="/diversions", tags=["diversions"])


async def _service(session: AsyncSession = Depends(get_session)) -> DiversionService:
    return DiversionService(session)


@router.get("/atlas/{junction_id}", response_model=AtlasEntry)
async def diversion_atlas(
    junction_id: str,
    service: DiversionService = Depends(_service),
) -> AtlasEntry:
    return service.get_atlas(junction_id)


@router.get("/atlas", response_model=list[str])
async def diversion_atlas_index(service: DiversionService = Depends(_service)) -> list[str]:
    return service.list_junctions()


@router.post("/compute", response_model=AtlasEntry)
async def diversion_compute(
    body: ComputeRequest,
    service: DiversionService = Depends(_service),
) -> AtlasEntry:
    return service.compute(body)


@router.get("/scenarios/{event_id}", response_model=ScenarioResponse)
async def diversion_scenarios(
    event_id: str,
    service: DiversionService = Depends(_service),
) -> ScenarioResponse:
    return await service.scenarios(event_id)


@router.post("/validate", response_model=ValidateResult)
async def diversion_validate(
    body: ValidateRequest,
    service: DiversionService = Depends(_service),
) -> ValidateResult:
    return service.validate(body)
