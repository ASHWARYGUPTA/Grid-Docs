"""Haversine DBSCAN clustering for M05 observed hotspots."""

from __future__ import annotations

import math
import uuid
from collections import Counter, defaultdict

import numpy as np
from sklearn.cluster import DBSCAN

from grid_unlocked.hotspots.geo import h3_centroid, h3_res7
from grid_unlocked.hotspots.schemas import HotspotCluster, HotspotLayer


def cause_entropy(causes: list[str]) -> float:
    if not causes:
        return 0.0
    counts = Counter(causes)
    total = sum(counts.values())
    entropy = 0.0
    for count in counts.values():
        p = count / total
        if p > 0:
            entropy -= p * math.log2(p)
    return round(entropy, 3)


class EventPoint:
    __slots__ = ("event_id", "lat", "lon", "cause", "corridor", "h3")

    def __init__(
        self,
        event_id: str,
        lat: float,
        lon: float,
        cause: str,
        corridor: str | None,
    ) -> None:
        self.event_id = event_id
        self.lat = lat
        self.lon = lon
        self.cause = cause
        self.corridor = corridor or "Non-corridor"
        self.h3 = h3_res7(lat, lon)


def cluster_events_haversine(
    points: list[EventPoint],
    *,
    eps_rad: float = 0.005,
    min_samples: int = 5,
    persistence: dict[str, float] | None = None,
) -> list[HotspotCluster]:
    if not points:
        return []

    persistence = persistence or {}

    if len(points) < min_samples:
        return _singleton_clusters(points, persistence)

    coords = np.radians(np.array([[p.lat, p.lon] for p in points]))
    labels = DBSCAN(eps=eps_rad, min_samples=min_samples, metric="haversine").fit_predict(coords)

    grouped: dict[int, list[EventPoint]] = defaultdict(list)
    for point, label in zip(points, labels, strict=True):
        grouped[int(label)].append(point)

    clusters: list[HotspotCluster] = []
    for label, members in grouped.items():
        if label == -1:
            clusters.extend(_singleton_clusters(members, persistence))
            continue

        lat = sum(m.lat for m in members) / len(members)
        lon = sum(m.lon for m in members) / len(members)
        h3_cells = sorted({m.h3 for m in members})
        corridors = sorted({m.corridor for m in members})
        causes = [m.cause for m in members]
        persist = max(persistence.get(h, 0.0) for h in h3_cells) if h3_cells else 0.0

        clusters.append(
            HotspotCluster(
                cluster_id=f"obs-{uuid.uuid4().hex[:8]}",
                layer=HotspotLayer.OBSERVED,
                centroid_lat=round(lat, 6),
                centroid_lon=round(lon, 6),
                density=len(members),
                cause_entropy=cause_entropy(causes),
                h3_cells=h3_cells,
                corridors=corridors,
                persistence_score=round(persist, 3),
            )
        )

    clusters.sort(key=lambda c: c.density, reverse=True)
    return clusters[:10]


def cluster_h3_cells_haversine(
    cell_points: list[tuple[str, float, float, int, list[str], list[str]]],
    *,
    eps_rad: float = 0.005,
    min_samples: int = 5,
    persistence: dict[str, float] | None = None,
) -> list[HotspotCluster]:
    """Cluster pre-aggregated H3 cells: (h3, lat, lon, count, causes, corridors)."""
    events: list[EventPoint] = []
    for h3_cell, lat, lon, count, causes, corridors in cell_points:
        corridor = corridors[0] if corridors else "Non-corridor"
        cause = causes[0] if causes else "unknown"
        for i in range(min(count, 15)):
            events.append(EventPoint(f"{h3_cell}-{i}", lat, lon, cause, corridor))

    return cluster_events_haversine(
        events,
        eps_rad=eps_rad,
        min_samples=min_samples,
        persistence=persistence,
    )


def _singleton_clusters(
    points: list[EventPoint],
    persistence: dict[str, float],
) -> list[HotspotCluster]:
    by_h3: dict[str, list[EventPoint]] = defaultdict(list)
    for p in points:
        by_h3[p.h3].append(p)

    clusters: list[HotspotCluster] = []
    for h3_cell, members in by_h3.items():
        lat, lon = h3_centroid(h3_cell)
        causes = [m.cause for m in members]
        corridors = sorted({m.corridor for m in members})
        clusters.append(
            HotspotCluster(
                cluster_id=f"obs-{h3_cell[-8:]}",
                layer=HotspotLayer.OBSERVED,
                centroid_lat=round(lat, 6),
                centroid_lon=round(lon, 6),
                density=len(members),
                cause_entropy=cause_entropy(causes),
                h3_cells=[h3_cell],
                corridors=corridors,
                persistence_score=round(persistence.get(h3_cell, 0.0), 3),
                label="singleton",
            )
        )
    clusters.sort(key=lambda c: c.density, reverse=True)
    return clusters
