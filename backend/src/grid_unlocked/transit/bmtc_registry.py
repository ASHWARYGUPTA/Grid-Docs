"""M12 — Mock BMTC route-corridor registry.

Maps Bengaluru corridors to a set of BMTC bus routes with an overlap
fraction (how much of that route's travel time is inside the affected
corridor). In the hackathon, routes are hardcoded here.

DEFERRED D-M12-02: Replace with a real route polyline ∩ corridor-buffer
spatial join in Phase 2, once real BMTC route geometry is available. The
interface (get_routes_for_corridor) stays the same — only the backing
store/computation changes.
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_OCCUPANCY = 45  # spec default: peak-hour passengers/bus when no load factor


@dataclass(frozen=True)
class BmtcRoute:
    route_id: str
    name: str
    avg_occupancy: int = DEFAULT_OCCUPANCY


# ---------------------------------------------------------------------------
# Hardcoded synthetic Bengaluru BMTC route inventory
# Phase 2: load from real BMTC GTFS static + GTFS-RT load factors
# ---------------------------------------------------------------------------
_ROUTES: dict[str, BmtcRoute] = {
    "BMTC-500D": BmtcRoute("BMTC-500D", "Silk Board - Whitefield"),
    "BMTC-500K": BmtcRoute("BMTC-500K", "Banashankari - Whitefield"),
    "BMTC-201": BmtcRoute("BMTC-201", "Majestic - Marathahalli"),
    "BMTC-210": BmtcRoute("BMTC-210", "Kempegowda Bus Stn - ITPL"),
    "BMTC-356": BmtcRoute("BMTC-356", "Jayanagar - Koramangala"),
    "BMTC-365": BmtcRoute("BMTC-365", "Banashankari - HSR Layout"),
    "BMTC-401K": BmtcRoute("BMTC-401K", "Shivajinagar - Sarjapur"),
    "BMTC-G4": BmtcRoute("BMTC-G4", "Kempegowda Bus Stn - Electronic City (via Hosur Rd)"),
    "BMTC-V500": BmtcRoute("BMTC-V500", "Vayu Vajra Airport - CBD"),
    "BMTC-KIA-9": BmtcRoute("BMTC-KIA-9", "KIA Shuttle - Hebbal"),
}

# corridor -> [(route_id, overlap_fraction)]
# Phase 2: replace with spatial join of route polyline vs corridor buffer
_CORRIDOR_ROUTES: dict[str, list[tuple[str, float]]] = {
    "ORR East 1": [("BMTC-500D", 0.6), ("BMTC-201", 0.4), ("BMTC-210", 0.3)],
    "ORR East 2": [("BMTC-500D", 0.4), ("BMTC-500K", 0.3)],
    "Hosur Road": [("BMTC-G4", 0.8), ("BMTC-401K", 0.2)],
    "Bannerghata Road": [("BMTC-365", 0.5), ("BMTC-356", 0.3)],
    "Old Airport Road": [("BMTC-V500", 0.5), ("BMTC-KIA-9", 0.3)],
    "Varthur Road": [("BMTC-210", 0.4), ("BMTC-401K", 0.3)],
    "Bellary Road 1": [("BMTC-KIA-9", 0.5)],
    "Bellary Road 2": [("BMTC-KIA-9", 0.4)],
    "CBD 1": [("BMTC-201", 0.5), ("BMTC-401K", 0.4)],
    "CBD 2": [("BMTC-201", 0.4), ("BMTC-V500", 0.3)],
}

# Used when a corridor has no specific mapping — keeps the endpoint
# returning a non-empty, non-error result rather than a 404/422 (same
# philosophy as vms/board_registry.py's _DEFAULT_BOARDS fallback).
_DEFAULT_ROUTES: list[tuple[str, float]] = [("BMTC-201", 0.2), ("BMTC-500D", 0.2)]


def get_routes_for_corridor(corridor: str | None) -> list[tuple[BmtcRoute, float]]:
    """Return (route, overlap_fraction) pairs for the given corridor."""
    if not corridor:
        pairs = _DEFAULT_ROUTES
    else:
        pairs = _DEFAULT_ROUTES
        for key, mapped in _CORRIDOR_ROUTES.items():
            if key.lower() in corridor.lower() or corridor.lower() in key.lower():
                pairs = mapped
                break

    return [(_ROUTES[route_id], overlap) for route_id, overlap in pairs if route_id in _ROUTES]


def get_route(route_id: str) -> BmtcRoute | None:
    return _ROUTES.get(route_id)


def all_routes() -> list[BmtcRoute]:
    return list(_ROUTES.values())
