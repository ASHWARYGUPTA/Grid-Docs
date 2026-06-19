"""Deterministic greedy dispatch fallback — O(n log n) pair ranking."""

from __future__ import annotations

import heapq

from grid_unlocked.config import settings
from grid_unlocked.dispatch.incidents import IncidentContext, effective_rci_for_scoring
from grid_unlocked.dispatch.schemas import Assignment, DispatchUnit, EquipType
from grid_unlocked.dispatch.travel import eta_minutes


def _heavy_tow_bonus(unit: DispatchUnit, incident: IncidentContext) -> float:
    if not incident.needs_heavy_tow:
        return 0.0
    if unit.equip_type == EquipType.HEAVY_TOW:
        return settings.dispatch_eta_heavy_tow
    return 0.0


def pair_cost(unit: DispatchUnit, incident: IncidentContext) -> tuple[float, float]:
    """Lower cost is better. Returns (cost, eta_min)."""
    eta = eta_minutes(
        unit.latitude,
        unit.longitude,
        incident.latitude,
        incident.longitude,
        avg_speed_kmh=settings.dispatch_avg_speed_kmh,
    )
    rci = effective_rci_for_scoring(incident)
    cost = (
        settings.dispatch_alpha_eta * eta
        + settings.dispatch_beta_rci * rci
        + settings.dispatch_gamma_centrality * incident.centrality
        + settings.dispatch_delta_cascade * incident.cascade_risk
        - _heavy_tow_bonus(unit, incident)
    )
    if incident.needs_heavy_tow and unit.equip_type != EquipType.HEAVY_TOW:
        cost += 10.0
    return round(cost, 4), eta


def greedy_assign(
    units: list[DispatchUnit],
    incidents: list[IncidentContext],
) -> list[Assignment]:
    if not incidents:
        return []

    on_shift = [u for u in units if u.on_shift]
    if not on_shift:
        return []

    heap: list[tuple[float, str, str, int, int, float]] = []
    costs: dict[tuple[int, int], tuple[float, float]] = {}

    for ui, unit in enumerate(on_shift):
        for ii, incident in enumerate(incidents):
            cost, eta = pair_cost(unit, incident)
            costs[(ui, ii)] = (cost, eta)
            heapq.heappush(heap, (cost, unit.station_id, unit.unit_id, ui, ii, eta))

    assigned_units: set[int] = set()
    assigned_incidents: set[int] = set()
    assignments: list[Assignment] = []

    while heap and len(assigned_incidents) < len(incidents):
        cost, _station, _unit, ui, ii, eta = heapq.heappop(heap)
        if ui in assigned_units or ii in assigned_incidents:
            continue
        unit = on_shift[ui]
        incident = incidents[ii]
        assigned_units.add(ui)
        assigned_incidents.add(ii)
        assignments.append(
            Assignment(
                unit_id=unit.unit_id,
                station_id=unit.station_id,
                event_id=incident.event_id,
                equip_type=unit.equip_type,
                eta_min=eta,
                pair_cost=cost,
                rci=incident.rci,
                cascade_risk=incident.cascade_risk,
                needs_heavy_tow=incident.needs_heavy_tow,
            )
        )

    # Unassigned high-RCI incidents: allow unit reuse if roster exhausted (no starvation)
    remaining = [ii for ii in range(len(incidents)) if ii not in assigned_incidents]
    if remaining:
        remaining.sort(key=lambda i: incidents[i].rci, reverse=True)
        for ii in remaining:
            incident = incidents[ii]
            best: tuple[float, int, float] | None = None
            for ui, unit in enumerate(on_shift):
                cost, eta = costs.get((ui, ii), pair_cost(unit, incident))
                if incident.needs_heavy_tow and unit.equip_type != EquipType.HEAVY_TOW:
                    continue
                if best is None or cost < best[0]:
                    best = (cost, ui, eta)
            if best is None:
                continue
            cost, ui, eta = best
            unit = on_shift[ui]
            assignments.append(
                Assignment(
                    unit_id=unit.unit_id,
                    station_id=unit.station_id,
                    event_id=incident.event_id,
                    equip_type=unit.equip_type,
                    eta_min=eta,
                    pair_cost=cost,
                    rci=incident.rci,
                    cascade_risk=incident.cascade_risk,
                    needs_heavy_tow=incident.needs_heavy_tow,
                )
            )

    assignments.sort(key=lambda a: (-a.rci, a.event_id))
    return assignments
