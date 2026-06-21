import json
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.citizen.cause_hint import infer_cause_hint
from grid_unlocked.citizen.exif import extract_gps_from_exif, strip_exif_except_gps
from grid_unlocked.citizen.geo import nearest_corridor
from grid_unlocked.citizen.repository import CitizenRepository, decode_json_list
from grid_unlocked.citizen.schemas import (
    CitizenPreAlertPayload,
    CitizenReport,
    CitizenReportStatus,
    CitizenReportStatusResponse,
    SubscriptionRequest,
    SubscriptionResponse,
)
from grid_unlocked.dashboard.bus import dashboard_bus
from grid_unlocked.dashboard.schemas import DashboardDelta, DeltaScope
from grid_unlocked.db.models import CitizenReportRow, CorridorSubscriptionRow
from grid_unlocked.features.service import FeatureService
from grid_unlocked.hotspots.geo import h3_res7
from grid_unlocked.hotspots.service import HotspotService
from grid_unlocked.impact.service import ImpactService
from grid_unlocked.ingestion.schemas import IngestSource
from grid_unlocked.ingestion.service import IngestionService
from grid_unlocked.ingestion.validator import IngestValidationError, validate_bbox
from grid_unlocked.propagation.service import PropagationService
from grid_unlocked.recommendations.schemas import ActionCard
from grid_unlocked.recommendations.service import RecommendationService

MAX_PHOTO_BYTES = 5 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}
ICT_P80_FALLBACK_MULTIPLIER = 1.6  # MVP heuristic — no real p80 in the prior-only fallback path
HOTSPOT_ALERT_DENSITY_THRESHOLD = 10  # >= this many events in a cluster => Orange, else Yellow
PROPAGATION_ALERT_RISK_THRESHOLD = 0.55


