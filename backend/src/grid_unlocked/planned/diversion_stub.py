"""M08 diversion atlas stub — top-3 routes per corridor until M08 ships."""

from grid_unlocked.planned.schemas import DiversionRef

CORRIDOR_DIVERSIONS: dict[str, list[tuple[str, str]]] = {
    "Mysore Road": [
        ("junction:Mysore-NICE", "NICE Road U-turn at junction 4412", "Via NICE connector → rejoin Mysore Road"),
        ("junction:Mysore-Vijayanagar", "Vijayanagar service road", "Local distributor → Bapuji Nagar"),
        ("junction:Mysore-Gnanabharathi", "Gnanabharathi ring", "Outer ring bypass segment"),
    ],
    "ORR East 1": [
        ("junction:ORR-Sarjapur", "Sarjapur Road detour", "ORR exit → Sarjapur → rejoin"),
        ("junction:ORR-OldAirport", "Old Airport Road flyover", "Parallel arterial"),
        ("junction:ORR-Hosur", "Hosur Road connector", "Southbound bypass"),
    ],
    "Bellary Road 1": [
        ("junction:Hebbal-flyover", "Hebbal flyover U-turn", "Northbound loop"),
        ("junction:Manyata", "Manyata embankment road", "Service lane"),
        ("junction:RTNagar", "RT Nagar cross", "Inner ring alternative"),
    ],
}

DEFAULT_DIVERSIONS = [
    ("junction:generic-1", "Nearest U-turn bay", "First legal U-turn within 500 m"),
    ("junction:generic-2", "Parallel service road", "Adjacent distributor if available"),
    ("junction:generic-3", "Corridor end-cap", "Route to next major junction"),
]


def diversion_refs_for_corridor(corridor: str | None, *, limit: int = 3) -> list[DiversionRef]:
    key = corridor or "Non-corridor"
    routes = CORRIDOR_DIVERSIONS.get(key, DEFAULT_DIVERSIONS)
    refs: list[DiversionRef] = []
    for rank, (junction_id, desc, summary) in enumerate(routes[:limit], start=1):
        refs.append(
            DiversionRef(
                junction_id=junction_id,
                description=desc,
                route_summary=summary,
                rank=rank,
            )
        )
    return refs
