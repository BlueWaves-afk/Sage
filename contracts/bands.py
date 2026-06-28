"""
C4 — Risk band thresholds. Single source of truth.

SAGE computes `band` at write time and stores it on the RISK_STATE edge.
Every reader reads the band string — no one re-implements this logic.
"""
from typing import Literal

RiskBand = Literal["calm", "watch", "elevated", "action", "critical"]

BANDS: list[tuple[float, RiskBand]] = [
    (0.90, "critical"),
    (0.70, "action"),
    (0.45, "elevated"),
    (0.25, "watch"),
    (0.00, "calm"),
]

UI_COLOURS: dict[RiskBand, str] = {
    "calm":     "#00FF41",  # phosphor green
    "watch":    "#00FFFF",  # cyan
    "elevated": "#FFA500",  # amber
    "action":   "#FF0000",  # red
    "critical": "#FF0000",  # pulsing red (handled client-side)
}

SANDBOX_FORK_THRESHOLD = 0.45    # elevated band — fork if P(crossing in 24h) > 0.5
SANDBOX_CONFIDENCE_MIN = 0.50    # minimum P(crossing) to trigger a fork
ACTION_THRESHOLD       = 0.70    # confirmed crossing — promote sandbox, fire systems 2-4
CRITICAL_THRESHOLD     = 0.90    # immediate human escalation


def score_to_band(score: float) -> RiskBand:
    """Map a 0..1 risk score to its named band. Called once at SAGE write time."""
    for threshold, band in BANDS:
        if score >= threshold:
            return band
    return "calm"
