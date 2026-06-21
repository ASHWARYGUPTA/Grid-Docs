"""M14 — GovernanceService.

Owns tier (1/2/3) + shadow mode, health rollup across M01/M02/M03/M07/M10/M11,
automatic tier transitions with recovery hysteresis, manual override audit,
cascade drills, and an M13 promotion checklist stub.

Architecture:
  - Durable state lives in `governance_state` (DB).
  - `get_governance()` (recommendations/governance.py) is called synchronously,
    with no DB session, from every hot path (M07/M09/M10/M11). So the live
    tier/shadow values are mirrored into an in-process cache on every write and
    on every health-probe cycle. If the cache was never populated (M14 unreachable
    at boot), the cache defaults to Tier 3 + shadow_mode=True — the spec's
    documented last-resort degradation behavior.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.config import settings
from grid_unlocked.dashboard.bus import dashboard_bus
from grid_unlocked.dashboard.schemas import DashboardDelta, DeltaScope
from grid_unlocked.db.models import DispatchRecommendationRow, ExecutionQueueRow, VmsDeliveryRow
from grid_unlocked.governance.repository import GovernanceRepository
from grid_unlocked.governance.schemas import (
    DrillRequest,
    DrillResult,
    GovernanceTierResponse,
    HealthRollup,
    ModuleHealth,
    PromotionApproveRequest,
    PromotionApproveResponse,
    PromotionChecklistItem,
    PromotionChecklistResponse,
    Tier,
    TierTransition,
    TierTransitionsResponse,
)

logger = logging.getLogger(__name__)

# Recovery hysteresis: a downgraded tier must stay healthy this long before
# auto-upgrading back — prevents flapping during transient blips.
RECOVERY_HYSTERESIS_SECONDS = 5 * 60


@dataclass
class _CachedState:
    tier: str = "3"
    shadow_mode: bool = True
    manual_mode: bool = True
    updated_at: datetime | None = None
    updated_by: str | None = None


# Module-level cache — read synchronously by get_governance() with zero I/O.
_cache = _CachedState()

# Until M14 has explicitly bootstrapped (app startup) or written a tier/shadow
# change, get_governance() proxies live `settings.governance_*` values. This
# preserves the pre-M14 behavior (and every existing `monkeypatch.setattr(
# settings, "governance_shadow_mode", ...)` test) for any process that never
# touches GovernanceService. The moment M14 writes — bootstrap, override,
# shadow toggle, or an automatic transition — the DB-backed cache becomes
# authoritative and settings are no longer consulted.
_bootstrapped = False

# Tracks when the system last observed a fully-healthy probe, for hysteresis.
_healthy_since: datetime | None = None


def read_cached_state() -> _CachedState:
    if not _bootstrapped:
        from grid_unlocked.config import settings as _settings

        return _CachedState(
            tier=_settings.governance_tier,
            shadow_mode=_settings.governance_shadow_mode,
            manual_mode=_settings.governance_tier == "3",
        )
    return _cache


def _write_cache(tier: str, shadow_mode: bool, updated_at: datetime, updated_by: str | None) -> None:
    global _cache, _bootstrapped
    _cache = _CachedState(
        tier=tier,
        shadow_mode=shadow_mode,
        manual_mode=tier == "3",
        updated_at=updated_at,
        updated_by=updated_by,
    )
    _bootstrapped = True


def reset_cache_for_tests() -> None:
    """Test-only: drop back to proxying live settings, undoing any bootstrap
    or override so tests don't leak governance state into each other."""
    global _cache, _bootstrapped, _healthy_since
    _cache = _CachedState()
    _bootstrapped = False
    _healthy_since = None


async def _publish_tier_delta(tier: str, shadow_mode: bool, manual_mode: bool) -> None:
    await dashboard_bus.publish(
        DashboardDelta(
            scope=DeltaScope.TIER,
            payload={"tier": tier, "shadow_mode": shadow_mode, "manual_mode": manual_mode},
            emitted_at=datetime.now(UTC),
        )
    )


class GovernanceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = GovernanceRepository(session)

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    async def bootstrap(self) -> None:
        """Seed governance_state from settings defaults if empty, then warm the cache."""
        row = await self.repo.ensure_seeded(
            default_tier=settings.governance_tier,
            default_shadow_mode=settings.governance_shadow_mode,
        )
        _write_cache(row.tier, row.shadow_mode, row.updated_at, row.updated_by)

    # ------------------------------------------------------------------
    # Tier / shadow mode
    # ------------------------------------------------------------------

    async def get_tier(self) -> GovernanceTierResponse:
        row = await self.repo.ensure_seeded(
            default_tier=settings.governance_tier,
            default_shadow_mode=settings.governance_shadow_mode,
        )
        return GovernanceTierResponse(
            tier=Tier(row.tier),
            shadow_mode=row.shadow_mode,
            manual_mode=row.tier == "3",
            flags={},
            updated_at=row.updated_at,
            updated_by=row.updated_by,
        )

    async def override_tier(
        self, tier: Tier, reason: str, operator_id: str
    ) -> GovernanceTierResponse:
        current = await self.repo.ensure_seeded(
            default_tier=settings.governance_tier,
            default_shadow_mode=settings.governance_shadow_mode,
        )
        from_tier = current.tier
        row = await self.repo.update_state(tier=tier.value, updated_by=operator_id)
        if from_tier != tier.value:
            await self.repo.log_transition(
                from_tier=from_tier,
                to_tier=tier.value,
                reason=reason,
                operator_id=operator_id,
            )
            logger.info("Tier override: %s -> %s by %s (%s)", from_tier, tier.value, operator_id, reason)
        _write_cache(row.tier, row.shadow_mode, row.updated_at, row.updated_by)
        await _publish_tier_delta(row.tier, row.shadow_mode, row.tier == "3")
        return await self.get_tier()

    async def set_shadow_mode(self, enabled: bool, operator_id: str) -> GovernanceTierResponse:
        row = await self.repo.update_state(shadow_mode=enabled, updated_by=operator_id)
        logger.info("Shadow mode set to %s by %s", enabled, operator_id)
        _write_cache(row.tier, row.shadow_mode, row.updated_at, row.updated_by)
        await _publish_tier_delta(row.tier, row.shadow_mode, row.tier == "3")
        return await self.get_tier()

    async def list_transitions(self, limit: int = 50) -> TierTransitionsResponse:
        rows = await self.repo.list_transitions(limit=limit)
        return TierTransitionsResponse(
            transitions=[
                TierTransition(
                    id=r.id,
                    from_tier=Tier(r.from_tier),
                    to_tier=Tier(r.to_tier),
                    reason=r.reason,
                    operator_id=r.operator_id,
                    created_at=r.created_at,
                )
                for r in rows
            ],
            count=len(rows),
        )

    # ------------------------------------------------------------------
    # Health rollup + automatic tier transitions
    # ------------------------------------------------------------------

    async def health(self) -> HealthRollup:
        modules = [
            await self._probe_ingestion(),
            await self._probe_features(),
            self._probe_impact(),
            await self._probe_dispatch(),
            await self._probe_execution(),
            await self._probe_vms(),
        ]
        overall = "down" if any(m.status == "down" for m in modules) else (
            "degraded" if any(m.status == "degraded" for m in modules) else "healthy"
        )
        current = await self.repo.ensure_seeded(
            default_tier=settings.governance_tier,
            default_shadow_mode=settings.governance_shadow_mode,
        )
        return HealthRollup(
            overall_status=overall,
            tier=Tier(current.tier),
            shadow_mode=current.shadow_mode,
            modules=modules,
            checked_at=datetime.now(UTC),
        )

    async def evaluate_auto_transition(self) -> None:
        """
        Apply the spec's auto tier-transition rules with recovery hysteresis:
          - M03 down (rule fallback active)         -> Tier 2
          - M01 + M02 both down                      -> Tier 3
          - Fully healthy for >= 5 min continuously   -> upgrade back to Tier 1
        Manual overrides are not undone by this loop except via the hysteresis
        recovery path, mirroring the spec's "automatic transition with manual
        override" model — an operator-set tier persists until conditions force
        a downgrade or the system has been healthy long enough to recover.
        """
        global _healthy_since
        rollup = await self.health()
        current = await self.repo.ensure_seeded(
            default_tier=settings.governance_tier,
            default_shadow_mode=settings.governance_shadow_mode,
        )
        current_tier = current.tier

        ingest_down = any(m.module == "M01_Ingestion" and m.status == "down" for m in rollup.modules)
        features_down = any(m.module == "M02_Features" and m.status == "down" for m in rollup.modules)
        impact_down = any(m.module == "M03_Impact" and m.status == "down" for m in rollup.modules)

        target: str | None = None
        reason = ""
        if ingest_down and features_down:
            target, reason = "3", "M01 + M02 both down — continuity SOP mode"
        elif impact_down:
            target, reason = "2", "M03 impact models unavailable — greedy dispatch only"

        now = datetime.now(UTC)
        if target is not None and target != current_tier:
            await self.repo.update_state(tier=target, updated_by=None)
            await self.repo.log_transition(
                from_tier=current_tier, to_tier=target, reason=reason, operator_id=None
            )
            row = await self.repo.get_state()
            _write_cache(row.tier, row.shadow_mode, row.updated_at, row.updated_by)
            await _publish_tier_delta(row.tier, row.shadow_mode, row.tier == "3")
            _healthy_since = None
            logger.warning("Automatic tier transition: %s -> %s (%s)", current_tier, target, reason)
            return

        if target is None and current_tier != "1":
            if _healthy_since is None:
                _healthy_since = now
            elif (now - _healthy_since).total_seconds() >= RECOVERY_HYSTERESIS_SECONDS:
                await self.repo.update_state(tier="1", updated_by=None)
                await self.repo.log_transition(
                    from_tier=current_tier,
                    to_tier="1",
                    reason=f"Healthy for >= {RECOVERY_HYSTERESIS_SECONDS}s — auto-recovered to Tier 1",
                    operator_id=None,
                )
                row = await self.repo.get_state()
                _write_cache(row.tier, row.shadow_mode, row.updated_at, row.updated_by)
                await _publish_tier_delta(row.tier, row.shadow_mode, row.tier == "3")
                _healthy_since = None
        elif target is None:
            _healthy_since = None

    async def _probe_ingestion(self) -> ModuleHealth:
        from grid_unlocked.ingestion.service import IngestionService

        try:
            health = await IngestionService(self.session).health()
            status_str = "healthy" if health.error_rate_pct < 20 else "degraded"
            return ModuleHealth(
                module="M01_Ingestion",
                status=status_str,
                detail=f"{health.total_events} events, {health.error_rate_pct:.1f}% error rate",
                metrics={
                    "total_events": health.total_events,
                    "error_rate_pct": health.error_rate_pct,
                    "active_events": health.active_events,
                },
            )
        except Exception as exc:
            return ModuleHealth(module="M01_Ingestion", status="down", detail=str(exc))

    async def _probe_features(self) -> ModuleHealth:
        from grid_unlocked.db.models import FeatureSnapshotRow

        try:
            count = await self.session.scalar(select(FeatureSnapshotRow.event_id).limit(1))
            return ModuleHealth(
                module="M02_Features",
                status="healthy",
                detail="Feature snapshot store reachable",
                metrics={"sample_row_present": count is not None},
            )
        except Exception as exc:
            return ModuleHealth(module="M02_Features", status="down", detail=str(exc))

    def _probe_impact(self) -> ModuleHealth:
        from grid_unlocked.impact.registry import registry

        try:
            registry.load()
            if registry._ml_available:
                return ModuleHealth(
                    module="M03_Impact",
                    status="healthy",
                    detail="ML models loaded",
                    metrics={"versions": json.dumps(registry.versions)},
                )
            return ModuleHealth(
                module="M03_Impact",
                status="down",
                detail="ML models not found — rule-based fallback active",
                metrics={"versions": json.dumps(registry.versions)},
            )
        except Exception as exc:
            return ModuleHealth(module="M03_Impact", status="down", detail=str(exc))

    async def _probe_dispatch(self) -> ModuleHealth:
        try:
            rows = (
                await self.session.scalars(
                    select(DispatchRecommendationRow)
                    .order_by(DispatchRecommendationRow.created_at.desc())
                    .limit(50)
                )
            ).all()
            if not rows:
                return ModuleHealth(
                    module="M07_Dispatch", status="healthy", detail="No recent recommendations", metrics={}
                )
            fallback = sum(1 for r in rows if r.source == "GREEDY_FALLBACK")
            fallback_rate = round(fallback / len(rows), 3)
            status_str = "degraded" if fallback_rate > 0.5 else "healthy"
            return ModuleHealth(
                module="M07_Dispatch",
                status=status_str,
                detail=f"Greedy fallback rate {fallback_rate:.0%} over last {len(rows)} recommendations",
                metrics={"fallback_rate": fallback_rate, "sample_size": len(rows)},
            )
        except Exception as exc:
            return ModuleHealth(module="M07_Dispatch", status="down", detail=str(exc))

    async def _probe_execution(self) -> ModuleHealth:
        try:
            rows = (
                await self.session.scalars(
                    select(ExecutionQueueRow).order_by(ExecutionQueueRow.created_at.desc()).limit(50)
                )
            ).all()
            if not rows:
                return ModuleHealth(
                    module="M10_Execution", status="healthy", detail="No recent executions", metrics={}
                )
            dlq = sum(1 for r in rows if r.status == "dead_letter")
            dlq_rate = round(dlq / len(rows), 3)
            status_str = "degraded" if dlq_rate > 0.2 else "healthy"
            return ModuleHealth(
                module="M10_Execution",
                status=status_str,
                detail=f"DLQ rate {dlq_rate:.0%} over last {len(rows)} executions",
                metrics={"dlq_rate": dlq_rate, "sample_size": len(rows)},
            )
        except Exception as exc:
            return ModuleHealth(module="M10_Execution", status="down", detail=str(exc))

    async def _probe_vms(self) -> ModuleHealth:
        try:
            rows = (
                await self.session.scalars(
                    select(VmsDeliveryRow).order_by(VmsDeliveryRow.created_at.desc()).limit(50)
                )
            ).all()
            if not rows:
                return ModuleHealth(
                    module="M11_VMS", status="healthy", detail="No recent VMS deliveries", metrics={}
                )
            dlq = sum(1 for r in rows if r.status == "dead_letter")
            dlq_rate = round(dlq / len(rows), 3)
            status_str = "degraded" if dlq_rate > 0.2 else "healthy"
            return ModuleHealth(
                module="M11_VMS",
                status=status_str,
                detail=f"DLQ rate {dlq_rate:.0%} over last {len(rows)} deliveries",
                metrics={"dlq_rate": dlq_rate, "sample_size": len(rows)},
            )
        except Exception as exc:
            return ModuleHealth(module="M11_VMS", status="down", detail=str(exc))

    # ------------------------------------------------------------------
    # Promotion checklist (M13 sign-off)
    # ------------------------------------------------------------------

    async def promotion_checklist(self, model_version: str) -> PromotionChecklistResponse:
        """
        accuracy_gate_94pct / anchor_slice_stable are read from M13's real
        eval result (model_registry + learning_jobs) once a retrain has run
        for this model_version. shadow_mode_stability remains intentionally
        stubbed — that is M14's own contract per spec ("Tertiary: shadow mode
        stability (M14) passing"), not something M13 produces.
        """
        from grid_unlocked.learning.repository import LearningRepository

        learning_repo = LearningRepository(self.session)
        model = await learning_repo.get_model(model_version)

        if not model:
            items = [
                PromotionChecklistItem(
                    item="accuracy_gate_94pct",
                    complete=False,
                    detail=f"No M13 retrain job has produced model {model_version} — no eval result available",
                ),
                PromotionChecklistItem(
                    item="anchor_slice_stable",
                    complete=False,
                    detail="No eval result available",
                ),
                PromotionChecklistItem(
                    item="shadow_mode_stability",
                    complete=False,
                    detail="Shadow agreement-rate tracking not yet implemented",
                ),
            ]
            return PromotionChecklistResponse(
                model_version=model_version, items=items, all_complete=False
            )

        accuracy_ok = model.accuracy is not None and model.accuracy >= settings.learning_accuracy_gate

        incumbent = await learning_repo.get_production_model()
        if incumbent and incumbent.model_version != model_version and incumbent.anchor_accuracy is not None:
            regression = incumbent.anchor_accuracy - (model.anchor_accuracy or 0.0)
            anchor_ok = regression <= settings.learning_anchor_epsilon
            anchor_detail = (
                f"Anchor regression {regression:.4f} vs epsilon {settings.learning_anchor_epsilon}"
            )
        else:
            anchor_ok = True
            anchor_detail = "No incumbent production model to regress against"

        items = [
            PromotionChecklistItem(
                item="accuracy_gate_94pct",
                complete=accuracy_ok,
                detail=f"Accuracy {model.accuracy:.4f} vs gate {settings.learning_accuracy_gate}",
            ),
            PromotionChecklistItem(
                item="anchor_slice_stable",
                complete=anchor_ok,
                detail=anchor_detail,
            ),
            PromotionChecklistItem(
                item="shadow_mode_stability",
                complete=False,
                detail="Shadow agreement-rate tracking not yet implemented (M14-owned, not blocked on M13)",
            ),
        ]
        return PromotionChecklistResponse(
            model_version=model_version,
            items=items,
            all_complete=all(i.complete for i in items),
        )

    async def approve_promotion(self, req: PromotionApproveRequest) -> PromotionApproveResponse:
        checklist = await self.promotion_checklist(req.model_version)
        if not checklist.all_complete:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Promotion checklist incomplete for {req.model_version} — cannot approve",
            )
        return PromotionApproveResponse(
            model_version=req.model_version,
            approved=True,
            message=f"Promotion of {req.model_version} approved by {req.operator_id}",
        )

    # ------------------------------------------------------------------
    # Cascade drills
    # ------------------------------------------------------------------

    async def run_cascade_drill(self, req: DrillRequest) -> DrillResult:
        """
        Synthetic drill: force concurrent MILP-tier dispatch calls with
        force_greedy=True (simulating a forced MILP timeout) against the
        live dispatch pipeline using currently active incidents, and verify
        100% greedy fallback within the total dispatch deadline — per spec
        testing decision ("forced timeout -> 100% GREEDY_FALLBACK, latency <1.8s").

        Requires at least one active incident already ingested (M01) — a
        drill cannot fabricate incidents the dispatch pipeline would accept,
        so with zero active incidents this returns passed=False with a clear
        "insufficient data" detail rather than a hollow pass.
        """
        from grid_unlocked.dispatch.repository import DispatchRepository
        from grid_unlocked.dispatch.schemas import GovernanceTier, RecommendRequest
        from grid_unlocked.dispatch.service import DispatchService

        active_ids = await DispatchRepository(self.session).list_active_event_ids(
            limit=req.concurrent_closures
        )
        if not active_ids:
            result_payload = {
                "concurrent_closures": 0,
                "fallback_rate": 0.0,
                "max_latency_ms": 0.0,
                "deadline_ms": settings.dispatch_total_deadline_ms,
            }
            row = await self.repo.save_drill(
                drill_type=req.drill_type, result=result_payload, passed=False
            )
            return DrillResult(
                id=row.id,
                drill_type=req.drill_type,
                passed=False,
                concurrent_closures=0,
                fallback_rate=0.0,
                max_latency_ms=0.0,
                deadline_ms=settings.dispatch_total_deadline_ms,
                detail="No active incidents to drill against — ingest events first",
                created_at=row.created_at,
            )

        dispatch = DispatchService(self.session)

        async def _run_one(event_id: str):
            return await dispatch.recommend(
                RecommendRequest(
                    event_id=event_id,
                    tier=GovernanceTier.TIER1,
                    force_greedy=req.force_milp_timeout,
                )
            )

        results = await asyncio.gather(*(_run_one(eid) for eid in active_ids), return_exceptions=True)

        latencies: list[float] = []
        all_greedy = True
        for r in results:
            if isinstance(r, Exception):
                all_greedy = False
                continue
            latencies.append(r.latency_ms)
            if r.source.value != "GREEDY_FALLBACK":
                all_greedy = False

        max_latency = max(latencies) if latencies else 0.0
        fallback_rate = round(sum(1 for r in results if not isinstance(r, Exception) and r.source.value == "GREEDY_FALLBACK") / len(results), 3)
        passed = all_greedy and max_latency < settings.dispatch_total_deadline_ms and len(latencies) == len(active_ids)

        result_payload = {
            "concurrent_closures": len(active_ids),
            "fallback_rate": fallback_rate,
            "max_latency_ms": max_latency,
            "deadline_ms": settings.dispatch_total_deadline_ms,
        }
        row = await self.repo.save_drill(drill_type=req.drill_type, result=result_payload, passed=passed)
        return DrillResult(
            id=row.id,
            drill_type=req.drill_type,
            passed=passed,
            concurrent_closures=len(active_ids),
            fallback_rate=fallback_rate,
            max_latency_ms=round(max_latency, 2),
            deadline_ms=settings.dispatch_total_deadline_ms,
            detail=(
                "100% greedy fallback within deadline"
                if passed
                else "Drill failed — MILP fallback incomplete or deadline exceeded"
            ),
            created_at=row.created_at,
        )

    async def last_drill(self, drill_type: str = "cascade") -> DrillResult | None:
        row = await self.repo.get_last_drill(drill_type)
        if not row:
            return None
        payload = json.loads(row.result_json)
        return DrillResult(
            id=row.id,
            drill_type=row.drill_type,
            passed=row.passed,
            concurrent_closures=payload["concurrent_closures"],
            fallback_rate=payload["fallback_rate"],
            max_latency_ms=payload["max_latency_ms"],
            deadline_ms=payload["deadline_ms"],
            detail="Cached result",
            created_at=row.created_at,
        )
