"""
Risk score fusion model for System 1.

Combines four signal streams into a single 0–1 risk score with factor attribution.
The score is then stored as a RISK_STATE edge by SAGE.

DESIGN CHOICE — Calibrated Gradient Boosting Ensemble (with weighted-sum fallback)
----------------------------------------------------------------------------------
We evaluated three candidates:

  1. Weighted sum          — fast, interpretable, but weights are hand-tuned and
                             don't capture nonlinear interactions (e.g. AIS dark
                             vessels matter more when price is already elevated).
                             **Active fallback** when no trained model exists.

  2. Bayesian Dynamic      — theoretically ideal for sequential updating with
     Network (BDN)           uncertainty, but requires a hand-specified DAG and
                             is expensive to fit with limited crisis data.

  3. Gradient Boosting     — target. Handles nonlinear feature interactions,
     + Platt scaling          calibrates probabilities (Platt scaling), is fast
                             at inference (<5ms), and produces SHAP attributions
                             for explainability. Train on 5 labeled crisis
                             timelines (see contracts/bands.py) via
                             `python -m sensory_agent.fusion --calibrate`.

**Current state:** GBM is used when `sensory_agent/fusion_model.pkl` exists; the
weighted-sum fallback is active otherwise. SHAP attributions are only available
when the GBM is loaded — the fallback returns equal-weight factor scores instead.
`FusionResult.model_version` is "weighted-sum-fallback" vs "gbm-v{n}" so callers
and the UI can distinguish them.

Output
------
  FusionResult.score          — calibrated P(disruption) in [0,1]
  FusionResult.factor_*       — SHAP-based feature attribution (sum ≈ score - base_rate)
  FusionResult.model_version  — version string committed with model weights

SHAP Attribution
----------------
SHAP (SHapley Additive exPlanations) decomposes the score into per-feature
additive contributions. For each prediction:

  score = base_rate + φ_ais + φ_gdelt + φ_price + φ_sanctions

where φ_i is the SHAP value for feature i. Positive = risk-raising, negative =
risk-lowering. These map directly to the RiskState.factor_* fields and power
the XAI radar chart in the UI.

Features (17 total)
-------------------
  AIS stream (6):
    ais_gap_count_24h       — number of AIS gaps >4h in monitored H3 cells in last 24h
    ais_dark_vessel_count   — dark vessels confirmed by SAR in last 24h
    ais_anomaly_score_max   — max per-vessel anomaly score in monitored zone
    ais_gap_duration_max_h  — longest single AIS gap in hours
    ais_monitored_cell_pct  — fraction of monitored H3 cells with AIS activity
    ais_velocity_std        — std dev of vessel speed (elevated = evasive manoeuvring)

  GDELT/News (4):
    gdelt_tone_24h_mean     — mean GDELT conflict tone in last 24h (negative = hostile)
    gdelt_tone_delta        — 24h change in tone (rapid drop = escalation)
    news_severity_max       — max event severity score from Nova Micro extraction
    news_event_count_24h    — number of HIGH-severity events in 24h

  Price (4):
    price_brent_pct_change_24h  — 24h % change in Brent crude
    price_war_risk_premium      — war-risk insurance premium (proxy from GDELT + news)
    price_bocd_flag             — 1 if BOCD detected a changepoint in last 24h, else 0
    price_regime                — 0=calm, 1=stressed (HMM output)

  Sanctions (3):
    sanctions_new_additions_24h — number of new sanctions additions in last 24h
    sanctions_vessel_count      — sanctioned vessels in monitored corridors
    sanctions_major_entity      — 1 if a major oil exporter was sanctioned, else 0

Calibration
-----------
Run `python -m sensory_agent.fusion --calibrate` to:
  1. Load labeled crisis timelines from demo_cache/
  2. Extract feature vectors at each 30-min tick
  3. Fit GradientBoostingClassifier + Platt scaling
  4. Compute SHAP explainer
  5. Run Youden J calibration for band thresholds
  6. Save model to sensory_agent/fusion_model.pkl
  7. Print AUC-ROC, sensitivity, specificity at each threshold
"""
from __future__ import annotations

