"""Historical ASTraM index for cell history, persistence, Poisson baselines."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np

from grid_unlocked.config import settings
from grid_unlocked.features.temporal import cyclical_temporal
from grid_unlocked.hotspots.dbscan import EventPoint, cluster_h3_cells_haversine
from grid_unlocked.hotspots.geo import h3_centroid, h3_res7
from grid_unlocked.hotspots.schemas import HotspotCluster
from grid_unlocked.ingestion.validator import normalize_cause, parse_datetime

IST = ZoneInfo("Asia/Kolkata")


@dataclass
class CellRecord:
    total_count: int = 0
    count_30d: int = 0
    causes: Counter = field(default_factory=Counter)
    corridors: Counter = field(default_factory=Counter)
    junctions: Counter = field(default_factory=Counter)
    hourly: Counter = field(default_factory=Counter)


@dataclass
class HistoricalIndex:
    cells: dict[str, CellRecord] = field(default_factory=dict)
    corridor_hour_counts: dict[tuple[str, int], int] = field(default_factory=dict)
    corridor_baselines: dict[str, float] = field(default_factory=dict)
    corridor_centroids: dict[str, tuple[float, float]] = field(default_factory=dict)
    persistence_scores: dict[str, float] = field(default_factory=dict)
    all_points: list[EventPoint] = field(default_factory=list)
    loaded: bool = False
    # Number of calendar days the loaded CSV actually spans — used to convert
    # raw cumulative (corridor, hour) counts into a per-hour rate. The corpus
    # is not always exactly 30 days (the real ASTraM CSV spans ~150 days), so
    # this must be measured, not assumed.
    history_days: float = 30.0

    def load(self, csv_path=None) -> None:
        if self.loaded:
            return

        path = csv_path or settings.astram_csv_path
        if not path.exists():
            self.loaded = True
            return

        now = datetime.now(UTC)
        cutoff_30d = now - timedelta(days=30)
        earliest: datetime | None = None
        latest: datetime | None = None

        try:
            with path.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    if row.get("event_cause") == "test_demo":
                        continue
                    try:
                        cause = normalize_cause(row.get("event_cause"))
                    except Exception:
                        continue

                    lat = float(row["latitude"])
                    lon = float(row["longitude"])
                    cell = h3_res7(lat, lon)
                    corridor = row.get("corridor") or "Non-corridor"
                    if corridor in ("NULL", ""):
                        corridor = "Non-corridor"

                    start = parse_datetime(row.get("start_datetime"))
                    hour_ist = start.astimezone(IST).hour if start else 12
                    if start:
                        earliest = start if earliest is None else min(earliest, start)
                        latest = start if latest is None else max(latest, start)

                    rec = self.cells.setdefault(cell, CellRecord())
                    rec.total_count += 1
                    rec.causes[cause] += 1
                    rec.corridors[corridor] += 1
                    rec.hourly[hour_ist] += 1
                    junction = row.get("junction")
                    if junction and junction not in ("NULL", ""):
                        rec.junctions[junction] += 1

                    if start and start >= cutoff_30d:
                        rec.count_30d += 1

                    self.corridor_hour_counts[(corridor, hour_ist)] = (
                        self.corridor_hour_counts.get((corridor, hour_ist), 0) + 1
                    )
                    self.all_points.append(
                        EventPoint(
                            row.get("id", f"hist-{len(self.all_points)}"),
                            lat,
                            lon,
                            cause,
                            corridor,
                        )
                    )

            max_30d = max((c.count_30d for c in self.cells.values()), default=0)
            if max_30d > 0:
                for cell_id, rec in self.cells.items():
                    self.persistence_scores[cell_id] = round(rec.count_30d / max_30d, 3)
            else:
                max_total = max((c.total_count for c in self.cells.values()), default=1)
                for cell_id, rec in self.cells.items():
                    self.persistence_scores[cell_id] = round(rec.total_count / max_total, 3)

            if earliest is not None and latest is not None:
                self.history_days = max((latest - earliest).total_seconds() / 86400, 1.0)

            corridor_totals: dict[str, int] = defaultdict(int)
            for (corridor, _), count in self.corridor_hour_counts.items():
                corridor_totals[corridor] += count
            for corridor, total in corridor_totals.items():
                self.corridor_baselines[corridor] = total / (24 * self.history_days)

            corridor_lat_sum: dict[str, float] = defaultdict(float)
            corridor_lon_sum: dict[str, float] = defaultdict(float)
            corridor_point_count: dict[str, int] = defaultdict(int)
            for point in self.all_points:
                corridor = point.corridor or "Non-corridor"
                corridor_lat_sum[corridor] += point.lat
                corridor_lon_sum[corridor] += point.lon
                corridor_point_count[corridor] += 1
            for corridor, count in corridor_point_count.items():
                self.corridor_centroids[corridor] = (
                    corridor_lat_sum[corridor] / count,
                    corridor_lon_sum[corridor] / count,
                )
        finally:
            self.loaded = True

    def all_cell_densities(self, min_count: int = 1) -> list[tuple[str, float, float, int]]:
        """Every H3 cell with >= min_count historical events, for a
        city-wide density heatmap — unlike historical_clusters() (top-N,
        DBSCAN-merged, for discrete hotspot cards), this is the raw,
        unclustered per-cell density a smooth heatmap layer needs."""
        result: list[tuple[str, float, float, int]] = []
        for cell_id, rec in self.cells.items():
            if rec.total_count < min_count:
                continue
            lat, lon = h3_centroid(cell_id)
            result.append((cell_id, lat, lon, rec.total_count))
        return result

    def historical_clusters(self, top_n: int = 10) -> list[HotspotCluster]:
        cell_points: list[tuple[str, float, float, int, list[str], list[str]]] = []
        for cell_id, rec in self.cells.items():
            if rec.total_count < 3:
                continue
            lat, lon = h3_centroid(cell_id)
            causes = [c for c, _ in rec.causes.most_common(5)]
            corridors = [c for c, _ in rec.corridors.most_common(3)]
            cell_points.append((cell_id, lat, lon, rec.total_count, causes, corridors))

        clusters = cluster_h3_cells_haversine(
            cell_points,
            persistence=self.persistence_scores,
        )
        return clusters[:top_n]

    def cell_summary(self, h3_cell: str) -> dict | None:
        rec = self.cells.get(h3_cell)
        lat, lon = h3_centroid(h3_cell)
        if not rec:
            return {
                "h3_res7": h3_cell,
                "total_events": 0,
                "events_30d": 0,
                "persistence_score": 0.0,
                "top_causes": [],
                "top_corridors": [],
                "hourly_counts": [0] * 24,
                "centroid_lat": lat,
                "centroid_lon": lon,
            }

        return {
            "h3_res7": h3_cell,
            "total_events": rec.total_count,
            "events_30d": rec.count_30d,
            "persistence_score": self.persistence_scores.get(h3_cell, 0.0),
            "top_causes": [{"cause": c, "count": n} for c, n in rec.causes.most_common(5)],
            "top_corridors": [{"corridor": c, "count": n} for c, n in rec.corridors.most_common(3)],
            "hourly_counts": [rec.hourly.get(h, 0) for h in range(24)],
            "centroid_lat": lat,
            "centroid_lon": lon,
        }

    def poisson_training_frame(self) -> tuple[np.ndarray, np.ndarray, list[str]]:
        """Target `y` is events-per-hour-of-day-per-day (a rate, not a raw
        cumulative count) — each (corridor, hour) bucket occurs once per
        calendar day across the loaded history, so dividing by history_days
        keeps this in the same units as corridor_baselines."""
        rows_x: list[list[float]] = []
        rows_y: list[float] = []
        corridors: list[str] = []

        corridor_set = sorted({c for c, _ in self.corridor_hour_counts})
        enc = {c: i for i, c in enumerate(corridor_set)}

        for (corridor, hour), count in self.corridor_hour_counts.items():
            temporal = cyclical_temporal(
                datetime(2024, 1, 1, hour, 0, tzinfo=IST).astimezone(UTC)
            )
            row = [
                temporal["hour_sin"],
                temporal["hour_cos"],
                temporal["dow_sin"],
                temporal["dow_cos"],
                float(temporal["is_weekend"]),
            ]
            one_hot = [0.0] * len(corridor_set)
            one_hot[enc[corridor]] = 1.0
            rows_x.append(row + one_hot)
            rows_y.append(count / self.history_days)
            corridors.append(corridor)

        return np.array(rows_x), np.array(rows_y), corridor_set


historical_index = HistoricalIndex()
