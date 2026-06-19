"""Build numeric feature rows for M03 models from M02 FeatureVector + event context."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from grid_unlocked.features.schemas import FeatureVector

FEATURE_COLUMNS = [
    "hour_sin",
    "hour_cos",
    "dow_sin",
    "dow_cos",
    "is_peak_hour",
    "is_weekend",
    "betweenness_norm",
    "degree_norm",
    "is_named_corridor",
    "corridor_cause_closure_rate",
    "duration_prior_h",
    "cause_median_resolution_global_h",
    "veh_complexity_score",
    "simultaneous_events_2km",
    "reporting_bias_weight",
    "is_planned",
    "cause_enc",
    "corridor_enc",
]


def encode_cause(cause: str, encoders: dict[str, Any]) -> int:
    mapping = encoders.get("cause", {})
    return int(mapping.get(cause, mapping.get("__unknown__", 0)))


def encode_corridor(corridor: str | None, encoders: dict[str, Any]) -> int:
    mapping = encoders.get("corridor", {})
    key = corridor or "Non-corridor"
    return int(mapping.get(key, mapping.get("__unknown__", 0)))


def vector_to_row(
    features: FeatureVector,
    *,
    is_planned: bool,
    event_cause: str,
    corridor: str | None,
    encoders: dict[str, Any],
) -> pd.DataFrame:
    row = {
        "hour_sin": features.hour_sin,
        "hour_cos": features.hour_cos,
        "dow_sin": features.dow_sin,
        "dow_cos": features.dow_cos,
        "is_peak_hour": int(features.is_peak_hour),
        "is_weekend": int(features.is_weekend),
        "betweenness_norm": features.betweenness_norm,
        "degree_norm": features.degree_norm,
        "is_named_corridor": int(features.is_named_corridor),
        "corridor_cause_closure_rate": features.corridor_cause_closure_rate,
        "duration_prior_h": features.duration_prior_h,
        "cause_median_resolution_global_h": features.cause_median_resolution_global_h,
        "veh_complexity_score": features.veh_complexity_score,
        "simultaneous_events_2km": features.simultaneous_events_2km,
        "reporting_bias_weight": features.reporting_bias_weight,
        "is_planned": int(is_planned),
        "cause_enc": encode_cause(event_cause, encoders),
        "corridor_enc": encode_corridor(corridor, encoders),
    }
    return pd.DataFrame([row], columns=FEATURE_COLUMNS)


def row_to_numpy(df: pd.DataFrame) -> np.ndarray:
    return df[FEATURE_COLUMNS].astype(float).values
