"""Action card assembly — orchestrates M03–M08."""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.dashboard.bus import dashboard_bus
from grid_unlocked.dashboard.schemas import DashboardDelta, DeltaScope
from grid_unlocked.dispatch.schemas import GovernanceTier, RecommendRequest
from grid_unlocked.dispatch.service import DispatchService
from grid_unlocked.diversions.service import DiversionService
from grid_unlocked.execution.schemas import ExecuteDispatchRequest
from grid_unlocked.execution.service import ExecutionService as M10ExecutionService
from grid_unlocked.features.service import FeatureService
from grid_unlocked.vms.schemas import VmsPushRequest
from grid_unlocked.vms.service import VmsService as M11VmsService
from grid_unlocked.hotspots.service import HotspotService
from grid_unlocked.impact.service import ImpactService
from grid_unlocked.planned.schemas import PackageRequest
from grid_unlocked.planned.service import PlannedService
from grid_unlocked.propagation.schemas import RippleRequest
from grid_unlocked.propagation.service import PropagationService
from grid_unlocked.recommendations.governance import get_governance
from grid_unlocked.recommendations.repository import RecommendationRepository
from grid_unlocked.impact.schemas import ImpactScore, ModelVersions, SeverityBand
from grid_unlocked.recommendations.schemas import (
    ActionCard,
    AlertPriority,
    ApprovalResult,
    CardMode,
    CardStatus,
    DispatchSection,
    EvidenceBundle,
    GovernanceInfo,
    HotspotContext,
    PlannedSection,
    PropagationSummary,
    QueueItem,
    QueueResponse,
)


def _alert_priority(
    rci: float,
    p_closure: float,
    severity: SeverityBand,
    *,
    is_named_corridor: bool,
    is_peak_hour: bool,
) -> AlertPriority:
    if p_closure > 0.7 and is_named_corridor and is_peak_hour:
        return AlertPriority.CRITICAL
    if severity in {SeverityBand.ORANGE, SeverityBand.RED} or rci >= 0.55:
        return AlertPriority.HIGH
    if severity == SeverityBand.YELLOW or rci >= 0.35:
        return AlertPriority.MEDIUM
    return AlertPriority.LOW


class RecommendationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = RecommendationRepository(session)
        self.features = FeatureService(session)
        self.impact = ImpactService(session)
        self.propagation = PropagationService(session)
        self.hotspots = HotspotService(session)
        self.diversions = DiversionService(session)
        self.dispatch = DispatchService(session)
        self.planned = PlannedService(session)

    async def _publish_card_delta(self, event_id: str, card_id: str, status: str) -> None:
        await dashboard_bus.publish(
            DashboardDelta(
                scope=DeltaScope.CARD,
                event_id=event_id,
                payload={"card_id": card_id, "status": status},
                emitted_at=datetime.now(UTC),
            )
        )

    async def _ensure_features(self, event_id: str):
        fv = await self.features.get_features(event_id)
        if not fv:
            await asyncio.sleep(0.25)
            fv = await self.features.get_features(event_id)
        return fv

    async def _hotspot_context(self, h3_res7: str | None) -> HotspotContext:
        if not h3_res7:
            return HotspotContext(nearby_cluster_count=0)
        observed = await self.hotspots.get_observed()
        nearby = sum(1 for c in observed.clusters if h3_res7 in c.h3_cells)
        try:
            cell = self.hotspots.get_cell_history(h3_res7)
            count_24h = cell.events_30d
        except Exception:
            count_24h = None
        return HotspotContext(
            nearby_cluster_count=nearby,
            cell_event_count_24h=count_24h,
            h3_res7=h3_res7,
        )

    async def build_card(
        self,
        event_id: str,
        *,
        mode: CardMode = CardMode.COMPLETE,
        refresh: bool = False,
    ) -> ActionCard:
        if not refresh:
            cached = await self.repo.get_card_by_event(event_id)
            if cached and cached.status in {CardStatus.PARTIAL, CardStatus.COMPLETE}:
                if mode == CardMode.SKELETON or cached.status == CardStatus.COMPLETE:
                    return cached

        t0 = time.perf_counter()
        row = await self.features.repo.get_event_row(event_id)
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Event {event_id} not found")

        gov = get_governance()
        features = await self._ensure_features(event_id)
        if not features and gov.tier != "3":
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Features not materialized for {event_id}",
            )

        card_id = f"CARD-{uuid.uuid4().hex[:12].upper()}"
        now = datetime.now(UTC)

        if gov.manual_mode or (features is None and gov.tier == "3"):
            return self._sop_fallback_card(card_id, event_id, row, gov, now)

        impact = await self.impact.score(event_id)
        explain = await self.impact.explain(event_id)
        prop = await self.propagation.ripple(RippleRequest(event_id=event_id))
        hotspot_ctx = await self._hotspot_context(features.h3_res7 if features else None)
        diversion_scenario = await self.diversions.scenarios(event_id)

        skeleton_ms = round((time.perf_counter() - t0) * 1000, 2)

        dispatch_section: DispatchSection | None = None
        field_link: str | None = None

        unauthenticated_hold = (
            mode in {CardMode.COMPLETE, CardMode.AUTO}
            and gov.tier != "3"
            and not row.authenticated
        )
        dispatch_pending = mode == CardMode.SKELETON or gov.tier == "3" or unauthenticated_hold

        include_dispatch = (
            mode in {CardMode.COMPLETE, CardMode.AUTO} and gov.tier != "3" and row.authenticated
        )
        if include_dispatch:
            tier = GovernanceTier(gov.tier)
            rec = await self.dispatch.recommend(
                RecommendRequest(event_id=event_id, tier=tier, force_greedy=gov.tier == "2")
            )
            dispatch_section = DispatchSection(
                recommendation_id=rec.recommendation_id,
                source=rec.source,
                assignments=rec.assignments,
                solver_ms=rec.solver_ms,
                provenance=rec.source.value,
            )
            dispatch_pending = False
            if rec.assignments:
                field_link = f"/field/packet/{rec.recommendation_id}"

        planned_section: PlannedSection | None = None
        if row.is_planned:
            try:
                pkg = await self.planned.generate_package(PackageRequest(event_id=event_id))
                planned_section = PlannedSection(
                    template_id=pkg.template_id,
                    barricade_count=pkg.barricade_count,
                    staffing_min=pkg.staffing_min,
                    staffing_max=pkg.staffing_max,
                    barricade_staging_required=pkg.barricade_staging_required,
                )
            except HTTPException:
                pass

        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        card_status = CardStatus.PARTIAL if dispatch_pending else CardStatus.COMPLETE

        card = ActionCard(
            card_id=card_id,
            event_id=event_id,
            source=row.source,
            status=card_status,
            alert_priority=_alert_priority(
                impact.rci,
                impact.p_closure,
                impact.severity_band,
                is_named_corridor=features.is_named_corridor if features else False,
                is_peak_hour=features.is_peak_hour if features else False,
            ),
            impact=impact,
            propagation=PropagationSummary(
                cascade_risk=prop.cascade_risk,
                seed_rci=prop.seed_rci,
                affected_nodes=len(prop.nodes),
                max_hop=max((n.hop for n in prop.nodes), default=0),
            ),
            hotspot_context=hotspot_ctx,
            diversions=diversion_scenario.routes,
            auto_suggest_diversion=diversion_scenario.auto_suggest,
            dispatch=dispatch_section,
            dispatch_pending=dispatch_pending,
            planned=planned_section,
            evidence=EvidenceBundle(
                top_features=explain.top_features,
                model_versions=impact.model_versions,
                diversion_routes=diversion_scenario.routes,
            ),
            governance=GovernanceInfo(
                tier=gov.tier,
                shadow_mode=gov.shadow_mode,
                manual_mode=gov.manual_mode,
            ),
            provenance={
                "impact": impact.model_versions.source,
                "propagation": "GCDH",
                "dispatch": dispatch_section.provenance
                if dispatch_section
                else ("awaiting_citizen_verification" if unauthenticated_hold else "pending"),
                "diversions": "M08_atlas",
            },
            skeleton_ms=skeleton_ms,
            latency_ms=latency_ms,
            field_packet_link=field_link,
            created_at=now,
            updated_at=now,
        )
        await self.repo.save_card(card)
        if card_status == CardStatus.COMPLETE:
            await self._publish_card_delta(event_id, card_id, card_status.value)
        return card

    def _sop_fallback_card(self, card_id, event_id, row, gov, now) -> ActionCard:
        """Tier 3 — static SOP template without ML sections."""
        impact = ImpactScore(
            event_id=event_id,
            p_closure=0.36 if row.is_planned else 0.2,
            ict_p20_h=1.0,
            ict_p50_h=2.0,
            ict_p80_h=4.0,
            rci=0.35,
            severity_band=SeverityBand.YELLOW,
            priority_structural=False,
            staging_recommended=row.is_planned,
            model_versions=ModelVersions(closure="sop", ict="sop", source="tier3_sop"),
            latency_ms=0,
            scored_at=now,
        )
        return ActionCard(
            card_id=card_id,
            event_id=event_id,
            source=row.source,
            status=CardStatus.PARTIAL,
            alert_priority=AlertPriority.MEDIUM,
            impact=impact,
            propagation=PropagationSummary(
                cascade_risk=impact.rci,
                seed_rci=impact.rci,
                affected_nodes=1,
                max_hop=0,
            ),
            hotspot_context=HotspotContext(nearby_cluster_count=0),
            diversions=[],
            auto_suggest_diversion=False,
            dispatch_pending=True,
            evidence=EvidenceBundle(
                top_features=[],
                model_versions=impact.model_versions,
                diversion_routes=[],
            ),
            governance=GovernanceInfo(tier=gov.tier, shadow_mode=gov.shadow_mode, manual_mode=True),
            provenance={"impact": "tier3_sop", "dispatch": "disabled"},
            skeleton_ms=0,
            latency_ms=0,
            created_at=now,
            updated_at=now,
        )

    async def approve(self, card_id: str, commander_id: str, override_codes: list[str]) -> ApprovalResult:
        card = await self.repo.get_card(card_id)
        if not card:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Card {card_id} not found")

        gov = get_governance()
        execution = not gov.shadow_mode and gov.tier != "3"
        token = await self.repo.save_approval(
            card_id,
            "approve",
            commander_id,
            override_codes=override_codes,
            shadow_mode=gov.shadow_mode,
            execution_enqueued=execution,
        )
        await self.repo.update_status(card_id, CardStatus.APPROVED)
        await self._publish_card_delta(card.event_id, card_id, CardStatus.APPROVED.value)

        # Trigger M10 execution when not in shadow mode
        if execution:
            try:
                m10 = M10ExecutionService(self.session)
                station_id: str | None = None
                rec_id: str | None = None
                barricade_count = 0

                # Extract dispatch info from card if available
                if card.dispatch:
                    rec_id = card.dispatch.recommendation_id
                    if card.dispatch.assignments:
                        station_id = card.dispatch.assignments[0].station_id

                # Extract barricade count from planned section if available
                if card.planned:
                    barricade_count = card.planned.barricade_count

                m10_result = await m10.enqueue_dispatch(
                    ExecuteDispatchRequest(
                        approval_token=token,
                        card_id=card_id,
                        event_id=card.event_id,
                        recommendation_id=rec_id,
                        barricade_count=barricade_count,
                        station_id=station_id,
                        commander_id=commander_id,
                    )
                )
                msg = f"Approval recorded — dispatch enqueued (token={token})"
                if m10_result.barricade_execution_id:
                    msg += f"; barricade reservation enqueued ({m10_result.barricade_execution_id})"
            except Exception:
                # Non-fatal: approval is still recorded even if M10 enqueue fails
                msg = f"Approval recorded — M10 enqueue failed (token={token}); manual dispatch required"

            # Trigger M11 VMS push when diversions exist for this card
            if card.diversions:
                try:
                    m11 = M11VmsService(self.session)
                    event_row = await self.features.repo.get_event_row(card.event_id)
                    corridor = event_row.corridor if event_row else None

                    m11_result = await m11.push(
                        VmsPushRequest(
                            push_id=token,
                            event_id=card.event_id,
                            card_id=card_id,
                            corridor=corridor,
                            routes=[r.model_dump() for r in card.diversions],
                            commander_id=commander_id,
                        )
                    )
                    msg += f"; VMS push to {m11_result.board_count} boards (push_id={token})"
                except Exception:
                    # Non-fatal: approval/dispatch already recorded even if VMS push fails
                    msg += "; M11 VMS push failed — manual board update required"
        else:
            msg = (
                "Approval logged in shadow mode — M10/M11 execution blocked"
                if gov.shadow_mode
                else f"Approval recorded — execution disabled in Tier {gov.tier}"
            )

        return ApprovalResult(
            card_id=card_id,
            action="approve",
            shadow_mode=gov.shadow_mode,
            execution_enqueued=execution,
            approval_token=token if execution else None,
            message=msg,
        )

    async def reject(self, card_id: str, commander_id: str, reason_code: str, notes: str | None) -> ApprovalResult:
        card = await self.repo.get_card(card_id)
        if not card:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Card {card_id} not found")

        gov = get_governance()
        await self.repo.save_approval(
            card_id,
            "reject",
            commander_id,
            reason_code=reason_code,
            notes=notes,
            shadow_mode=gov.shadow_mode,
            execution_enqueued=False,
        )
        await self.repo.update_status(card_id, CardStatus.REJECTED)
        await self._publish_card_delta(card.event_id, card_id, CardStatus.REJECTED.value)
        return ApprovalResult(
            card_id=card_id,
            action="reject",
            shadow_mode=gov.shadow_mode,
            execution_enqueued=False,
            message=f"Rejection recorded: {reason_code}",
        )

    async def queue(self, severity_min: str | None = None) -> QueueResponse:
        events = await self.repo.list_active_events()
        items: list[QueueItem] = []

        for row in events:
            try:
                score = await self.impact.score(row.event_id)
            except HTTPException:
                continue
            if severity_min:
                bands = ["Green", "Yellow", "Orange", "Red"]
                min_idx = bands.index(severity_min) if severity_min in bands else 0
                if bands.index(score.severity_band.value) < min_idx:
                    continue

            features = await self.features.get_features(row.event_id)
            priority = _alert_priority(
                score.rci,
                score.p_closure,
                score.severity_band,
                is_named_corridor=features.is_named_corridor if features else False,
                is_peak_hour=features.is_peak_hour if features else False,
            )
            cached = await self.repo.get_card_by_event(row.event_id)
            items.append(
                QueueItem(
                    event_id=row.event_id,
                    card_id=cached.card_id if cached else None,
                    rci=score.rci,
                    p_closure=score.p_closure,
                    severity_band=score.severity_band,
                    alert_priority=priority,
                    corridor=row.corridor,
                    status=cached.status if cached else None,
                )
            )

        items.sort(key=lambda i: (-i.rci, i.event_id))
        return QueueResponse(items=items, count=len(items))
