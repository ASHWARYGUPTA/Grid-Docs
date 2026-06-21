from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.citizen.schemas import (
    CitizenRejectRequest,
    CitizenReport,
    CitizenReportStatusResponse,
    CitizenVerifyRequest,
    SubscriptionRequest,
    SubscriptionResponse,
)
from grid_unlocked.citizen.service import CitizenReportError, CitizenService
from grid_unlocked.db.session import get_session
from grid_unlocked.recommendations.schemas import ActionCard

router = APIRouter(prefix="/citizen", tags=["citizen"])


async def _service(session: AsyncSession = Depends(get_session)) -> CitizenService:
    return CitizenService(session)


@router.post("/report", response_model=CitizenReport, status_code=status.HTTP_201_CREATED)
async def submit_report(
    photo: UploadFile = File(...),
    lat: float | None = Form(default=None),
    lon: float | None = Form(default=None),
    description: str | None = Form(default=None),
    service: CitizenService = Depends(_service),
) -> CitizenReport:
    photo_bytes = await photo.read()
    try:
        return await service.submit_report(
            lat=lat,
            lon=lon,
            photo_bytes=photo_bytes,
            content_type=photo.content_type or "",
            description=description,
        )
    except CitizenReportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/report/{report_id}", response_model=CitizenReportStatusResponse)
async def get_report(
    report_id: str, service: CitizenService = Depends(_service)
) -> CitizenReportStatusResponse:
    return await service.get_report(report_id)


@router.post("/verify/{report_id}", response_model=ActionCard)
async def verify_report(
    report_id: str, body: CitizenVerifyRequest, service: CitizenService = Depends(_service)
) -> ActionCard:
    return await service.verify_report(report_id, body.commander_id)


@router.post("/reject/{report_id}")
async def reject_report(
    report_id: str, body: CitizenRejectRequest, service: CitizenService = Depends(_service)
) -> dict:
    await service.reject_report(report_id, body.reason_code, body.commander_id)
    return {"report_id": report_id, "status": "rejected"}


@router.post("/subscribe", response_model=SubscriptionResponse)
async def subscribe(
    body: SubscriptionRequest, service: CitizenService = Depends(_service)
) -> SubscriptionResponse:
    return await service.subscribe(body)


@router.delete("/subscribe/{subscription_id}")
async def unsubscribe(subscription_id: str, service: CitizenService = Depends(_service)) -> dict:
    await service.unsubscribe(subscription_id)
    return {"subscription_id": subscription_id, "status": "unsubscribed"}


@router.get("/photo/{report_id}")
async def get_photo(report_id: str, service: CitizenService = Depends(_service)) -> Response:
    photo_bytes, content_type = await service.get_photo(report_id)
    return Response(content=photo_bytes, media_type=content_type)
