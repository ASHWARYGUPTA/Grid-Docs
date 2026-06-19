"""Poisson intensity forecast for predicted hotspots."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
from sklearn.linear_model import PoissonRegressor

from grid_unlocked.features.constants import CORRIDOR_CENTRALITY
from grid_unlocked.features.temporal import cyclical_temporal
from grid_unlocked.hotspots.historical import HistoricalIndex, historical_index
from grid_unlocked.hotspots.schemas import HotspotCluster, HotspotLayer, PredictedZoneForecast


class PoissonForecaster:
    def __init__(self) -> None:
        self._model: PoissonRegressor | None = None
        self._corridors: list[str] = []
        self._fitted = False

    def fit(self, index: HistoricalIndex | None = None) -> None:
        idx = index or historical_index
        idx.load()
        if not idx.corridor_hour_counts:
            self._fitted = True
            return

        x, y, corridors = idx.poisson_training_frame()
        self._corridors = corridors
        self._model = PoissonRegressor(alpha=0.1, max_iter=300)
        self._model.fit(x, y)
        self._fitted = True

    def forecast(
        self,
        horizon_hours: int = 4,
        *,
        index: HistoricalIndex | None = None,
    ) -> list[PredictedZoneForecast]:
        if not self._fitted:
            self.fit(index)

        idx = index or historical_index
        now = datetime.now(UTC)
        temporal = cyclical_temporal(now)

        forecasts: list[PredictedZoneForecast] = []
        enc = {c: i for i, c in enumerate(self._corridors)}

        for corridor in self._corridors:
            baseline = idx.corridor_baselines.get(corridor, 0.1) * horizon_hours
            if self._model is None or not self._corridors:
                expected = baseline
            else:
                row = [
                    temporal["hour_sin"],
                    temporal["hour_cos"],
                    temporal["dow_sin"],
                    temporal["dow_cos"],
                    float(temporal["is_weekend"]),
                ]
                one_hot = [0.0] * len(self._corridors)
                one_hot[enc[corridor]] = 1.0
                x = np.array([row + one_hot])
                expected = float(self._model.predict(x)[0]) * horizon_hours
                expected = max(0.0, expected)

            lift = ((expected - baseline) / baseline * 100) if baseline > 0 else 0.0
            forecasts.append(
                PredictedZoneForecast(
                    corridor=corridor,
                    zone=None,
                    expected_count=round(expected, 2),
                    baseline_count=round(baseline, 2),
                    lift_pct=round(lift, 1),
                )
            )

        forecasts.sort(key=lambda f: f.expected_count, reverse=True)
        return forecasts[:20]

    def as_predicted_clusters(self, horizon_hours: int = 4) -> list[HotspotCluster]:
        clusters: list[HotspotCluster] = []
        for rank, fc in enumerate(self.forecast(horizon_hours)):
            density = max(1, int(round(fc.expected_count)))
            clusters.append(
                HotspotCluster(
                    cluster_id=f"pred-{rank}-{fc.corridor.replace(' ', '_')[:20]}",
                    layer=HotspotLayer.PREDICTED,
                    centroid_lat=12.97,
                    centroid_lon=77.59 + rank * 0.01,
                    density=density,
                    cause_entropy=0.0,
                    h3_cells=[],
                    corridors=[fc.corridor],
                    persistence_score=round(CORRIDOR_CENTRALITY.get(fc.corridor, 0.5), 3),
                    label=f"+{fc.lift_pct:.0f}% vs baseline",
                )
            )
        return clusters


poisson_forecaster = PoissonForecaster()