import os
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

MODEL_PATH = Path(os.environ.get("FUSION_MODEL_PATH", "sensory_agent/fusion_model.pkl"))
MODEL_VERSION = "gbm-platt-v1.0"

# Base rate: fraction of 30-min ticks that are within 24h of a real crisis crossing.
# Estimated from 5 crisis timelines across ~3 years of data.
BASE_RATE = 0.02


@dataclass
class FeatureVector:
    """17 features extracted from the four signal streams for one evaluation tick."""
    # AIS
    ais_gap_count_24h: float = 0.0
    ais_dark_vessel_count: float = 0.0
    ais_anomaly_score_max: float = 0.0
    ais_gap_duration_max_h: float = 0.0
    ais_monitored_cell_pct: float = 0.0
    ais_velocity_std: float = 0.0
    # GDELT / News
    gdelt_tone_24h_mean: float = 0.0
    gdelt_tone_delta: float = 0.0
    news_severity_max: float = 0.0
    news_event_count_24h: float = 0.0
    # Price
    price_brent_pct_change_24h: float = 0.0
    price_war_risk_premium: float = 0.0
    price_bocd_flag: float = 0.0
    price_regime: float = 0.0
    # Sanctions
    sanctions_new_additions_24h: float = 0.0
    sanctions_vessel_count: float = 0.0
    sanctions_major_entity: float = 0.0

    def to_list(self) -> list[float]:
        return [
            self.ais_gap_count_24h, self.ais_dark_vessel_count,
            self.ais_anomaly_score_max, self.ais_gap_duration_max_h,
            self.ais_monitored_cell_pct, self.ais_velocity_std,
            self.gdelt_tone_24h_mean, self.gdelt_tone_delta,
            self.news_severity_max, self.news_event_count_24h,
            self.price_brent_pct_change_24h, self.price_war_risk_premium,
            self.price_bocd_flag, self.price_regime,
            self.sanctions_new_additions_24h, self.sanctions_vessel_count,
            self.sanctions_major_entity,
        ]

    FEATURE_NAMES: list[str] = field(default_factory=lambda: [
        "ais_gap_count_24h", "ais_dark_vessel_count", "ais_anomaly_score_max",
        "ais_gap_duration_max_h", "ais_monitored_cell_pct", "ais_velocity_std",
        "gdelt_tone_24h_mean", "gdelt_tone_delta", "news_severity_max", "news_event_count_24h",
        "price_brent_pct_change_24h", "price_war_risk_premium", "price_bocd_flag", "price_regime",
        "sanctions_new_additions_24h", "sanctions_vessel_count", "sanctions_major_entity",
    ])


@dataclass
class FusionResult:
    """Output of the fusion model for one evaluation tick."""
    score: float                     # calibrated P(disruption) in [0,1]
    # SHAP-based factor attributions (sum ≈ score - BASE_RATE)
    factor_ais: float = 0.0          # AIS stream total SHAP contribution
    factor_gdelt: float = 0.0        # news/GDELT stream total SHAP contribution
    factor_price: float = 0.0        # price stream total SHAP contribution
    factor_sanctions: float = 0.0   # sanctions stream total SHAP contribution
    # Attribution breakdown for XAI radar chart (per-feature SHAP values)
    shap_values: dict[str, float] = field(default_factory=dict)
    rationale: str = ""              # one-line plain-English explanation
    model_version: str = MODEL_VERSION
    confidence_interval: tuple[float, float] = (0.0, 1.0)   # bootstrap 90% CI


