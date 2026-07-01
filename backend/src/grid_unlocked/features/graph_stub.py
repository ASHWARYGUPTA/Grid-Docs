from grid_unlocked.features.constants import (
    CORRIDOR_CENTRALITY,
    CORRIDOR_NEIGHBORS,
    DEFAULT_CENTRALITY,
)
from grid_unlocked.features.schemas import GraphCentrality, GraphNeighbors


def corridor_to_node_id(corridor: str | None) -> str:
    key = corridor or "unknown"
    return f"corridor:{key}"


def parse_node_id(node_id: str) -> str | None:
    if node_id.startswith("corridor:"):
        name = node_id.removeprefix("corridor:")
        return None if name == "unknown" else name
    return None


def corridor_centrality(corridor: str | None) -> tuple[float, float, int]:
    """Return (betweenness_norm, degree_norm, degree) for MVP corridor graph."""
    name = corridor or "Non-corridor"
    betweenness = CORRIDOR_CENTRALITY.get(name, DEFAULT_CENTRALITY)
    neighbors = CORRIDOR_NEIGHBORS.get(name, [])
    degree = len(neighbors)
    degree_norm = min(1.0, degree / 6.0)
    return betweenness, degree_norm, degree


def get_centrality(node_id: str) -> GraphCentrality:
    corridor = parse_node_id(node_id)
    betweenness, degree_norm, degree = corridor_centrality(corridor)
    edges = [
        {"target": corridor_to_node_id(n), "weight": 1.0}
        for n in CORRIDOR_NEIGHBORS.get(corridor or "Non-corridor", [])
    ]
    return GraphCentrality(
        node_id=node_id,
        betweenness=betweenness,
        betweenness_norm=betweenness,
        degree=degree,
        degree_norm=degree_norm,
        corridor=corridor,
        edge_weights=edges,
    )


def get_neighbors(node_id: str, hops: int = 3) -> GraphNeighbors:
    visited: set[str] = {node_id}
    frontier = [node_id]
    collected: list[GraphCentrality] = []

    for _ in range(max(1, min(hops, 5))):
        next_frontier: list[str] = []
        for nid in frontier:
            c = parse_node_id(nid)
            for neighbor in CORRIDOR_NEIGHBORS.get(c or "Non-corridor", []):
                nn = corridor_to_node_id(neighbor)
                if nn not in visited:
                    visited.add(nn)
                    next_frontier.append(nn)
                    collected.append(get_centrality(nn))
        frontier = next_frontier

    return GraphNeighbors(node_id=node_id, hops=hops, nodes=collected)
