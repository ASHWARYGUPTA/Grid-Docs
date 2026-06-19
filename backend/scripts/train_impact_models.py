#!/usr/bin/env python3
"""Train M03 closure classifier + Cox PH ICT model from ASTraM CSV."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from lifelines import CoxPHFitter
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import train_test_split

from grid_unlocked.config import settings
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


def load_training_frame(csv_path: Path) -> pd.DataFrame:
    import csv

    cc_agg: dict[tuple[str, str], list[dict]] = defaultdict(list)
    cause_agg: dict[str, list[dict]] = defaultdict(list)
    hour_counts: dict[int, int] = defaultdict(int)
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

            record = {"closure": closure, "ict": ict}
            cc_agg[(corridor, cause)].append(record)
            cause_agg[cause].append(record)
            hour_counts[start.astimezone(IST).hour] += 1

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
                }
            )

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
        cc_rate, cc_ict = cc_stats.get((r["corridor"], r["cause"]), (DEFAULT_PRIOR_CLOSURE_RATE, DEFAULT_PRIOR_ICT_H))
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
            }
        )

    return pd.DataFrame(built)


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


def train_closure_model(df: pd.DataFrame) -> tuple[object, object, dict[str, float]]:
    x = df[FEATURE_COLUMNS]
    y = df["closure"]
    x_train, x_val, y_train, y_val = train_test_split(x, y, test_size=0.2, random_state=42, stratify=y)

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
    return base, calibrator, importances


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Train M03 impact models")
    parser.add_argument("--csv", type=Path, default=settings.astram_csv_path)
    parser.add_argument("--out", type=Path, default=settings.models_dir)
    args = parser.parse_args()

    print(f"Loading {args.csv}...")
    raw = load_training_frame(args.csv)
    encoders = build_encoders(raw)
    df = apply_encoders(raw, encoders)

    print(f"Training on {len(df)} rows ({df['closure'].mean():.1%} closure rate)...")
    closure_model, calibrator, importances = train_closure_model(df)
    cox_model = train_cox_model(df)

    args.out.mkdir(parents=True, exist_ok=True)
    joblib.dump(closure_model, args.out / "closure_model.joblib")
    joblib.dump(calibrator, args.out / "closure_calibrator.joblib")
    joblib.dump(cox_model, args.out / "cox_model.joblib")
    joblib.dump(encoders, args.out / "encoders.joblib")

    metadata = {
        "closure_version": "lgbm-v1",
        "ict_version": "cox-ph-v1",
        "source": "ml",
        "trained_at": datetime.now(UTC).isoformat(),
        "training_rows": len(df),
        "closure_positive_rate": round(float(df["closure"].mean()), 4),
    }
    with (args.out / "metadata.json").open("w") as f:
        json.dump(metadata, f, indent=2)

    ranked = sorted(importances.items(), key=lambda x: x[1], reverse=True)
    fi = {k: round(v, 4) for k, v in ranked}
    with (args.out / "feature_importance.json").open("w") as f:
        json.dump(fi, f, indent=2)

    print(f"Artifacts saved to {args.out}")
    print(f"Top features: {list(fi.items())[:5]}")


if __name__ == "__main__":
    main()
