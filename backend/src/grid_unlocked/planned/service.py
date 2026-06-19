import asyncio
import time
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.features.service import FeatureService
from grid_unlocked.impact.registry import registry
from grid_unlocked.planned.analogs import find_analog_events
from grid_unlocked.planned.diversion_stub import diversion_refs_for_corridor
from grid_unlocked.planned.repository import PlannedRepository, attributes_hash
from grid_unlocked.planned.rules import (
    apply_vip_barricade_floor,
    barricade_staging_required,
    severity_ordinal,
)
from grid_unlocked.planned.schemas import ImpactOverlay, PackageRequest, PlannedEventPackage
from grid_unlocked.planned.templates import match_template, seed_to_definition


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


class PlannedService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = PlannedRepository(session)
        self.features = FeatureService(session)

    async def generate_package(self, request: PackageRequest) -> PlannedEventPackage:
        t0 = time.perf_counter()
        event = await self.repo.get_event(request.event_id)
        if not event:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Event {request.event_id} not found")
        if not event.is_planned:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Package generation requires a planned event",
            )

        est_duration_h = None
        if event.end_datetime and event.end_datetime > event.start_datetime:
            est_duration_h = (
                event.end_datetime - event.start_datetime
            ).total_seconds() / 3600.0

        attr_hash = attributes_hash(
            event.event_cause,
            event.corridor,
            event.start_datetime,
            event.end_datetime,
        )

        if not request.force_refresh:
            cached = await self.repo.get_cached_package(request.event_id, attr_hash)
            if cached:
                cached.latency_ms = round((time.perf_counter() - t0) * 1000, 2)
                return cached

        seed, low_conf = match_template(
            cause=event.event_cause,
            corridor=event.corridor,
            start_datetime=event.start_datetime,
            estimated_duration_h=est_duration_h,
        )
        template = seed_to_definition(seed)

        overlay = await self._impact_overlay(event, request.force_refresh)

        barricades = apply_vip_barricade_floor(event.event_cause, template.barricade_count)
        staging = barricade_staging_required(event.event_cause, overlay.p_closure)

        now = datetime.now(UTC)
        hours_until = max(0.0, (_as_utc(event.start_datetime) - now).total_seconds() / 3600.0)

        package = PlannedEventPackage(
            event_id=event.event_id,
            template_id=template.template_id,
            cause=event.event_cause,
            corridor=event.corridor,
            hours_until_start=round(hours_until, 2),
            estimated_duration_h=round(est_duration_h, 2) if est_duration_h else None,
            staffing_min=template.staffing_min,
            staffing_max=template.staffing_max,
            barricade_count=barricades,
            barricade_staging_required=staging,
            deployment_lead_time_hours=template.deployment_lead_time_hours,
            checklist=template.checklist,
            analog_events=find_analog_events(event.event_cause, event.corridor),
            diversion_refs=diversion_refs_for_corridor(event.corridor),
            impact_overlay=overlay,
            compliance_items=[
                "BTP permit reference verified",
                "BBMP road cut approval (if construction)",
                "Station commander sign-off",
            ],
            low_confidence_template=low_conf,
            cached=False,
            latency_ms=round((time.perf_counter() - t0) * 1000, 2),
            generated_at=now,
        )

        await self.repo.save_package(package, attr_hash)
        return package

    async def _impact_overlay(self, event, force_refresh: bool) -> ImpactOverlay:
        if not force_refresh:
            stored = await self.repo.get_stored_package(event.event_id)
            if stored and stored.impact_overlay:
                return stored.impact_overlay

        features = await self.features.get_features(event.event_id)
        if not features:
            await asyncio.sleep(0.25)
            features = await self.features.get_features(event.event_id)
        if not features:
            return self._prior_overlay(event)

        result = registry.score(
            features,
            is_planned=True,
            event_cause=event.event_cause,
            corridor=event.corridor,
        )
        return ImpactOverlay(
            p_closure=result.p_closure,
            ict_p20_h=result.ict_p20_h,
            ict_p50_h=result.ict_p50_h,
            ict_p80_h=result.ict_p80_h,
            rci=result.rci,
            severity_band=result.severity_band,
            severity_ordinal=severity_ordinal(result.severity_band),
            source=result.source,
        )

    def _prior_overlay(self, event) -> ImpactOverlay:
        """Tier 2 fallback — planned prior p_closure=0.36."""
        return ImpactOverlay(
            p_closure=0.36,
            ict_p20_h=12.0,
            ict_p50_h=18.0,
            ict_p80_h=24.0,
            rci=0.45,
            severity_band="Yellow",
            severity_ordinal=2,
            source="rule_fallback",
        )

    async def upcoming(self, hours: int = 72) -> list[PlannedEventPackage]:
        events = await self.repo.list_upcoming_planned(hours)
        packages: list[PlannedEventPackage] = []
        for event in events:
            try:
                pkg = await self.generate_package(PackageRequest(event_id=event.event_id))
                packages.append(pkg)
            except HTTPException:
                continue
        packages.sort(key=lambda p: p.hours_until_start)
        return packages

    def get_template(self, cause: str):
        from grid_unlocked.planned.templates import get_template_by_cause

        template = get_template_by_cause(cause)
        if not template:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"No template for cause {cause}")
        return template
