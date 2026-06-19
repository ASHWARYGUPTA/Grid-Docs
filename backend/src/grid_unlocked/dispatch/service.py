"""Non-blocking dispatch orchestrator — MILP with greedy fallback."""

from __future__ import annotations

import asyncio
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.config import settings
from grid_unlocked.dispatch.greedy import greedy_assign, pair_cost
from grid_unlocked.dispatch.incidents import IncidentContext, build_incident_context
from grid_unlocked.dispatch.milp import milp_assign
from grid_unlocked.dispatch.repository import DispatchRepository
from grid_unlocked.dispatch.roster import resolve_units
from grid_unlocked.dispatch.schemas import (
    Assignment,
    AstramShadowCompare,
    DispatchRecommendation,
    DispatchSource,
    DispatchStatus,
    GovernanceTier,
    RecommendRequest,
)
from grid_unlocked.dispatch.travel import eta_minutes
from grid_unlocked.features.service import FeatureService
from grid_unlocked.impact.registry import registry

_status_cache: dict[str, DispatchStatus] = {}
_late_milp_log: dict[str, bool] = {}
_executor = ThreadPoolExecutor(max_workers=2)


def _priority_rank(priority: str | None) -> int:
    order = {"High": 0, "Medium": 1, "Low": 2}
    return order.get(priority or "Low", 3)


def _astram_shadow(incidents: list[IncidentContext]) -> list[AstramShadowCompare]:
    by_astram = sorted(
        incidents,
        key=lambda i: (_priority_rank(i.priority), -i.centrality, i.event_id),
    )
    by_rci = sorted(incidents, key=lambda i: (-i.rci, i.event_id))
    astram_rank = {i.event_id: idx + 1 for idx, i in enumerate(by_astram)}
    rci_rank = {i.event_id: idx + 1 for idx, i in enumerate(by_rci)}
    return [
        AstramShadowCompare(
            event_id=i.event_id,
            astram_priority=i.priority,
            astram_rank=astram_rank[i.event_id],
            grid_rci_rank=rci_rank[i.event_id],
            priority_structural=i.priority_structural,
        )
        for i in incidents
    ]


def _tier3_assign(units, incidents: list[IncidentContext]) -> list[Assignment]:
    on_shift = [u for u in units if u.on_shift]
    assignments: list[Assignment] = []
    for incident in sorted(incidents, key=lambda i: -i.rci):
        if not on_shift:
            break
        best = min(
            on_shift,
            key=lambda u: (
                eta_minutes(
                    u.latitude,
                    u.longitude,
                    incident.latitude,
                    incident.longitude,
                    avg_speed_kmh=settings.dispatch_avg_speed_kmh,
                ),
                u.station_id,
                u.unit_id,
            ),
        )
        eta = eta_minutes(
            best.latitude,
            best.longitude,
            incident.latitude,
            incident.longitude,
            avg_speed_kmh=settings.dispatch_avg_speed_kmh,
        )
        cost, _ = pair_cost(best, incident)
        assignments.append(
            Assignment(
                unit_id=best.unit_id,
                station_id=best.station_id,
                event_id=incident.event_id,
                equip_type=best.equip_type,
                eta_min=eta,
                pair_cost=cost,
                rci=incident.rci,
                cascade_risk=incident.cascade_risk,
                needs_heavy_tow=incident.needs_heavy_tow,
            )
        )
    return assignments


