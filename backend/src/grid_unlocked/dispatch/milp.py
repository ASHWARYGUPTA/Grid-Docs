"""OR-Tools MILP assignment with hard deadline."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

from ortools.linear_solver import pywraplp

from grid_unlocked.config import settings
from grid_unlocked.dispatch.greedy import pair_cost
from grid_unlocked.dispatch.incidents import IncidentContext, uncovered_risk
from grid_unlocked.dispatch.schemas import Assignment, DispatchUnit, EquipType
from grid_unlocked.dispatch.travel import eta_minutes


def _build_cost_matrix(
    units: list[DispatchUnit],
    incidents: list[IncidentContext],
) -> list[list[float]]:
    matrix: list[list[float]] = []
    for unit in units:
        row: list[float] = []
        for incident in incidents:
            eta = eta_minutes(
                unit.latitude,
                unit.longitude,
                incident.latitude,
                incident.longitude,
                avg_speed_kmh=settings.dispatch_avg_speed_kmh,
            )
            base, _ = pair_cost(unit, incident)
            row.append(
                settings.dispatch_alpha_eta * eta
                + settings.dispatch_alpha_uncovered_risk * uncovered_risk(incident)
                + (base - settings.dispatch_alpha_eta * eta)
            )
        matrix.append(row)
    return matrix


def _solve_milp_sync(
    units: list[DispatchUnit],
    incidents: list[IncidentContext],
    deadline_ms: int,
) -> tuple[list[tuple[int, int]] | None, float, bool]:
    t0 = time.perf_counter()
    on_shift = [u for u in units if u.on_shift]
    if not on_shift or not incidents:
        return None, 0.0, False

    n_units = len(on_shift)
    n_incidents = len(incidents)
    costs = _build_cost_matrix(on_shift, incidents)

    solver = pywraplp.Solver.CreateSolver("SCIP")
    if not solver:
        solver = pywraplp.Solver.CreateSolver("CBC")
    if not solver:
        return None, round((time.perf_counter() - t0) * 1000, 2), False

    solver.SetTimeLimit(deadline_ms)
    x: dict[tuple[int, int], pywraplp.Variable] = {}
    for i in range(n_units):
        for j in range(n_incidents):
            x[i, j] = solver.BoolVar(f"x_{i}_{j}")

    for j in range(n_incidents):
        solver.Add(sum(x[i, j] for i in range(n_units)) == 1)

    for i in range(n_units):
        solver.Add(sum(x[i, j] for j in range(n_incidents)) <= 1)

    for i, unit in enumerate(on_shift):
        for j, incident in enumerate(incidents):
            if incident.needs_heavy_tow and unit.equip_type != EquipType.HEAVY_TOW:
                solver.Add(x[i, j] == 0)

    objective = solver.Objective()
    for i in range(n_units):
        for j in range(n_incidents):
            objective.SetCoefficient(x[i, j], costs[i][j])
    objective.SetMinimization()

    status = solver.Solve()
    solver_ms = round((time.perf_counter() - t0) * 1000, 2)

    if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        return None, solver_ms, False

    pairs: list[tuple[int, int]] = []
    for i in range(n_units):
        for j in range(n_incidents):
            if x[i, j].solution_value() > 0.5:
                pairs.append((i, j))
    return pairs, solver_ms, True


def milp_assign(
    units: list[DispatchUnit],
    incidents: list[IncidentContext],
    deadline_ms: int | None = None,
) -> tuple[list[Assignment] | None, float, bool]:
    """Run MILP in a worker thread with wall-clock timeout."""
    ms = deadline_ms if deadline_ms is not None else settings.dispatch_milp_deadline_ms
    timeout_s = max(ms / 1000.0, 0.001)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_solve_milp_sync, units, incidents, ms)
        try:
            pairs, solver_ms, feasible = future.result(timeout=timeout_s + 0.05)
        except FuturesTimeout:
            return None, float(ms), False

    if not feasible or pairs is None:
        return None, solver_ms, False

    on_shift = [u for u in units if u.on_shift]
    assignments: list[Assignment] = []
    for ui, ii in pairs:
        unit = on_shift[ui]
        incident = incidents[ii]
        cost, eta = pair_cost(unit, incident)
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
    return assignments, solver_ms, True
