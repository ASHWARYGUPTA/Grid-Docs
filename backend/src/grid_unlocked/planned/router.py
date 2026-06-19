from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db.session import get_session
from grid_unlocked.planned.schemas import PackageRequest, PlannedEventPackage, TemplateDefinition
from grid_unlocked.planned.service import PlannedService

router = APIRouter(prefix="/planned", tags=["planned"])
templates_router = APIRouter(prefix="/templates", tags=["templates"])


async def _service(session: AsyncSession = Depends(get_session)) -> PlannedService:
    return PlannedService(session)


@router.post("/package", response_model=PlannedEventPackage)
async def planned_package(
    body: PackageRequest,
    service: PlannedService = Depends(_service),
) -> PlannedEventPackage:
    return await service.generate_package(body)


@router.get("/upcoming", response_model=list[PlannedEventPackage])
async def planned_upcoming(
    hours: int = Query(default=72, ge=1, le=168),
    service: PlannedService = Depends(_service),
) -> list[PlannedEventPackage]:
    return await service.upcoming(hours)


@templates_router.get("/{cause}", response_model=TemplateDefinition)
async def template_by_cause(
    cause: str,
    service: PlannedService = Depends(_service),
) -> TemplateDefinition:
    return service.get_template(cause)