class DispatchService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = DispatchRepository(session)
        self.features = FeatureService(session)

    async def _materialize_incidents(self, event_ids: list[str]) -> list[IncidentContext]:
        rows = await self.repo.get_event_rows(event_ids)
        if not rows:
            return []

        contexts: list[IncidentContext] = []
        for row in rows:
            features = await self.features.get_features(row.event_id)
            if not features:
                await asyncio.sleep(0.25)
                features = await self.features.get_features(row.event_id)
            if not features:
                continue

            scored = registry.score(
                features,
                is_planned=row.is_planned,
                event_cause=row.event_cause,
                corridor=row.corridor,
            )
            contexts.append(
                build_incident_context(
                    row,
                    features,
                    rci=scored.rci,
                    p_closure=scored.p_closure,
                    graph_node_id=features.graph_node_id,
                )
            )
        return contexts

    async def _resolve_incident_ids(self, request: RecommendRequest) -> list[str]:
        ids: list[str] = []
        if request.active_incident_ids:
            ids.extend(request.active_incident_ids)
        else:
            ids.extend(await self.repo.list_active_event_ids())
        if request.event_id not in ids:
            ids.insert(0, request.event_id)

        seen: set[str] = set()
        ordered: list[str] = []
        for eid in ids:
            if eid not in seen:
                seen.add(eid)
                ordered.append(eid)
        return ordered

    def _schedule_late_milp_log(
        self,
        recommendation_id: str,
        units,
        incidents: list[IncidentContext],
    ) -> None:
        def _late() -> None:
            _, _, feasible = milp_assign(units, incidents, deadline_ms=10_000)
            if feasible:
                _late_milp_log[recommendation_id] = True
                cached = _status_cache.get(recommendation_id)
                if cached:
                    _status_cache[recommendation_id] = DispatchStatus(
                        recommendation_id=recommendation_id,
                        source=cached.source,
                        complete=True,
                        solver_ms=cached.solver_ms,
                        late_milp_logged=True,
                    )

        _executor.submit(_late)

    async def recommend(self, request: RecommendRequest) -> DispatchRecommendation:
        t0 = time.perf_counter()
        recommendation_id = f"DISP-{uuid.uuid4().hex[:12].upper()}"

        incident_ids = await self._resolve_incident_ids(request)
        if not incident_ids:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No active incidents found")

        incidents = await self._materialize_incidents(incident_ids)
        if not incidents:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Features not materialized for requested incidents",
            )

        units, roster_stale = resolve_units(
            request.available_units,
            ttl_s=settings.dispatch_roster_cache_ttl_s,
        )

        milp_attempted = False
        milp_feasible: bool | None = None
        solver_ms = 0.0
        source = DispatchSource.GREEDY_FALLBACK
        assignments: list[Assignment] = []
        loop = asyncio.get_running_loop()

        if request.tier == GovernanceTier.TIER1 and not request.force_greedy:
            milp_attempted = True
            milp_result, solver_ms, milp_feasible = await loop.run_in_executor(
                _executor,
                milp_assign,
                units,
                incidents,
                settings.dispatch_milp_deadline_ms,
            )
            if milp_feasible and milp_result:
                assignments = milp_result
                source = DispatchSource.MILP
            else:
                self._schedule_late_milp_log(recommendation_id, units, incidents)

        if not assignments:
            greedy_t0 = time.perf_counter()
            if request.tier == GovernanceTier.TIER3:
                assignments = await loop.run_in_executor(
                    _executor, _tier3_assign, units, incidents
                )
            else:
                assignments = await loop.run_in_executor(
                    _executor, greedy_assign, units, incidents
                )
            if not milp_attempted:
                solver_ms = round((time.perf_counter() - greedy_t0) * 1000, 2)

        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        late_logged = _late_milp_log.get(recommendation_id, False)

        rec = DispatchRecommendation(
            recommendation_id=recommendation_id,
            source=source,
            assignments=assignments,
            tier_at_decision=request.tier,
            solver_ms=solver_ms,
            latency_ms=latency_ms,
            milp_attempted=milp_attempted,
            milp_feasible=milp_feasible,
            late_milp_logged=late_logged,
            roster_stale=roster_stale,
            astram_shadow=_astram_shadow(incidents),
            created_at=datetime.now(UTC),
        )

        await self.repo.save_recommendation(rec)
        _status_cache[recommendation_id] = DispatchStatus(
            recommendation_id=recommendation_id,
            source=source,
            complete=True,
            solver_ms=solver_ms,
            late_milp_logged=late_logged,
        )
        return rec

    async def status(self, recommendation_id: str) -> DispatchStatus:
        cached = _status_cache.get(recommendation_id)
        if cached:
            late = _late_milp_log.get(recommendation_id, False)
            if late and not cached.late_milp_logged:
                return DispatchStatus(
                    recommendation_id=recommendation_id,
                    source=cached.source,
                    complete=True,
                    solver_ms=cached.solver_ms,
                    late_milp_logged=True,
                )
            return cached

        rec = await self.repo.get_recommendation(recommendation_id)
        if not rec:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"Recommendation {recommendation_id} not found",
            )
        return DispatchStatus(
            recommendation_id=recommendation_id,
            source=rec.source,
            complete=True,
            solver_ms=rec.solver_ms,
            late_milp_logged=rec.late_milp_logged,
        )

    def list_roster(self):
        units, stale = resolve_units(None, ttl_s=settings.dispatch_roster_cache_ttl_s)
        return {"units": units, "stale": stale, "count": len(units)}
