#!/usr/bin/env python3
"""Evaluate performance metrics of M03 closure and Cox PH survival models."""

from __future__ import annotations

import argparse
import math
from datetime import UTC, datetime
import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_recall_curve, auc, f1_score, roc_auc_score, accuracy_score
from lifelines.utils import concordance_index

from grid_unlocked.config import settings
from grid_unlocked.impact.feature_matrix import FEATURE_COLUMNS
from grid_unlocked.impact.rci import compute_rci, ict_bands_from_median
from grid_unlocked.features.schemas import FeatureVector
from grid_unlocked.learning.training_core import IST, apply_encoders, load_csv_frame as load_training_frame

def expected_calibration_error(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        bin_lower = bin_boundaries[i]
        bin_upper = bin_boundaries[i + 1]
        in_bin = (y_prob >= bin_lower) & (y_prob < bin_upper)
        prop_in_bin = np.mean(in_bin)
        if prop_in_bin > 0:
            accuracy_in_bin = np.mean(y_true[in_bin])
            avg_confidence_in_bin = np.mean(y_prob[in_bin])
            ece += prop_in_bin * np.abs(avg_confidence_in_bin - accuracy_in_bin)
    return ece

def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate M03 model performance")
    parser.add_argument("--csv", type=Path, default=settings.astram_csv_path)
    parser.add_argument("--models", type=Path, default=settings.models_dir)
    args = parser.parse_args()

    if not args.models.exists() or not (args.models / "closure_model.joblib").exists():
        print(f"Models directory {args.models} not found or missing artifacts. Please train models first.")
        return

    print("Loading data and models...")
    raw = load_training_frame(args.csv)
    encoders = joblib.load(args.models / "encoders.joblib")
    df = apply_encoders(raw, encoders)

    closure_model = joblib.load(args.models / "closure_model.joblib")
    calibrator = joblib.load(args.models / "closure_calibrator.joblib")
    cox_model = joblib.load(args.models / "cox_model.joblib")

    x = df[FEATURE_COLUMNS]
    y = df["closure"]

    # Recreate the exact split used in training
    _, x_test, _, y_test = train_test_split(x, y, test_size=0.2, random_state=42, stratify=y)
    test_indices = y_test.index
    test_df = df.loc[test_indices].copy()

    # 1. Evaluate Closure Classifier
    raw_probs = closure_model.predict_proba(x_test)[:, 1]
    cal_probs = calibrator.predict(raw_probs)
    
    # Clip probabilities to [0, 1] just in case
    cal_probs = np.clip(cal_probs, 0.0, 1.0)

    # Compute metrics
    prec, rec, _ = precision_recall_curve(y_test, cal_probs)
    pr_auc = auc(rec, prec)
    roc_auc = roc_auc_score(y_test, cal_probs)
    
    threshold = settings.closure_alert_threshold
    preds = (cal_probs > threshold).astype(int)
    acc = accuracy_score(y_test, preds)
    dummy_acc = accuracy_score(y_test, np.zeros_like(y_test))
    f1_mac = f1_score(y_test, preds, average="macro")
    ece = expected_calibration_error(y_test.values, cal_probs)

    print("\n" + "="*50)
    print("M03 CLOSURE CLASSIFIER EVALUATION")
    print("="*50)
    print(f"PR-AUC (Target > 0.85):       {pr_auc:.4f}")
    print(f"ROC-AUC:                      {roc_auc:.4f}")
    print(f"F1-Macro (Threshold {threshold}):  {f1_mac:.4f}")
    print(f"Accuracy (Threshold {threshold}):  {acc:.4f}")
    print(f"Dummy Accuracy (Always No):   {dummy_acc:.4f}")
    print(f"ECE (Target < 0.05):          {ece:.4f}")

    # 2. Evaluate ICT Survival Model (Cox PH)
    cox_test_df = test_df.copy()
    cox_test_df["duration_h"] = cox_test_df["duration_h"].fillna(cox_test_df["duration_prior_h"])
    cox_test_df["duration_h"] = cox_test_df["duration_h"].clip(lower=0.05)

    cox_cols = getattr(cox_model, "_grid_cox_features", FEATURE_COLUMNS)
    
    # Predict survival functions on test set
    surv_fn = cox_model.predict_survival_function(cox_test_df[cox_cols])
    times = surv_fn.index.values.astype(float)
    
    # Compute P80 quantile (S(t) = 0.20) for each test record
    p80_times = []
    c_index_scores = []
    
    for i, col in enumerate(surv_fn.columns):
        probs = surv_fn[col].values
        
        # P80 definition: S(t) = 0.20
        idx = np.where(probs <= 0.20)[0]
        if len(idx) == 0:
            p80_times.append(float(times[-1]))
        else:
            p80_times.append(float(times[idx[0]]))
            
    # Calculate C-index
    # We predict the hazard score (or median duration). CoxPHFitter can predict expectation/partial hazard.
    predicted_partial_hazards = cox_model.predict_partial_hazard(cox_test_df[cox_cols])
    c_index = concordance_index(
        cox_test_df["duration_h"],
        -predicted_partial_hazards, # higher partial hazard means shorter survival time
        cox_test_df["event_observed"]
    )
    
    # Coverage of P80 (conservative duration estimate)
    # Target: S(t) = 0.20. Observed duration <= P80 time should be >= 78%
    actual_durations = cox_test_df["duration_h"].values
    observed_mask = cox_test_df["event_observed"].values == 1
    
    # Only evaluate coverage on observed/uncensored cases for pure coverage calculation
    covered = actual_durations[observed_mask] <= np.array(p80_times)[observed_mask]
    p80_coverage = np.mean(covered) if len(covered) > 0 else 1.0

    print("\n" + "="*50)
    print("M03 ICT SURVIVAL MODEL EVALUATION")
    print("="*50)
    print(f"C-index (Concordance Index):  {c_index:.4f}")
    print(f"P80 Coverage (Target >= 78%): {p80_coverage * 100:.2f}%")

    # 3. Evaluate RCI Spearman Rank Correlation
    rcis = []
    for idx, row in test_df.iterrows():
        # Reconstruct FeatureVector
        fv = FeatureVector(
            event_id=str(idx),
            graph_node_id=f"corridor:{row['corridor']}",
            hour_ist=int(row["hour_ist"]),
            dow=int(row["dow"]),
            hour_sin=float(row["hour_sin"]),
            hour_cos=float(row["hour_cos"]),
            dow_sin=float(row["dow_sin"]),
            dow_cos=float(row["dow_cos"]),
            is_peak_hour=bool(row["is_peak_hour"]),
            is_weekend=bool(row["is_weekend"]),
            reporting_bias_weight=float(row["reporting_bias_weight"]),
            betweenness_norm=float(row["betweenness_norm"]),
            degree_norm=float(row["degree_norm"]),
            h3_res7="872830828ffffff",  # dummy
            h3_res9="892830828bfffff",  # dummy
            is_named_corridor=bool(row["is_named_corridor"]),
            corridor_cause_closure_rate=float(row["corridor_cause_closure_rate"]),
            corridor_cause_median_ict_h=float(row["duration_prior_h"]),
            duration_prior_h=float(row["duration_prior_h"]),
            cause_median_resolution_global_h=float(row["cause_median_resolution_global_h"]),
            veh_complexity_score=float(row["veh_complexity_score"]),
            simultaneous_events_2km=int(row["simultaneous_events_2km"]),
            materialized_at=datetime.now(UTC),
        )
        # Compute RCI using the calibrated live closure probability
        rci = compute_rci(fv, p_closure=cal_probs[len(rcis)])
        rcis.append(rci)
        
    test_df["rci"] = rcis
    # Spearman rank correlation vs observed duration
    corr_df = test_df[test_df["event_observed"] == 1]
    spearman_corr = corr_df["rci"].corr(corr_df["duration_h"], method="spearman")

    print("\n" + "="*50)
    print("M02/M03 RCI EVALUATION")
    print("="*50)
    print(f"RCI vs Duration Spearman Corr: {spearman_corr:.4f}")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()
