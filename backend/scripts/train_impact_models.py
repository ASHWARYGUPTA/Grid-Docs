#!/usr/bin/env python3
"""Train M03 closure classifier + Cox PH ICT model from ASTraM CSV.

Feature engineering + training logic lives in grid_unlocked.learning.training_core
(shared with M13's live retrain pipeline). This script is a thin CLI wrapper
around it for offline full-corpus training.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import joblib

from grid_unlocked.config import settings
from grid_unlocked.learning.training_core import (
    apply_encoders,
    build_encoders,
    load_csv_frame,
    train_closure_model,
    train_cox_model,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train M03 impact models")
    parser.add_argument("--csv", type=Path, default=settings.astram_csv_path)
    parser.add_argument("--out", type=Path, default=settings.models_dir)
    args = parser.parse_args()

    print(f"Loading {args.csv}...")
    raw = load_csv_frame(args.csv)
    encoders = build_encoders(raw)
    df = apply_encoders(raw, encoders)

    print(f"Training on {len(df)} rows ({df['closure'].mean():.1%} closure rate)...")
    closure_model, calibrator, importances, _val_df, _train_df = train_closure_model(
        df, temporal_split=False
    )
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
