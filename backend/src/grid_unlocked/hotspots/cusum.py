"""CUSUM anomaly detection on corridor event rates."""

from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from grid_unlocked.config import settings
from grid_unlocked.hotspots.schemas import AnomalyAlert


@dataclass
class RateSample:
    corridor: str
    timestamp: datetime


class CusumTracker:
    def __init__(self) -> None:
        self._samples: deque[RateSample] = deque(maxlen=10_000)
        self._baselines: dict[str, float] = {}
        self._stddevs: dict[str, float] = {}
        self._alerts: deque[AnomalyAlert] = deque(maxlen=500)

    def set_baselines(self, baselines: dict[str, float]) -> None:
        for corridor, rate in baselines.items():
            self._baselines[corridor] = rate
            self._stddevs[corridor] = max(rate * 0.5, 0.05)

    def record(self, corridor: str, timestamp: datetime | None = None) -> None:
        ts = timestamp or datetime.now(UTC)
        self._samples.append(RateSample(corridor=corridor, timestamp=ts))
        self._evaluate(corridor, ts)

    def _evaluate(self, corridor: str, now: datetime) -> None:
        baseline = self._baselines.get(corridor)
        if baseline is None:
            return

        window = now - timedelta(minutes=30)
        recent = [s for s in self._samples if s.corridor == corridor and s.timestamp >= window]
        observed_rate = len(recent) * 2.0

        sigma = self._stddevs.get(corridor, max(baseline * 0.5, 0.05))
        z = (observed_rate - baseline) / sigma if sigma > 0 else 0.0

        if z >= settings.hotspot_cusum_sigma:
            alert = AnomalyAlert(
                alert_id=f"cusum-{uuid.uuid4().hex[:8]}",
                corridor=corridor,
                zone=None,
                observed_rate_per_hour=round(observed_rate, 2),
                baseline_rate_per_hour=round(baseline, 2),
                sigma=round(z, 2),
                detected_at=now.replace(tzinfo=UTC).isoformat(),
            )
            self._alerts.appendleft(alert)

    def alerts_last_hours(self, hours: int = 24) -> list[AnomalyAlert]:
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        results: list[AnomalyAlert] = []
        for a in self._alerts:
            ts = datetime.fromisoformat(a.detected_at.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            if ts >= cutoff:
                results.append(a)
        return results


cusum_tracker = CusumTracker()
