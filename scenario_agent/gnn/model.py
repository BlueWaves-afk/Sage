"""
Cascade surrogate model.

⚠️ MEASURED REALITY (don't skip this): our analytic ARIO is a cheap pure-Python day-loop
at ~0.04 ms/call. A surrogate emulating it is SLOWER (~13 ms for a tree ensemble) and less
accurate at the operating points that matter (full closure). **So for the current ARIO,
run ARIO directly in the sandbox** — 500 Monte-Carlo paths × 0.04 ms ≈ 20 ms, well under
the 150 ms target. `scenario_agent.runner._run_gnn` therefore calls ARIO directly.

The surrogate earns its keep only when the ground-truth cascade is EXPENSIVE — i.e. when
ARIO is replaced/augmented by a full agent-based model (ABM) that takes seconds per run
(the plan's "ARIO + ABM + GNN surrogate"). Then this surrogate, trained on ABM outputs,
restores interactive speed. The infra below is ready for that; it's currently trained on
ARIO as a placeholder/proof.

Backends behind one interface:
  • sklearn tree-ensemble (default) — CPU, trains in seconds.
  • torch GraphSAGE/GAT (future) — for when graph *structure* varies; GPU.

Trained weights: scenario_agent/gnn/weights/cascade_surrogate.joblib (see train.py).
"""
from __future__ import annotations

from typing import Optional

from scenario_agent.ario import ARIOParams, ARIOResult, run as run_ario


class CascadeSurrogate:
    """Fast ARIO emulator. predict(params) → ARIOResult-shaped dict in <1ms."""

    def __init__(self, bundle: dict):
        self._model   = bundle["model"]
        self.features = bundle["features"]
        self.targets  = bundle["targets"]

    @classmethod
    def load(cls, path: str = "scenario_agent/gnn/weights/cascade_surrogate.joblib") -> "CascadeSurrogate":
        import joblib
        return cls(joblib.load(path))

    def predict(self, params: ARIOParams) -> dict:
        """Return the cascade scalars (gap, price band, SPR depletion, GDP)."""
        import numpy as np
        x = np.array([[getattr(params, f) for f in self.features]], dtype=float)
        out = self._model.predict(x)[0]
        return {t: round(float(v), 4) for t, v in zip(self.targets, out)}


def predict_cascade(params: ARIOParams, weights: Optional[str] = None) -> dict:
    """
    Convenience: load the surrogate and predict, falling back to analytic ARIO if no
    trained weights exist yet. Used by orchestration/sandbox.py and scenario_agent.runner.
    """
    try:
        surrogate = CascadeSurrogate.load(weights or "scenario_agent/gnn/weights/cascade_surrogate.joblib")
        return surrogate.predict(params)
    except Exception:
        r: ARIOResult = run_ario(params)   # exact fallback — slower but always available
        return {
            "gap_mbpd": r.gap_mbpd, "gap_duration_days": r.gap_duration_days,
            "spr_depletion_days": r.spr_depletion_days,
            "price_impact_low": r.price_impact_low, "price_impact_high": r.price_impact_high,
            "gdp_proxy_impact_pct": r.gdp_proxy_impact_pct,
        }


# Back-compat alias (sandbox/runner referenced CascadeGNN).
CascadeGNN = CascadeSurrogate
