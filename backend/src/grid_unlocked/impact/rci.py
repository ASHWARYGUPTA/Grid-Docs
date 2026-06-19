import math

from grid_unlocked.features.schemas import FeatureVector
from grid_unlocked.impact.schemas import SeverityBand

# Calibrated on holdout — ML_MODELS_PRD defaults
RCI_WEIGHTS = {
    "log_duration_prior": 0.20,
    "betweenness": 0.18,
    "cascade_seed": 0.22,
    "p_closure": 0.25,
    "veh_complexity": 0.10,
    "simultaneous_events": 0.05,
}

SEVERITY_THRESHOLDS = {
    SeverityBand.GREEN: 0.35,
    SeverityBand.YELLOW: 0.55,
    SeverityBand.ORANGE: 0.75,
}


def _norm_log_duration(hours: float) -> float:
    return min(1.0, math.log1p(max(hours, 0.01)) / math.log1p(48.0))


def _norm_simultaneous(count: int) -> float:
    return min(1.0, count / 10.0)


def compute_rci(
    features: FeatureVector,
    p_closure: float,
    cascade_seed: float | None = None,
) -> float:
    cascade = cascade_seed if cascade_seed is not None else p_closure
    rci = (
        RCI_WEIGHTS["log_duration_prior"] * _norm_log_duration(features.duration_prior_h)
        + RCI_WEIGHTS["betweenness"] * features.betweenness_norm
        + RCI_WEIGHTS["cascade_seed"] * min(1.0, cascade)
        + RCI_WEIGHTS["p_closure"] * p_closure
        + RCI_WEIGHTS["veh_complexity"] * min(1.0, features.veh_complexity_score)
        + RCI_WEIGHTS["simultaneous_events"] * _norm_simultaneous(features.simultaneous_events_2km)
    )
    if 14 <= features.hour_ist <= 18:
        rci *= min(features.reporting_bias_weight, 3.0)
    return round(min(1.0, max(0.0, rci)), 4)


def severity_band_from_rci(rci: float) -> SeverityBand:
    if rci < SEVERITY_THRESHOLDS[SeverityBand.GREEN]:
        return SeverityBand.GREEN
    if rci < SEVERITY_THRESHOLDS[SeverityBand.YELLOW]:
        return SeverityBand.YELLOW
    if rci < SEVERITY_THRESHOLDS[SeverityBand.ORANGE]:
        return SeverityBand.ORANGE
    return SeverityBand.RED


def ict_bands_from_median(median_h: float) -> tuple[float, float, float]:
    """Rule fallback: derive P20/P50/P80 from median prior."""
    median_h = max(0.1, median_h)
    return round(median_h * 0.8, 2), round(median_h, 2), round(median_h * 1.5, 2)
