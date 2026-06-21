import logging
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.dashboard.bus import dashboard_bus
from grid_unlocked.dashboard.schemas import DashboardDelta, DeltaScope
from grid_unlocked.db.models import FieldClosureRow
from grid_unlocked.dispatch.repository import DispatchRepository
from grid_unlocked.diversions.service import DiversionService
from grid_unlocked.field.repository import FieldRepository
from grid_unlocked.field.schemas import (
    AckResponse,
    ClosureRequest,
    ClosureResponse,
    FieldAssignmentSummary,
    FieldDiversionSummary,
    FieldIctBands,
    FieldPacket,
)
from grid_unlocked.governance.schemas import GovernanceTierResponse
from grid_unlocked.governance.service import GovernanceService
from grid_unlocked.impact.service import ImpactService
from grid_unlocked.ingestion.schemas import IngestSource
from grid_unlocked.ingestion.service import IngestionService

logger = logging.getLogger(__name__)


class FieldService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = FieldRepository(session)
        self.dispatch_repo = DispatchRepository(session)
        self.ingestion = IngestionService(session)
        self.impact = ImpactService(session)
        self.diversions = DiversionService(session)
        self.governance = GovernanceService(session)

    async def get_packet(self, recommendation_id: str) -> FieldPacket:
        rec = await self.dispatch_repo.get_recommendation(recommendation_id)
        if rec is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="recommendation not found")
        if not rec.assignments:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail="recommendation has no assignments"
            )

        event_id = rec.assignments[0].event_id
        event = await self.ingestion.get_event(event_id)
        if event is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="underlying event not found")

        try:
            impact = await self.impact.score(event_id)
            ict = FieldIctBands(
                ict_p20_h=impact.ict_p20_h,
                ict_p50_h=impact.ict_p50_h,
                ict_p80_h=impact.ict_p80_h,
                severity_band=impact.severity_band.value,
            )
        except HTTPException:
            logger.warning("M16 packet %s: impact score unavailable, degrading", recommendation_id)
            ict = FieldIctBands(ict_p20_h=0.0, ict_p50_h=0.0, ict_p80_h=0.0, severity_band="Green")

        top_diversion: FieldDiversionSummary | None = None
        try:
            scenario = await self.diversions.scenarios(event_id)
            if scenario.routes:
                route = scenario.routes[0]
                top_diversion = FieldDiversionSummary(
                    junction_id=route.junction_id,
                    description=route.description,
                    route_summary=route.route_summary,
                    eta_delta_min=route.eta_delta_min,
                    capacity_class=route.capacity_class,
                    available=True,
                )
        except HTTPException:
            logger.warning("M16 packet %s: diversion scenario unavailable", recommendation_id)

        ack_row = await self.repo.get_ack(recommendation_id)

        navigation_deep_link = (
            f"https://www.google.com/maps/search/?api=1&query={event.latitude},{event.longitude}"
        )

        return FieldPacket(
            recommendation_id=rec.recommendation_id,
            event_id=event_id,
            source=rec.source.value,
            tier_at_decision=rec.tier_at_decision.value,
            assignments=[
                FieldAssignmentSummary(
                    unit_id=a.unit_id,
                    station_id=a.station_id,
                    equip_type=a.equip_type.value,
                    eta_min=a.eta_min,
                    rci=a.rci,
                    cascade_risk=a.cascade_risk,
                    needs_heavy_tow=a.needs_heavy_tow,
                )
                for a in rec.assignments
            ],
            impact=ict,
            top_diversion=top_diversion,
            navigation_deep_link=navigation_deep_link,
            event_status=event.status,
            already_closed=event.status == "closed",
            acknowledged=ack_row is not None,
            acknowledged_at=ack_row.acknowledged_at if ack_row else None,
            provenance={"dispatch": "M07", "impact": "M03", "diversion": "M08", "tier": "M14"},
            generated_at=datetime.now(UTC),
        )

    async def ack(self, recommendation_id: str, officer_id: str) -> AckResponse:
        rec = await self.dispatch_repo.get_recommendation(recommendation_id)
        if rec is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="recommendation not found")

        now = datetime.now(UTC)
        await self.repo.upsert_ack(recommendation_id, officer_id, now)

        event_id = rec.assignments[0].event_id if rec.assignments else None
        await dashboard_bus.publish(
            DashboardDelta(
                scope=DeltaScope.FIELD,
                event_id=event_id,
                payload={
                    "type": "FieldAcknowledged",
                    "recommendation_id": recommendation_id,
                    "officer_id": officer_id,
                },
                emitted_at=now,
            )
        )
        return AckResponse(recommendation_id=recommendation_id, acknowledged=True, acknowledged_at=now)

    async def close(self, event_id: str, req: ClosureRequest) -> ClosureResponse:
        existing = await self.repo.get_closure_by_event(event_id)
        if existing is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="event already has a field closure on record",
            )

        event = await self.ingestion.get_event(event_id)
        if event is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="event not found")

        payload = event.model_dump(mode="json")
        payload["id"] = payload.pop("event_id")
        payload["status"] = "closed"
        # Match start_datetime's awareness: SQLite round-trips datetimes as
        # naive (see learning/buffer.py's identical caveat), so a tz-aware
        # closed_datetime here would make detect_anomalies' `closed < start`
        # comparison raise on naive-vs-aware. Postgres keeps tzinfo on both
        # sides and is unaffected either way.
        closed_dt = req.closed_datetime
        if event.start_datetime.tzinfo is None and closed_dt.tzinfo is not None:
            closed_dt = closed_dt.astimezone(UTC).replace(tzinfo=None)
        payload["closed_datetime"] = closed_dt.isoformat()

        result = await self.ingestion.ingest(payload, source=IngestSource.FIELD)
        if isinstance(result, tuple):
            _, reason = result
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"could not close event: {reason}"
            )

        closure_id = f"FCLOSE-{uuid.uuid4().hex[:12].upper()}"
        try:
            await self.repo.save_closure(
                FieldClosureRow(
                    closure_id=closure_id,
                    event_id=event_id,
                    recommendation_id=None,
                    barricades_used=req.barricades_used,
                    officers_used=req.officers_used,
                    diversion_activated=req.diversion_activated,
                    notes=req.notes,
                    closed_datetime=req.closed_datetime,
                    officer_id=req.officer_id,
                )
            )
        except Exception:
            logger.exception(
                "M16 close %s: event closed successfully but field_closures write failed",
                event_id,
            )

        await dashboard_bus.publish(
            DashboardDelta(
                scope=DeltaScope.FIELD,
                event_id=event_id,
                payload={
                    "type": "FieldClosureSubmitted",
                    "closure_id": closure_id,
                    "barricades_used": req.barricades_used,
                    "officers_used": req.officers_used,
                    "diversion_activated": req.diversion_activated,
                },
                emitted_at=datetime.now(UTC),
            )
        )

        return ClosureResponse(
            event_id=event_id,
            closure_id=closure_id,
            event_closed=True,
            closed_datetime=req.closed_datetime,
        )

    async def get_tier(self) -> GovernanceTierResponse:
        return await self.governance.get_tier()
