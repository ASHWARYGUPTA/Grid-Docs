"""M13 — shared training core.

Extracted from scripts/train_impact_models.py so the same feature
engineering + model training logic is importable both by the standalone CLI
script (offline, full-corpus retrain) and by M13's live retrain pipeline
(buffer of recent-closed DB rows + CSV anchor sample). Nothing about the
existing script's behavior changes — it now imports these functions instead
of defining them inline.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import lightgbm as lgb
import numpy as np
import pandas as pd
from lifelines import CoxPHFitter
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import train_test_split

from grid_unlocked.features.constants import (
    CORRIDOR_CENTRALITY,
    DEFAULT_PRIOR_CLOSURE_RATE,
    DEFAULT_PRIOR_ICT_H,
    DEFAULT_VEH_COMPLEXITY,
    PEAK_HOURS,
    VEH_COMPLEXITY_BASE,
)
from grid_unlocked.features.graph_stub import corridor_centrality
from grid_unlocked.impact.feature_matrix import FEATURE_COLUMNS
from grid_unlocked.ingestion.validator import normalize_cause, parse_bool, parse_datetime

IST = ZoneInfo("Asia/Kolkata")


def _ict_hours(start: datetime | None, closed: datetime | None) -> float | None:
    if start is None or closed is None or closed <= start:
        return None
    return (closed - start).total_seconds() / 3600.0


def _temporal(start: datetime) -> dict:
    ist = start.astimezone(IST)
    hour = ist.hour
    dow = ist.weekday()
    return {
        "hour_ist": hour,
        "dow": dow,
        "hour_sin": math.sin(2 * math.pi * hour / 24),
        "hour_cos": math.cos(2 * math.pi * hour / 24),
        "dow_sin": math.sin(2 * math.pi * dow / 7),
        "dow_cos": math.cos(2 * math.pi * dow / 7),
        "is_peak_hour": int(hour in PEAK_HOURS),
        "is_weekend": int(dow >= 5),
    }


def _veh_score(veh_type: str | None) -> float:
    if not veh_type:
        return DEFAULT_VEH_COMPLEXITY
    return VEH_COMPLEXITY_BASE.get(veh_type.lower(), DEFAULT_VEH_COMPLEXITY)


def build_feature_rows(rows: list[dict]) -> pd.DataFrame:
    """
    Shared per-row feature engineering. `rows` is a list of dicts each with
    keys: cause, corridor, is_planned, closure (0/1), duration_h (float|nan),
    event_observed (0/1), veh_type, start (datetime).

    Corridor x cause priors (closure rate, median ICT) and the hour-of-day
    reporting bias weights are recomputed from whatever population `rows`
    represents — the CSV's full corpus when called from the CLI script, or
    the live DB's recent-closed pool + CSV anchor sample when called from
    M13's buffer construction. This is what makes a buffer-based retrain
    meaningfully different from re-running the static CLI script.
    """
    cc_agg: dict[tuple[str, str], list[dict]] = defaultdict(list)
    cause_agg: dict[str, list[dict]] = defaultdict(list)
    hour_counts: dict[int, int] = defaultdict(int)

    for r in rows:
        record = {"closure": r["closure"], "ict": r["duration_h"] if not pd.isna(r["duration_h"]) else None}
        cc_agg[(r["corridor"], r["cause"])].append(record)
        cause_agg[r["cause"]].append(record)
        hour_counts[r["start"].astimezone(IST).hour] += 1

    median_hour = statistics.median(hour_counts.values()) if hour_counts else 1
    bias_weights = {
        h: min(3.0, max(0.5, median_hour / max(hour_counts.get(h, 0), 1))) for h in range(24)
    }

    cc_stats: dict[tuple[str, str], tuple[float, float]] = {}
    for key, records in cc_agg.items():
        closures = [r["closure"] for r in records]
        icts = [r["ict"] for r in records if r["ict"] is not None]
        cc_stats[key] = (
            sum(closures) / len(closures) if closures else DEFAULT_PRIOR_CLOSURE_RATE,
            statistics.median(icts) if icts else DEFAULT_PRIOR_ICT_H,
        )

    cause_medians: dict[str, float] = {}
    for c, recs in cause_agg.items():
        icts = [r["ict"] for r in recs if r["ict"] is not None]
        cause_medians[c] = statistics.median(icts) if icts else DEFAULT_PRIOR_ICT_H

    built: list[dict] = []
    for r in rows:
        temporal = _temporal(r["start"])
        betweenness, degree_norm, _ = corridor_centrality(r["corridor"])
        cc_rate, cc_ict = cc_stats.get(
            (r["corridor"], r["cause"]), (DEFAULT_PRIOR_CLOSURE_RATE, DEFAULT_PRIOR_ICT_H)
        )
        built.append(
            {
                **temporal,
                "betweenness_norm": betweenness,
                "degree_norm": degree_norm,
                "is_named_corridor": int(r["corridor"] in CORRIDOR_CENTRALITY),
                "corridor_cause_closure_rate": cc_rate,
                "duration_prior_h": cc_ict,
                "cause_median_resolution_global_h": cause_medians.get(r["cause"], DEFAULT_PRIOR_ICT_H),
                "veh_complexity_score": _veh_score(r["veh_type"]),
                "simultaneous_events_2km": 0,
                "reporting_bias_weight": bias_weights[temporal["hour_ist"]],
                "is_planned": int(r["is_planned"]),
                "cause": r["cause"],
                "corridor": r["corridor"],
                "closure": r["closure"],
                "duration_h": r["duration_h"],
                "event_observed": r["event_observed"],
                "start": r["start"],
                "event_id": r.get("event_id"),
                "pool": r.get("pool", "anchor"),
            }
        )

    return pd.DataFrame(built)


def load_csv_frame(csv_path: Path) -> pd.DataFrame:
    """Parse the ASTraM CSV corpus into the shared feature-engineered frame.

    Identical behavior to the original train_impact_models.load_training_frame.
    """
    import csv

    rows: list[dict] = []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("event_cause") == "test_demo":
                continue
            try:
                cause = normalize_cause(row.get("event_cause"))
            except Exception:
                continue

            start = parse_datetime(row.get("start_datetime"))
            if not start:
                continue

            closed = parse_datetime(row.get("closed_datetime"))
            corridor = row.get("corridor")
            if corridor in ("NULL", "", None):
                corridor = "Non-corridor"

            closure = parse_bool(row.get("requires_road_closure"), default=False)
            ict = _ict_hours(start, closed)
            is_planned = row.get("event_type") == "planned"

            rows.append(
                {
                    "cause": cause,
                    "corridor": corridor,
                    "is_planned": is_planned,
                    "closure": int(closure),
                    "duration_h": ict if ict is not None else np.nan,
                    "event_observed": int(ict is not None),
                    "veh_type": row.get("veh_type"),
                    "start": start,
                    "event_id": row.get("id"),
                    "pool": "anchor",
                }
            )

    return build_feature_rows(rows)


def build_encoders(df: pd.DataFrame) -> dict:
    causes = sorted(df["cause"].unique())
    corridors = sorted(df["corridor"].unique())
    cause_map = {"__unknown__": 0, **{c: i + 1 for i, c in enumerate(causes)}}
    corridor_map = {"__unknown__": 0, **{c: i + 1 for i, c in enumerate(corridors)}}
    return {"cause": cause_map, "corridor": corridor_map}


def apply_encoders(df: pd.DataFrame, encoders: dict) -> pd.DataFrame:
    out = df.copy()
    out["cause_enc"] = out["cause"].map(encoders["cause"]).fillna(0).astype(int)
    out["corridor_enc"] = out["corridor"].map(encoders["corridor"]).fillna(0).astype(int)
    return out


def train_closure_model(
    df: pd.DataFrame, *, temporal_split: bool = False
) -> tuple[object, object, dict[str, float], pd.DataFrame, pd.DataFrame]:
    """
    Train the LightGBM closure classifier + isotonic calibrator.

    temporal_split=False (CLI script default): today's stratified random
    80/20 split, unchanged behavior.
    temporal_split=True (M13 retrain): sort by `start` and take the trailing
    20% as the validation slice — spec: "temporal CV (no shuffle)".

    Returns (model, calibrator, feature_importances, val_df, train_df) so
    callers can evaluate on the exact validation rows used during fit.
    """
    if temporal_split:
        ordered = df.sort_values("start")
        split_idx = int(len(ordered) * 0.8)
        train_df, val_df = ordered.iloc[:split_idx], ordered.iloc[split_idx:]
        x_train, y_train = train_df[FEATURE_COLUMNS], train_df["closure"]
        x_val, y_val = val_df[FEATURE_COLUMNS], val_df["closure"]
    else:
        x = df[FEATURE_COLUMNS]
        y = df["closure"]
        x_train, x_val, y_train, y_val = train_test_split(
            x, y, test_size=0.2, random_state=42, stratify=y
        )
        train_df = df.loc[x_train.index]
        val_df = df.loc[x_val.index]

    base = lgb.LGBMClassifier(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=6,
        num_leaves=31,
        scale_pos_weight=11,
        random_state=42,
        verbose=-1,
    )
    base.fit(x_train, y_train)

    val_probs = base.predict_proba(x_val)[:, 1]
    calibrator = IsotonicRegression(out_of_bounds="clip")
    calibrator.fit(val_probs, y_val)

    importances = dict(zip(FEATURE_COLUMNS, base.feature_importances_.tolist(), strict=False))
    return base, calibrator, importances, val_df, train_df


def train_cox_model(df: pd.DataFrame) -> CoxPHFitter:
    cox_df = df[FEATURE_COLUMNS + ["duration_h", "event_observed"]].copy()
    cox_df["duration_h"] = cox_df["duration_h"].fillna(cox_df["duration_prior_h"])
    cox_df["duration_h"] = cox_df["duration_h"].clip(lower=0.05)

    use_cols = [c for c in FEATURE_COLUMNS if cox_df[c].nunique() > 1]
    fit_cols = use_cols + ["duration_h", "event_observed"]

    cph = CoxPHFitter(penalizer=0.1)
    cph.fit(cox_df[fit_cols], duration_col="duration_h", event_col="event_observed")
    cph._grid_cox_features = use_cols  # type: ignore[attr-defined]
    return cph
