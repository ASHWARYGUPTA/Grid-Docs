"""Cyclic gridlock detection for proposed diversion paths."""

from __future__ import annotations

from grid_unlocked.config import settings
from grid_unlocked.diversions.schemas import ValidateResult


def detect_gridlock(
    path: list[str],
    *,
    closed_node_id: str | None = None,
) -> ValidateResult:
    notes: list[str] = []
    reenters = closed_node_id is not None and closed_node_id in path[1:]
    cycle = len(path) != len(set(path))

    if closed_node_id and closed_node_id in path:
        notes.append("Path touches closed zone node")
    if reenters:
        notes.append("Route re-enters closed zone after exit")
    if cycle:
        notes.append("Cycle detected in path node sequence")

    capacity_exceeded = len(path) > settings.diversion_max_hops + 2
    if capacity_exceeded:
        notes.append("Path exceeds secondary corridor capacity hop budget")

    gridlock = reenters or cycle or capacity_exceeded
    valid = not gridlock

    return ValidateResult(
        valid=valid,
        gridlock_cycle_detected=cycle or reenters,
        reenters_closed_zone=reenters,
        capacity_exceeded=capacity_exceeded,
        notes=notes,
    )


def capacity_class(path: list[str], gridlock: bool) -> str:
    if gridlock:
        return "low"
    hops = max(0, len(path) - 1)
    if hops <= 2:
        return "high"
    if hops <= 4:
        return "medium"
    return "low"