class CitizenReportError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class CitizenService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = CitizenRepository(session)
        self.ingestion = IngestionService(session)
        self.impact = ImpactService(session)
        self.features = FeatureService(session)
        self.recommendations = RecommendationService(session)
        self.hotspots = HotspotService(session)
        self.propagation = PropagationService(session)

    async def _resolve_location(
        self, lat: float | None, lon: float | None, photo_bytes: bytes
    ) -> tuple[float, float, str]:
        if lat is not None and lon is not None:
            resolved_lat, resolved_lon, source = lat, lon, "device"
        else:
            gps = extract_gps_from_exif(photo_bytes)
            if gps is None:
                raise CitizenReportError(
                    "missing location: provide device GPS or a photo with EXIF GPS"
                )
            resolved_lat, resolved_lon, source = gps[0], gps[1], "exif"

        try:
            validate_bbox(resolved_lat, resolved_lon)
        except IngestValidationError as exc:
            raise CitizenReportError(f"location outside Bengaluru service area: {exc.reason}") from exc

        return resolved_lat, resolved_lon, source

    def _validate_photo(self, content_type: str, photo_bytes: bytes) -> None:
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise CitizenReportError("photo must be JPEG or PNG")
        if len(photo_bytes) > MAX_PHOTO_BYTES:
            raise CitizenReportError("photo exceeds 5MB limit")

    async def _quote_ict(
        self, event_id: str | None, corridor: str | None, cause: str
    ) -> tuple[float, float, float, str]:
        if event_id is not None:
            try:
                impact = await self.impact.score(event_id)
                return impact.ict_p50_h, impact.ict_p80_h, impact.p_closure, "m03_live"
            except HTTPException:
                pass

        prior = await self.features.get_prior(corridor or "Non-corridor", cause)
        ict_p50 = prior.median_ict_h if prior else 1.0
        closure_rate = prior.closure_rate if prior else 0.083
        return ict_p50, round(ict_p50 * ICT_P80_FALLBACK_MULTIPLIER, 2), closure_rate, "corridor_prior_fallback"

    async def submit_report(
        self,
        *,
        lat: float | None,
        lon: float | None,
        photo_bytes: bytes,
        content_type: str,
        description: str | None,
    ) -> CitizenReport:
        resolved_lat, resolved_lon, location_source = await self._resolve_location(
            lat, lon, photo_bytes
        )
        self._validate_photo(content_type, photo_bytes)

        h3_cell = h3_res7(resolved_lat, resolved_lon)
        centroids = await self.repo.get_all_centroids()
        corridor = nearest_corridor(resolved_lat, resolved_lon, centroids)
        cause, confidence = infer_cause_hint(description)

        report_id = f"CTZ-{uuid.uuid4().hex[:12].upper()}"
        cleaned_photo = strip_exif_except_gps(photo_bytes)

        ingest_payload = {
            "id": report_id,
            "event_type": "unplanned",
            "latitude": resolved_lat,
            "longitude": resolved_lon,
            "event_cause": cause,
            "requires_road_closure": False,
            "start_datetime": datetime.now(UTC).isoformat(),
            "status": "active",
            "corridor": corridor,
            "description": description,
            "priority": "Low",
            "source": "citizen",
        }
        ack_or_error = await self.ingestion.ingest(ingest_payload, source=IngestSource.CITIZEN)
        event_id = ack_or_error.event_id if not isinstance(ack_or_error, tuple) else None

        ict_p50, ict_p80, p_closure, quote_source = await self._quote_ict(event_id, corridor, cause)

        row = CitizenReportRow(
            report_id=report_id,
            event_id=event_id,
            status=CitizenReportStatus.PENDING.value,
            latitude=resolved_lat,
            longitude=resolved_lon,
            location_source=location_source,
            h3_cell=h3_cell,
            corridor=corridor,
            junction=None,
            cause_hint=cause,
            cause_confidence=confidence,
            ict_p50=ict_p50,
            ict_p80=ict_p80,
            p_closure=p_closure,
            ict_quote_source=quote_source,
            description=description,
            photo_bytes=cleaned_photo,
            photo_content_type=content_type,
        )
        await self.repo.save_report(row)

        await dashboard_bus.publish(
            DashboardDelta(
                scope=DeltaScope.CITIZEN,
                event_id=event_id,
                payload={
                    "type": "CitizenReportSubmitted",
                    "report_id": report_id,
                    "lat": resolved_lat,
                    "lon": resolved_lon,
                    "corridor": corridor,
                    "ict_p50": ict_p50,
                    "ict_p80": ict_p80,
                    "has_photo": True,
                },
                emitted_at=datetime.now(UTC),
            )
        )

        return CitizenReport(
            report_id=report_id,
            status=CitizenReportStatus.PENDING,
            h3_cell=h3_cell,
            corridor=corridor,
            junction=None,
            ict_p50=ict_p50,
            ict_p80=ict_p80,
            p_closure=p_closure,
            cause_hint=cause,
            cause_confidence=confidence,
            event_id=event_id,
            has_photo=True,
            created_at=row.created_at,
        )

    async def get_report(self, report_id: str) -> CitizenReportStatusResponse:
        row = await self.repo.get_report(report_id)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Report {report_id} not found")
        return CitizenReportStatusResponse(
            report_id=row.report_id,
            status=CitizenReportStatus(row.status),
            ict_p50=row.ict_p50,
            ict_p80=row.ict_p80,
            p_closure=row.p_closure,
            corridor=row.corridor,
            h3_cell=row.h3_cell,
            created_at=row.created_at,
        )

    async def verify_report(self, report_id: str, commander_id: str) -> ActionCard:
        row = await self.repo.get_report(report_id)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Report {report_id} not found")

        event_id = row.event_id
        if event_id is None:
            ingest_payload = {
                "id": row.report_id,
                "event_type": "unplanned",
                "latitude": row.latitude,
                "longitude": row.longitude,
                "event_cause": row.cause_hint,
                "requires_road_closure": False,
                "start_datetime": datetime.now(UTC).isoformat(),
                "status": "active",
                "corridor": row.corridor,
                "description": row.description,
                "priority": "Low",
                "source": "citizen",
            }
            ack_or_error = await self.ingestion.ingest(ingest_payload, source=IngestSource.CITIZEN)
            if isinstance(ack_or_error, tuple):
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail="cannot verify: backend ingest still failing",
                )
            event_id = ack_or_error.event_id

        await self.repo.set_event_authenticated(event_id, True)
        await self.repo.update_status(
            report_id, CitizenReportStatus.VERIFIED.value, event_id=event_id, verified_by=commander_id
        )
        return await self.recommendations.build_card(event_id, refresh=True)

    async def reject_report(
        self, report_id: str, reason_code: str, commander_id: str | None
    ) -> None:
        row = await self.repo.get_report(report_id)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Report {report_id} not found")
        await self.repo.update_status(
            report_id,
            CitizenReportStatus.REJECTED.value,
            rejected_by=commander_id,
            reject_reason_code=reason_code,
        )

    async def get_photo(self, report_id: str) -> tuple[bytes, str]:
        row = await self.repo.get_report(report_id)
        if row is None or row.photo_bytes is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="photo not found")
        return row.photo_bytes, row.photo_content_type or "application/octet-stream"

    async def subscribe(self, req: SubscriptionRequest) -> SubscriptionResponse:
        if not req.corridors and not req.h3_cells:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="must provide corridors or h3_cells"
            )
        subscription_id = f"SUB-{uuid.uuid4().hex[:12].upper()}"
        row = CorridorSubscriptionRow(
            subscription_id=subscription_id,
            user_ref=req.user_ref,
            corridors_json=json.dumps(req.corridors),
            h3_cells_json=json.dumps(req.h3_cells),
        )
        await self.repo.create_subscription(row)
        return SubscriptionResponse(
            subscription_id=subscription_id,
            user_ref=req.user_ref,
            corridors=req.corridors,
            h3_cells=req.h3_cells,
            created_at=row.created_at,
        )

    async def unsubscribe(self, subscription_id: str) -> None:
        found = await self.repo.deactivate_subscription(subscription_id)
        if not found:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Subscription {subscription_id} not found")

    async def check_pre_alerts(self) -> int:
        subs = await self.repo.list_active_subscriptions()
        if not subs:
            return 0

        alert_count = 0

        observed = await self.hotspots.get_observed()
        for cluster in observed.clusters:
            severity = "Orange" if cluster.density >= HOTSPOT_ALERT_DENSITY_THRESHOLD else "Yellow"
            for sub in subs:
                sub_h3_cells = set(decode_json_list(sub.h3_cells_json))
                sub_corridors = set(decode_json_list(sub.corridors_json))
                if sub_h3_cells & set(cluster.h3_cells) or sub_corridors & set(cluster.corridors):
                    await self._publish_pre_alert(sub.subscription_id, "hotspot", severity)
                    alert_count += 1

        active_ripples = await self.propagation.get_active()
        for pmap in active_ripples:
            for node in pmap.nodes:
                if node.corridor is None:
                    continue
                severity = "Orange" if node.risk >= PROPAGATION_ALERT_RISK_THRESHOLD else "Yellow"
                for sub in subs:
                    sub_corridors = set(decode_json_list(sub.corridors_json))
                    if node.corridor in sub_corridors:
                        await self._publish_pre_alert(sub.subscription_id, "propagation", severity)
                        alert_count += 1

        return alert_count

    async def _publish_pre_alert(self, subscription_id: str, alert_type: str, severity_band: str) -> None:
        payload = CitizenPreAlertPayload(
            subscription_id=subscription_id, alert_type=alert_type, severity_band=severity_band
        )
        await dashboard_bus.publish(
            DashboardDelta(
                scope=DeltaScope.CITIZEN,
                event_id=None,
                payload={"type": "CitizenPreAlert", **payload.model_dump()},
                emitted_at=datetime.now(UTC),
            )
        )