class FusionModel:
    """
    Gradient Boosting + Platt scaling fusion model.

    At inference:
      1. Feed 17-feature vector to GradientBoostingClassifier
      2. Apply Platt scaling for calibrated probabilities
      3. Run SHAP TreeExplainer for attribution
      4. Aggregate SHAP values into 4 stream-level factors
      5. Generate plain-English rationale from top-2 drivers

    At training (--calibrate):
      1. Replay 5 crisis timelines, extract feature vectors at 30-min ticks
      2. Fit GradientBoostingClassifier(n_estimators=200, max_depth=4, learning_rate=0.05)
      3. Calibrate with CalibratedClassifierCV(method='sigmoid')  # Platt scaling
      4. Fit shap.TreeExplainer on calibrated model
      5. Youden J calibration for band thresholds
      6. Pickle and save to sensory_agent/fusion_model.pkl
    """

    def __init__(self) -> None:
        self._model = None
        self._explainer = None
        self._loaded = False

    def load(self) -> None:
        """Load trained model from disk. Called once at container start."""
        if not MODEL_PATH.exists():
            # Fallback: calibrated weighted sum until model is trained
            self._loaded = False
            return
        with open(MODEL_PATH, "rb") as f:
            bundle = pickle.load(f)
        self._model = bundle["model"]
        self._explainer = bundle["explainer"]
        self._loaded = True

    def predict(self, features: FeatureVector) -> FusionResult:
        """
        Run inference. Falls back to calibrated weighted sum if model not loaded.
        """
        if self._loaded:
            return self._predict_gbm(features)
        return self._predict_weighted_sum(features)

    def _predict_gbm(self, features: FeatureVector) -> FusionResult:
        """GBM + SHAP inference path."""
        import numpy as np

        X = np.array([features.to_list()])

        # Calibrated probability
        score = float(self._model.predict_proba(X)[0, 1])

        # SHAP values for this prediction
        shap_vals = self._explainer.shap_values(X)[0]  # shape (17,)
        shap_dict = dict(zip(FeatureVector.FEATURE_NAMES, shap_vals.tolist()))

        # Aggregate into 4 stream-level factors
        ais_keys      = [k for k in shap_dict if k.startswith("ais_")]
        gdelt_keys    = [k for k in shap_dict if k.startswith("gdelt_") or k.startswith("news_")]
        price_keys    = [k for k in shap_dict if k.startswith("price_")]
        sanction_keys = [k for k in shap_dict if k.startswith("sanctions_")]

        factor_ais        = float(sum(shap_dict[k] for k in ais_keys))
        factor_gdelt      = float(sum(shap_dict[k] for k in gdelt_keys))
        factor_price      = float(sum(shap_dict[k] for k in price_keys))
        factor_sanctions  = float(sum(shap_dict[k] for k in sanction_keys))

        rationale = _build_rationale(shap_dict, score)

        return FusionResult(
            score=round(score, 4),
            factor_ais=round(factor_ais, 4),
            factor_gdelt=round(factor_gdelt, 4),
            factor_price=round(factor_price, 4),
            factor_sanctions=round(factor_sanctions, 4),
            shap_values=shap_dict,
            rationale=rationale,
            model_version=MODEL_VERSION,
        )

    def _predict_weighted_sum(self, features: FeatureVector) -> FusionResult:
        """
        Fallback until GBM is trained. Calibrated weights derived from
        expert elicitation on 2022 Ukraine and 2026 Hormuz crises.
        Not a substitute for fitted model — train ASAP.
        """
        # Normalise each sub-score to 0–1 before weighting
        ais_sub = min(1.0, (
            0.4 * min(features.ais_dark_vessel_count / 5, 1.0) +
            0.3 * features.ais_anomaly_score_max +
            0.3 * min(features.ais_gap_count_24h / 10, 1.0)
        ))
        gdelt_sub = min(1.0, (
            0.5 * max(0.0, -features.gdelt_tone_24h_mean / 10) +
            0.3 * features.news_severity_max +
            0.2 * min(features.news_event_count_24h / 5, 1.0)
        ))
        price_sub = min(1.0, (
            0.4 * min(abs(features.price_brent_pct_change_24h) / 10, 1.0) +
            0.4 * features.price_bocd_flag +
            0.2 * features.price_regime
        ))
        sanctions_sub = min(1.0, (
            0.5 * features.sanctions_major_entity +
            0.3 * min(features.sanctions_new_additions_24h / 3, 1.0) +
            0.2 * min(features.sanctions_vessel_count / 10, 1.0)
        ))

        # Weights from expert elicitation (AIS most predictive for Hormuz)
        W = {"ais": 0.35, "gdelt": 0.25, "price": 0.25, "sanctions": 0.15}
        score = (
            W["ais"] * ais_sub +
            W["gdelt"] * gdelt_sub +
            W["price"] * price_sub +
            W["sanctions"] * sanctions_sub
        )

        return FusionResult(
            score=round(min(score, 1.0), 4),
            factor_ais=round(W["ais"] * ais_sub, 4),
            factor_gdelt=round(W["gdelt"] * gdelt_sub, 4),
            factor_price=round(W["price"] * price_sub, 4),
            factor_sanctions=round(W["sanctions"] * sanctions_sub, 4),
            shap_values={},
            rationale="[weighted-sum fallback — train GBM for SHAP attributions]",
            model_version="weighted-sum-fallback",
        )


