"""M13 — model evaluation against the replay buffer.

Computes accuracy on the recent-pool validation slice (the "governance-
approved operational validation slice" for MVP) and on the anchor slice,
then checks both promotion-gate criteria from the spec:
  - accuracy_gate: overall accuracy >= settings.learning_accuracy_gate (94%)
  - anchor_stable: anchor accuracy must not regress > epsilon vs incumbent
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score

from grid_unlocked.config import settings
from grid_unlocked.impact.feature_matrix import FEATURE_COLUMNS


@dataclass
class EvalResult:
    accuracy: float
    anchor_accuracy: float
    incumbent_anchor_accuracy: float | None
    anchor_regression: float | None
    gate_passed: bool
    anchor_stable: bool


def _accuracy_on(model, calibrator, df: pd.DataFrame) -> float:
    if df.empty:
        return 0.0
    x = df[FEATURE_COLUMNS]
    raw_probs = model.predict_proba(x)[:, 1]
    cal_probs = np.clip(calibrator.predict(raw_probs), 0.0, 1.0)
    preds = (cal_probs > settings.closure_alert_threshold).astype(int)
    return float(accuracy_score(df["closure"], preds))


def evaluate(
    model,
    calibrator,
    val_df: pd.DataFrame,
    full_df: pd.DataFrame,
    *,
    incumbent_anchor_accuracy: float | None,
) -> EvalResult:
    accuracy = _accuracy_on(model, calibrator, val_df)

    anchor_rows = full_df[full_df["pool"] == "anchor"]
    anchor_accuracy = _accuracy_on(model, calibrator, anchor_rows) if not anchor_rows.empty else accuracy

    anchor_regression: float | None = None
    anchor_stable = True
    if incumbent_anchor_accuracy is not None:
        anchor_regression = round(incumbent_anchor_accuracy - anchor_accuracy, 4)
        anchor_stable = anchor_regression <= settings.learning_anchor_epsilon

    gate_passed = accuracy >= settings.learning_accuracy_gate

    return EvalResult(
        accuracy=round(accuracy, 4),
        anchor_accuracy=round(anchor_accuracy, 4),
        incumbent_anchor_accuracy=incumbent_anchor_accuracy,
        anchor_regression=anchor_regression,
        gate_passed=gate_passed,
        anchor_stable=anchor_stable,
    )
