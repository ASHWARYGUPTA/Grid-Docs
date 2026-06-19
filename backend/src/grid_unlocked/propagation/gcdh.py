"""Graph-Centrality Decay Heuristic (GCDH) — M04 core algorithm."""

from __future__ import annotations

import math
import time

from grid_unlocked.features.constants import CORRIDOR_CENTRALITY, CORRIDOR_NEIGHBORS, DEFAULT_CENTRALITY
from grid_unlocked.features.graph_stub import corridor_centrality, corridor_to_node_id, parse_node_id
from grid_unlocked.propagation.schemas import GcdhParams, PropagationMap, PropagationNode


def _edge_weight(source_corridor: str | None, target_corridor: str) -> float:
    src_b = CORRIDOR_CENTRALITY.get(source_corridor or "Non-corridor", DEFAULT_CENTRALITY)
    tgt_b = CORRIDOR_CENTRALITY.get(target_corridor, DEFAULT_CENTRALITY)
    return round(0.5 + 0.5 * (src_b + tgt_b) / 2.0, 3)


def _parent_edge(source: str, target: str) -> str:
    return f"{source}->{target}"


def compute_cascade_risk(nodes: list[PropagationNode], seed_rci: float, max_hop: int = 2) -> float:
    nearby = [n.risk for n in nodes if n.hop <= max_hop]
    if not nearby:
        return round(seed_rci, 4)
    return round(max(nearby), 4)


def run_gcdh(
    event_id: str,
    seed_node_id: str,
    seed_rci: float,
    params: GcdhParams,
) -> PropagationMap:
    t0 = time.perf_counter()

    risk: dict[str, float] = {seed_node_id: seed_rci}
    traces: list[PropagationNode] = []
    best_parent: dict[str, str] = {}
    best_delta: dict[str, float] = {}

    seed_corridor = parse_node_id(seed_node_id)
    traces.append(
        PropagationNode(
            node_id=seed_node_id,
            corridor=seed_corridor,
            risk=round(seed_rci, 4),
            hop=0,
            parent_edge=None,
        )
    )

    current: dict[str, float] = {seed_node_id: seed_rci}

    for hop in range(1, params.max_hops + 1):
        decay = math.exp(-params.lambda_ * hop)
        nxt: dict[str, float] = {}

        for u, r_u in current.items():
            u_corridor = parse_node_id(u)
            for neighbor_name in CORRIDOR_NEIGHBORS.get(u_corridor or "Non-corridor", []):
                v = corridor_to_node_id(neighbor_name)
                betw, _, _ = corridor_centrality(neighbor_name)
                edge_w = _edge_weight(u_corridor, neighbor_name)
                amp = 1.0 + params.k * betw
                delta = r_u * edge_w * decay * amp

                if delta < params.epsilon:
                    continue

                risk[v] = risk.get(v, 0.0) + delta
                nxt[v] = risk[v]

                if delta > best_delta.get(v, 0.0):
                    best_delta[v] = delta
                    best_parent[v] = _parent_edge(u, v)

                traces.append(
                    PropagationNode(
                        node_id=v,
                        corridor=neighbor_name,
                        risk=round(risk[v], 4),
                        hop=hop,
                        parent_edge=best_parent.get(v),
                    )
                )

        current = nxt
        if not current:
            break

    deduped: dict[tuple[str, int], PropagationNode] = {}
    for node in traces:
        key = (node.node_id, node.hop)
        existing = deduped.get(key)
        if existing is None or node.risk > existing.risk:
            deduped[key] = node

    sorted_nodes = sorted(deduped.values(), key=lambda n: (n.hop, -n.risk))
    cascade = compute_cascade_risk(sorted_nodes, seed_rci)
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    return PropagationMap(
        event_id=event_id,
        seed_node_id=seed_node_id,
        seed_rci=round(seed_rci, 4),
        nodes=sorted_nodes,
        cascade_risk=cascade,
        gcdh_params=params,
        latency_ms=latency_ms,
    )
