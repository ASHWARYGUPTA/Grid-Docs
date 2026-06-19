"""Model registry — loads LightGBM + Cox PH artifacts or falls back to rule-based scoring."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from grid_unlocked.config import settings
from grid_unlocked.features.schemas import FeatureVector
from grid_unlocked.impact.feature_matrix import FEATURE_COLUMNS, vector_to_row
from grid_unlocked.impact.rci import compute_rci, ict_bands_from_median, severity_band_from_rci

logger = logging.getLogger(__name__)

VIP_CAUSES = frozenset({"vip_movement"})


@dataclass
class ScoreResult:
    p_closure: float
    ict_p20_h: float
    ict_p50_h: float
    ict_p80_h: float
    rci: float
    severity_band: str
    staging_recommended: bool
    closure_version: str
    ict_version: str
    source: str
    top_features: list[dict[str, float | str]] = field(default_factory=list)


class ModelRegistry:
    def __init__(self, models_dir: Path | None = None) -> None:
        self.models_dir = models_dir or settings.models_dir
        self._closure_model: Any = None
        self._calibrator: Any = None
        self._cox_model: Any = None
        self._encoders: dict[str, Any] = {}
        self._metadata: dict[str, Any] = {}
        self._feature_importance: dict[str, float] = {}
        self._loaded = False
        self._ml_available = False

    def load(self) -> None:
        if self._loaded:
            return
        meta_path = self.models_dir / "metadata.json"
        if not meta_path.exists():
            logger.warning("M03 models not found at %s — using rule-based fallback", self.models_dir)
            self._metadata = {"closure_version": "rule-v1", "ict_version": "rule-v1", "source": "rule_fallback"}
            self._loaded = True
            return

        with meta_path.open() as f:
            self._metadata = json.load(f)

        self._encoders = joblib.load(self.models_dir / "encoders.joblib")
        self._closure_model = joblib.load(self.models_dir / "closure_model.joblib")
        self._calibrator = joblib.load(self.models_dir / "closure_calibrator.joblib")
        self._cox_model = joblib.load(self.models_dir / "cox_model.joblib")
        fi_path = self.models_dir / "feature_importance.json"
        if fi_path.exists():
            with fi_path.open() as f:
                self._feature_importance = json.load(f)
        self._ml_available = True
        self._loaded = True
        logger.info("M03 models loaded from %s", self.models_dir)

    @property
    def versions(self) -> dict[str, str]:
        self.load()
        return {
            "closure": self._metadata.get("closure_version", "rule-v1"),
            "ict": self._metadata.get("ict_version", "rule-v1"),
            "source": self._metadata.get("source", "rule_fallback"),
        }

    def score(
        self,
        features: FeatureVector,
        *,
        is_planned: bool,
        event_cause: str,
        corridor: str | None,
    ) -> ScoreResult:
        self.load()
        if self._ml_available:
            return self._score_ml(features, is_planned=is_planned, event_cause=event_cause, corridor=corridor)
        return self._score_rules(features, is_planned=is_planned, event_cause=event_cause)

    def _score_ml(
        self,
        features: FeatureVector,
        *,
        is_planned: bool,
        event_cause: str,
        corridor: str | None,
    ) -> ScoreResult:
        df = vector_to_row(
            features,
            is_planned=is_planned,
            event_cause=event_cause,
            corridor=corridor,
            encoders=self._encoders,
        )

        p_raw = float(self._closure_model.predict_proba(df[FEATURE_COLUMNS])[0, 1])
        p_closure = float(self._calibrator.predict([p_raw])[0])

        if is_planned:
            p_closure = max(p_closure, 0.36)
        if event_cause in VIP_CAUSES:
            p_closure = max(p_closure, 0.80)

        ict_p20, ict_p50, ict_p80 = self._predict_ict_quantiles(df)
        rci = compute_rci(features, p_closure)
        band = severity_band_from_rci(rci)
        top = self._top_features(5)

        return ScoreResult(
            p_closure=round(p_closure, 4),
            ict_p20_h=ict_p20,
            ict_p50_h=ict_p50,
            ict_p80_h=ict_p80,
            rci=rci,
            severity_band=band.value,
            staging_recommended=p_closure > settings.closure_alert_threshold,
            closure_version=self._metadata["closure_version"],
            ict_version=self._metadata["ict_version"],
            source="ml",
            top_features=top,
        )

    def _predict_ict_quantiles(self, df: pd.DataFrame) -> tuple[float, float, float]:
        try:
            cox_cols = getattr(self._cox_model, "_grid_cox_features", FEATURE_COLUMNS)
            surv_fn = self._cox_model.predict_survival_function(df[cox_cols])
            times = surv_fn.index.values.astype(float)
            probs = surv_fn.values.flatten()

            def quantile_at(prob: float) -> float:
                idx = np.where(probs <= prob)[0]
                if len(idx) == 0:
                    return float(times[-1])
                return float(times[idx[0]])

            return (
                round(max(0.1, quantile_at(0.80)), 2),
                round(max(0.1, quantile_at(0.50)), 2),
                round(max(0.1, quantile_at(0.20)), 2),
            )
        except Exception:
            return ict_bands_from_median(float(df["duration_prior_h"].iloc[0]))

    def _score_rules(
        self,
        features: FeatureVector,
        *,
        is_planned: bool,
        event_cause: str,
    ) -> ScoreResult:
        p_closure = features.corridor_cause_closure_rate
        if is_planned:
            p_closure = max(p_closure, 0.36)
        if event_cause in VIP_CAUSES:
            p_closure = max(p_closure, 0.80)

        ict_p20, ict_p50, ict_p80 = ict_bands_from_median(features.duration_prior_h)
        rci = compute_rci(features, p_closure)
        band = severity_band_from_rci(rci)

        return ScoreResult(
            p_closure=round(p_closure, 4),
            ict_p20_h=ict_p20,
            ict_p50_h=ict_p50,
            ict_p80_h=ict_p80,
            rci=rci,
            severity_band=band.value,
            staging_recommended=p_closure > settings.closure_alert_threshold,
            closure_version="rule-v1",
            ict_version="rule-v1",
            source="rule_fallback",
            top_features=[
                {"feature": "corridor_cause_closure_rate", "importance": 1.0},
                {"feature": "duration_prior_h", "importance": 0.8},
            ],
        )

    def _top_features(self, n: int) -> list[dict[str, float | str]]:
        if not self._feature_importance:
            return []
        ranked = sorted(self._feature_importance.items(), key=lambda x: x[1], reverse=True)[:n]
        return [{"feature": k, "importance": round(v, 4)} for k, v in ranked]

    def explain(
        self,
        features: FeatureVector,
        *,
        is_planned: bool,
        event_cause: str,
        corridor: str | None,
    ) -> list[dict[str, float | str]]:
        self.load()
        if self._ml_available and self._feature_importance:
            return self._top_features(5)
        return self._score_rules(features, is_planned=is_planned, event_cause=event_cause).top_features


registry = ModelRegistry()
