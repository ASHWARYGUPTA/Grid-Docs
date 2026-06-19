"""Corridor graph utilities — k-shortest paths on M02 static OSM proxy."""

from __future__ import annotations

import heapq
from itertools import count

from grid_unlocked.features.constants import CORRIDOR_CENTRALITY, CORRIDOR_NEIGHBORS
from grid_unlocked.features.graph_stub import corridor_to_node_id, parse_node_id

_counter = count()


def edge_weight(node_a: str, node_b: str) -> float:
    ca = parse_node_id(node_a) or "Non-corridor"
    cb = parse_node_id(node_b) or "Non-corridor"
    avg_c = (CORRIDOR_CENTRALITY.get(ca, 0.25) + CORRIDOR_CENTRALITY.get(cb, 0.25)) / 2
    return 8.0 / max(avg_c, 0.1)


def build_adjacency() -> dict[str, list[str]]:
    adj: dict[str, set[str]] = {}
    for corridor, neighbors in CORRIDOR_NEIGHBORS.items():
        src = corridor_to_node_id(corridor)
        adj.setdefault(src, set())
        for neighbor in neighbors:
            dst = corridor_to_node_id(neighbor)
            adj[src].add(dst)
            adj.setdefault(dst, set()).add(src)
    for corridor in CORRIDOR_CENTRALITY:
        if corridor != "Non-corridor":
            adj.setdefault(corridor_to_node_id(corridor), set())
    return {node: sorted(neighbors) for node, neighbors in adj.items()}


def dijkstra(
    start: str,
    goal: str,
    *,
    blocked_nodes: set[str] | None = None,
    blocked_edges: set[tuple[str, str]] | None = None,
) -> tuple[list[str], float] | None:
    blocked_nodes = blocked_nodes or set()
    blocked_edges = blocked_edges or set()
    if start in blocked_nodes or goal in blocked_nodes:
        return None

    adj = build_adjacency()
    dist: dict[str, float] = {start: 0.0}
    prev: dict[str, str | None] = {start: None}
    heap: list[tuple[float, int, str]] = [(0.0, next(_counter), start)]
    seen: set[str] = set()

    while heap:
        d, _, u = heapq.heappop(heap)
        if u in seen:
            continue
        seen.add(u)
        if u == goal:
            path: list[str] = []
            cur: str | None = u
            while cur is not None:
                path.append(cur)
                cur = prev[cur]
            path.reverse()
            return path, d

        for v in adj.get(u, []):
            if v in blocked_nodes:
                continue
            edge = tuple(sorted((u, v)))
            if edge in blocked_edges:
                continue
            w = edge_weight(u, v)
            nd = d + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, next(_counter), v))
    return None


def k_shortest_paths(
    start: str,
    goal: str,
    k: int,
    *,
    blocked_nodes: set[str] | None = None,
) -> list[tuple[list[str], float]]:
    """Yen's algorithm (simplified) for k shortest simple paths."""
    blocked_nodes = blocked_nodes or set()
    if start == goal:
        return [([start], 0.0)]

    first = dijkstra(start, goal, blocked_nodes=blocked_nodes)
    if not first:
        return []

    paths: list[tuple[list[str], float]] = [first]
    candidates: list[tuple[float, int, list[str], float]] = []

    for path_rank in range(1, k):
        prev_path, _ = paths[-1]
        for i in range(len(prev_path) - 1):
            spur_node = prev_path[i]
            root_path = prev_path[: i + 1]
            blocked_edges: set[tuple[str, str]] = set()
            blocked_extra = set(blocked_nodes)

            for p, _ in paths:
                if len(p) > i and p[: i + 1] == root_path:
                    blocked_edges.add(tuple(sorted((p[i], p[i + 1]))))

            for node in root_path[:-1]:
                blocked_extra.add(node)

            spur_result = dijkstra(
                spur_node,
                goal,
                blocked_nodes=blocked_extra,
                blocked_edges=blocked_edges,
            )
            if not spur_result:
                continue
            spur_path, spur_cost = spur_result
            total_path = root_path[:-1] + spur_path
            root_cost = sum(
                edge_weight(total_path[j], total_path[j + 1])
                for j in range(len(root_path) - 1)
            )
            total_cost = root_cost + spur_cost
            heapq.heappush(candidates, (total_cost, next(_counter), total_path, total_cost))

        if not candidates:
            break
        _, _, path, cost = heapq.heappop(candidates)
        paths.append((path, cost))

    return paths[:k]


def neighbors_of(corridor: str) -> list[str]:
    return [corridor_to_node_id(n) for n in CORRIDOR_NEIGHBORS.get(corridor, [])]
