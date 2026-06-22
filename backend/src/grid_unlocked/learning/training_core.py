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

    Priors are computed as **time-ordered expanding (past-only) statistics**:
    each row only sees outcomes from rows with an earlier `start` timestamp,
    falling back to the global default constants for the first occurrence of
    any (corridor, cause) pair or cause. This avoids a training-time leak
    where a row's prior is built from outcomes — including its own and future
    rows' — that would not actually be known yet at that row's incident-start
    time in production (whole-population aggregation leaks the future into
    the past and inflates offline eval metrics vs true online performance).
    """
    ordered = sorted(range(len(rows)), key=lambda i: rows[i]["start"])

    hour_counts: dict[int, int] = defaultdict(int)
    for r in rows:
        hour_counts[r["start"].astimezone(IST).hour] += 1
    median_hour = statistics.median(hour_counts.values()) if hour_counts else 1
    bias_weights = {
        h: min(3.0, max(0.5, median_hour / max(hour_counts.get(h, 0), 1))) for h in range(24)
    }

    # running (expanding) sums, keyed by (corridor, cause) and by cause alone
    cc_closure_sum: dict[tuple[str, str], int] = defaultdict(int)
    cc_closure_n: dict[tuple[str, str], int] = defaultdict(int)
    cc_icts: dict[tuple[str, str], list[float]] = defaultdict(list)
    cause_icts: dict[str, list[float]] = defaultdict(list)

    cc_rate_prior: dict[int, float] = {}
    cc_ict_prior: dict[int, float] = {}
    cause_ict_prior: dict[int, float] = {}

    for idx in ordered:
        r = rows[idx]
        cc_key = (r["corridor"], r["cause"])

        n = cc_closure_n[cc_key]
        cc_rate_prior[idx] = (
            cc_closure_sum[cc_key] / n if n > 0 else DEFAULT_PRIOR_CLOSURE_RATE
        )
        cc_icts_so_far = cc_icts[cc_key]
        cc_ict_prior[idx] = (
            statistics.median(cc_icts_so_far) if cc_icts_so_far else DEFAULT_PRIOR_ICT_H
        )
        cause_icts_so_far = cause_icts[r["cause"]]
        cause_ict_prior[idx] = (
            statistics.median(cause_icts_so_far) if cause_icts_so_far else DEFAULT_PRIOR_ICT_H
        )

        # only now fold this row's own outcome into the running stats, so the
        # NEXT row in time order (not this one) is the first to see it
        cc_closure_sum[cc_key] += r["closure"]
        cc_closure_n[cc_key] += 1
        if not pd.isna(r["duration_h"]):
            cc_icts[cc_key].append(r["duration_h"])
            cause_icts[r["cause"]].append(r["duration_h"])

    built: list[dict] = []
    for idx, r in enumerate(rows):
        temporal = _temporal(r["start"])
        betweenness, degree_norm, _ = corridor_centrality(r["corridor"])
        built.append(
            {
                **temporal,
                "betweenness_norm": betweenness,
                "degree_norm": degree_norm,
                "is_named_corridor": int(r["corridor"] in CORRIDOR_CENTRALITY),
                "corridor_cause_closure_rate": cc_rate_prior[idx],
                "duration_prior_h": cc_ict_prior[idx],
                "cause_median_resolution_global_h": cause_ict_prior[idx],
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
                "censor_time": r.get("censor_time", r["start"]),
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

            # Censoring horizon for rows with no closed_datetime: the last
            # timestamp we actually observed the row at (modified_datetime,
            # falling back to created_date, then start itself). Used by
            # train_cox_model so censored rows carry their true observed
            # window instead of a corridor x cause prior (see that function).
            censor_time = (
                parse_datetime(row.get("modified_datetime"))
                or parse_datetime(row.get("created_date"))
                or start
            )

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
                    "censor_time": censor_time,
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
    """
    Fit Cox PH on true survival semantics: an observed row's duration is its
    real elapsed start->closed time; a censored row's duration is its real
    elapsed start->censor_time (last time we actually observed it, e.g.
    modified_datetime), NOT the corridor x cause prior. Filling censored
    durations with the prior pins them to a population median instead of
    their true (noisier) observed window, which understates duration
    variance and previously inflated the model's offline C-index relative to
    how it performs on genuinely-unknown future incidents.
    """
    cox_df = df[FEATURE_COLUMNS + ["duration_h", "event_observed", "start"]].copy()
    if "censor_time" in df.columns:
        censor_h = (df["censor_time"] - df["start"]).dt.total_seconds() / 3600.0
    else:
        censor_h = pd.Series(0.0, index=df.index)
    cox_df["duration_h"] = cox_df["duration_h"].where(
        cox_df["event_observed"] == 1, censor_h
    )
    cox_df["duration_h"] = cox_df["duration_h"].clip(lower=0.05)
    cox_df = cox_df.drop(columns="start")

    use_cols = [c for c in FEATURE_COLUMNS if cox_df[c].nunique() > 1]
    fit_cols = use_cols + ["duration_h", "event_observed"]

    cph = CoxPHFitter(penalizer=0.1)
    cph.fit(cox_df[fit_cols], duration_col="duration_h", event_col="event_observed")
    cph._grid_cox_features = use_cols  # type: ignore[attr-defined]
    return cph
