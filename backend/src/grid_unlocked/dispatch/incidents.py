"""Build dispatch-ready incident contexts from M02/M03/M04."""

from __future__ import annotations

from dataclasses import dataclass

from grid_unlocked.config import settings
from grid_unlocked.db.models import NormalizedEventRow
from grid_unlocked.features.schemas import FeatureVector
from grid_unlocked.propagation.gcdh import run_gcdh
from grid_unlocked.propagation.schemas import GcdhParams


@dataclass(frozen=True)
class IncidentContext:
    event_id: str
    latitude: float
    longitude: float
    corridor: str | None
    priority: str | None
    rci: float
    p_closure: float
    cascade_risk: float
    centrality: float
    needs_heavy_tow: bool
    priority_structural: bool
    reporting_bias_weight: float
    hour_ist: int
    simultaneous_events_2km: int


def needs_heavy_tow(row: NormalizedEventRow) -> bool:
    if row.veh_type and row.veh_type.lower() in {"heavy_vehicle", "heavy", "truck", "cargo"}:
        return True
    desc = (row.description or "").lower()
    cargo_tokens = ("cargo", "steel coil", "container", "trailer", "heavy vehicle")
    return any(token in desc for token in cargo_tokens)


def uncovered_risk(ctx: IncidentContext) -> float:
    return (
        settings.dispatch_beta_rci * ctx.rci
        + settings.dispatch_delta_cascade * ctx.cascade_risk
        + 0.2 * ctx.p_closure
    )


def effective_rci_for_scoring(ctx: IncidentContext) -> float:
    rci = ctx.rci
    if ctx.hour_ist in settings.dispatch_bias_hours:
        rci *= min(ctx.reporting_bias_weight, settings.dispatch_bias_max_multiplier)
    return min(1.0, rci)


def build_incident_context(
    row: NormalizedEventRow,
    features: FeatureVector,
    rci: float,
    p_closure: float,
    graph_node_id: str,
) -> IncidentContext:
    params = GcdhParams(
        **{
            "lambda": settings.gcdh_lambda,
            "k": settings.gcdh_k,
            "epsilon": settings.gcdh_epsilon,
            "max_hops": settings.gcdh_max_hops,
        }
    )
    pmap = run_gcdh(
        event_id=row.event_id,
        seed_node_id=graph_node_id,
        seed_rci=rci,
        params=params,
    )
    cascade = pmap.cascade_risk if pmap.cascade_risk else rci

    return IncidentContext(
        event_id=row.event_id,
        latitude=row.latitude,
        longitude=row.longitude,
        corridor=row.corridor,
        priority=row.priority,
        rci=rci,
        p_closure=p_closure,
        cascade_risk=cascade,
        centrality=features.betweenness_norm,
        needs_heavy_tow=needs_heavy_tow(row),
        priority_structural=features.is_named_corridor,
        reporting_bias_weight=features.reporting_bias_weight,
        hour_ist=features.hour_ist,
        simultaneous_events_2km=features.simultaneous_events_2km,
    )
