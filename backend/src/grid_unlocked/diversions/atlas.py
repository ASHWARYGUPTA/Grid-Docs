"""Pre-computed diversion atlas — top closure-prone junctions."""

from __future__ import annotations

import time

from grid_unlocked.diversions.graph import k_shortest_paths, neighbors_of
from grid_unlocked.diversions.gridlock import capacity_class, detect_gridlock
from grid_unlocked.diversions.schemas import AtlasEntry, DiversionRoute
from grid_unlocked.features.graph_stub import corridor_to_node_id

# Junction registry — MVP subset of top-50 atlas (expand weekly in production)
JUNCTION_REGISTRY: dict[str, dict[str, str]] = {
    "junction:Mysore-NICE": {
        "corridor": "Mysore Road",
        "description": "NICE Road U-turn at junction 4412",
        "summary": "Via NICE connector → rejoin Mysore Road",
    },
    "junction:Mysore-Vijayanagar": {
        "corridor": "Mysore Road",
        "description": "Vijayanagar service road",
        "summary": "Local distributor → Bapuji Nagar",
    },
    "junction:Mysore-Gnanabharathi": {
        "corridor": "Mysore Road",
        "description": "Gnanabharathi ring",
        "summary": "Outer ring bypass segment",
    },
    "junction:ORR-Sarjapur": {
        "corridor": "ORR East 1",
        "description": "Sarjapur Road detour",
        "summary": "ORR exit → Sarjapur → rejoin",
    },
    "junction:ORR-OldAirport": {
        "corridor": "ORR East 1",
        "description": "Old Airport Road flyover",
        "summary": "Parallel arterial",
    },
    "junction:ORR-Hosur": {
        "corridor": "ORR East 1",
        "description": "Hosur Road connector",
        "summary": "Southbound bypass",
    },
    "junction:Hebbal-flyover": {
        "corridor": "Bellary Road 1",
        "description": "Hebbal flyover U-turn",
        "summary": "Northbound loop",
    },
    "junction:Manyata": {
        "corridor": "Bellary Road 1",
        "description": "Manyata embankment road",
        "summary": "Service lane",
    },
    "junction:RTNagar": {
        "corridor": "Bellary Road 1",
        "description": "RT Nagar cross",
        "summary": "Inner ring alternative",
    },
    "junction:generic-1": {
        "corridor": "Non-corridor",
        "description": "Nearest U-turn bay",
        "summary": "First legal U-turn within 500 m",
    },
    "junction:generic-2": {
        "corridor": "Non-corridor",
        "description": "Parallel service road",
        "summary": "Adjacent distributor if available",
    },
    "junction:generic-3": {
        "corridor": "Non-corridor",
        "description": "Corridor end-cap",
        "summary": "Route to next major junction",
    },
}

CORRIDOR_PRIMARY_JUNCTION: dict[str, str] = {
    "Mysore Road": "junction:Mysore-NICE",
    "ORR East 1": "junction:ORR-Sarjapur",
    "Bellary Road 1": "junction:Hebbal-flyover",
}


def _build_routes(
    junction_id: str,
    corridor: str,
    description: str,
    summary: str,
    *,
    k: int = 3,
) -> list[DiversionRoute]:
    closed = corridor_to_node_id(corridor)
    blocked = {closed} if corridor != "Non-corridor" else set()
    nbrs = neighbors_of(corridor)

    if not nbrs and corridor != "Non-corridor":
        nbrs = [
            corridor_to_node_id(n)
            for n in ("ORR West 1", "Bannerghata Road", "Tumkur Road")
            if n != corridor
        ][:3]

    candidates: list[tuple[float, list[str], bool]] = []

    if corridor == "Non-corridor" or not nbrs:
        # Static fallback path for non-corridor / isolated nodes
        stub_path = [corridor_to_node_id("ORR East 1"), corridor_to_node_id("Old Airport Road")]
        validation = detect_gridlock(stub_path, closed_node_id=closed if blocked else None)
        return [
            DiversionRoute(
                rank=1,
                junction_id=junction_id,
                description=description,
                route_summary=summary,
                path=stub_path,
                eta_delta_min=5.0,
                capacity_class=capacity_class(stub_path, validation.gridlock_cycle_detected),
                gridlock_cycle_detected=validation.gridlock_cycle_detected,
            )
        ]

    for start in nbrs:
        for goal in nbrs:
            if start == goal:
                continue
            for path, cost in k_shortest_paths(start, goal, k, blocked_nodes=blocked):
                validation = detect_gridlock(path, closed_node_id=closed)
                candidates.append((cost, path, validation.gridlock_cycle_detected))

    if not candidates:
        fallback_path = [nbrs[0], nbrs[-1]] if len(nbrs) >= 2 else nbrs
        validation = detect_gridlock(fallback_path, closed_node_id=closed)
        candidates.append((12.0, fallback_path, validation.gridlock_cycle_detected))

    candidates.sort(key=lambda x: (x[2], x[0]))
    seen: set[tuple[str, ...]] = set()
    routes: list[DiversionRoute] = []

    for cost, path, gridlock in candidates:
        sig = tuple(path)
        if sig in seen:
            continue
        seen.add(sig)
        routes.append(
            DiversionRoute(
                rank=len(routes) + 1,
                junction_id=junction_id,
                description=description,
                route_summary=summary,
                path=path,
                eta_delta_min=round(cost, 2),
                capacity_class=capacity_class(path, gridlock),
                gridlock_cycle_detected=gridlock,
            )
        )
        if len(routes) >= k:
            break

    return routes


def _build_atlas() -> dict[str, AtlasEntry]:
    atlas: dict[str, AtlasEntry] = {}
    for junction_id, meta in JUNCTION_REGISTRY.items():
        t0 = time.perf_counter()
        corridor = meta["corridor"]
        routes = _build_routes(
            junction_id,
            corridor,
            meta["description"],
            meta["summary"],
        )
        closed = corridor_to_node_id(corridor) if corridor != "Non-corridor" else None
        atlas[junction_id] = AtlasEntry(
            junction_id=junction_id,
            source_corridor=corridor,
            closed_node_id=closed,
            routes=routes,
            cached=True,
            latency_ms=round((time.perf_counter() - t0) * 1000, 2),
        )
    return atlas


_ATLAS: dict[str, AtlasEntry] = _build_atlas()


def get_atlas(junction_id: str) -> AtlasEntry | None:
    return _ATLAS.get(junction_id)


def list_atlas_junction_ids() -> list[str]:
    return sorted(_ATLAS.keys())


def primary_junction_for_corridor(corridor: str | None) -> str:
    key = corridor or "Non-corridor"
    return CORRIDOR_PRIMARY_JUNCTION.get(key, "junction:generic-1")


def routes_for_corridor(corridor: str | None, *, k: int = 3) -> list[DiversionRoute]:
    """Top-k routes for a corridor — one best route per junction atlas entry."""
    key = corridor or "Non-corridor"
    collected: list[DiversionRoute] = []

    junction_ids = [
        jid for jid, meta in JUNCTION_REGISTRY.items() if meta["corridor"] == key
    ]
    if not junction_ids:
        junction_ids = [primary_junction_for_corridor(key)]

    for jid in junction_ids:
        entry = _ATLAS.get(jid)
        if not entry or not entry.routes:
            continue
        best = min(entry.routes, key=lambda r: (r.gridlock_cycle_detected, r.eta_delta_min))
        collected.append(best.model_copy(update={"rank": len(collected) + 1}))

    return collected[:k]