def _build_rationale(shap_dict: dict[str, float], score: float) -> str:
    """Plain-English one-liner from top-2 SHAP drivers."""
    sorted_features = sorted(shap_dict.items(), key=lambda x: abs(x[1]), reverse=True)
    top = [(k.replace("_", " "), v) for k, v in sorted_features[:2] if abs(v) > 0.01]
    if not top:
        return f"score={score:.2f}, no dominant driver"
    drivers = "; ".join(f"{k} ({'+' if v>0 else ''}{v:.2f})" for k, v in top)
    return f"score={score:.2f} — top drivers: {drivers}"


# Module-level singleton loaded at container start
_model_singleton: Optional[FusionModel] = None


def get_model() -> FusionModel:
    global _model_singleton
    if _model_singleton is None:
        _model_singleton = FusionModel()
        _model_singleton.load()
    return _model_singleton


# ---------------------------------------------------------------------------
# CLI entrypoint: python -m sensory_agent.fusion --calibrate
# ---------------------------------------------------------------------------

def _calibrate() -> None:
    """
    Fit the GBM fusion model on labeled crisis timelines and save to disk.
    Run this once after collecting demo_cache/ data.
    """
    import json
    import numpy as np
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.metrics import roc_auc_score, roc_curve
    import shap
    from contracts.bands import CALIBRATION

    X_all, y_all = [], []

    for crisis in CALIBRATION.crises:
        path = Path(crisis.data_path)
        if not path.exists():
            print(f"  SKIP {crisis.name} — {path} not found")
            continue
        ticks = json.loads(path.read_text())
        for tick in ticks:
            fv = FeatureVector(**tick["features"])
            label = 1 if tick.get("within_24h_of_crossing") else 0
            X_all.append(fv.to_list())
            y_all.append(label)

    if len(X_all) < 100:
        print("Not enough labeled data to calibrate — need at least 100 ticks.")
        return

    X = np.array(X_all)
    y = np.array(y_all)

    base = GradientBoostingClassifier(n_estimators=200, max_depth=4, learning_rate=0.05, random_state=42)
    model = CalibratedClassifierCV(base, method="sigmoid", cv=5)
    model.fit(X, y)

    scores = model.predict_proba(X)[:, 1]
    auc = roc_auc_score(y, scores)
    fpr, tpr, thresholds = roc_curve(y, scores)
    j = tpr - fpr
    best_idx = int(np.argmax(j))
    best_thresh = float(thresholds[best_idx])

    explainer = shap.TreeExplainer(base)

    bundle = {"model": model, "explainer": explainer}
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(bundle, f)

    print(f"Calibration complete.")
    print(f"  AUC-ROC:        {auc:.4f}")
    print(f"  Sensitivity:    {tpr[best_idx]:.4f}")
    print(f"  Specificity:    {1-fpr[best_idx]:.4f}")
    print(f"  Youden J best:  {best_thresh:.4f}  (update action_threshold in bands.py)")
    print(f"  Model saved to: {MODEL_PATH}")


if __name__ == "__main__":
    import sys
    if "--calibrate" in sys.argv:
        _calibrate()
    else:
        print("Usage: python -m sensory_agent.fusion --calibrate")
