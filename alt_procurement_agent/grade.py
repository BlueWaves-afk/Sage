"""
Crude grade compatibility model.

Deterministic Gaussian API/sulfur distance model, calibrated to published
refinery processing windows. Produces transparent, auditable 0..1 scores.

Calibration sources:
- API tolerance window ±8°: IEA Refinery Complexity study; PPAC NCI guidance
- Sulfur tolerance ±0.5 wt%: EIA crude assay economics / desulphuriser capacity norms
- Weight split 0.6/0.4 API/sulfur: EIA crude assay sensitivity analysis

RF+PR-EOS upgrade path: system3_design.md §3.1 — drop-in when yield curves available.
"""
from __future__ import annotations

import math
import os

from knowledge.api.read import GradeSpecView

_GRADE_DEFAULTS = {
    "grade_api_sigma":     8.0,
    "grade_sulfur_sigma":  0.5,
    "grade_api_floor":     0.25,
    "grade_sulfur_floor":  0.30,
    "grade_api_weight":    0.6,
    "grade_sulfur_weight": 0.4,
}


def _load_grade_params() -> dict:
    bundle_path = os.environ.get("SAGE_BUNDLE_PATH", "")
    if not bundle_path:
        return _GRADE_DEFAULTS.copy()
    try:
        from knowledge.context.loader import load_bundle
        gp = load_bundle(bundle_path).grade_params
        return {k: float(gp.get(k, {"value": v})["value"]) for k, v in _GRADE_DEFAULTS.items()}
    except Exception:
        return _GRADE_DEFAULTS.copy()


def compatibility_score(
    supplier_grade_api: float,
    supplier_grade_sulfur: float,
    refinery_spec: GradeSpecView,
) -> float:
    """
    Returns compatibility 0..1 for a supplier crude against one configured grade spec.

    1.0  = drop-in within tolerance window
    ~0.5 = processable with yield penalty / blending needed
    <0.3 = significant throughput loss; avoid unless no alternative

    All tolerance parameters (API/sulfur sigma, floors, weights) read from bundle
    grade_params.csv; no hardcoded values in this function.
    """
    # Bundle CONFIGURED_FOR edges may carry LP-calibrated compatibility directly.
    if refinery_spec.compatibility is not None:
        return float(refinery_spec.compatibility)

    ref_api    = refinery_spec.api_gravity
    ref_sulfur = refinery_spec.sulfur_pct
    if ref_api is None or ref_sulfur is None:
        return 0.5  # no spec data — neutral

    p = _load_grade_params()
    api_score    = _gaussian(supplier_grade_api,    ref_api,    p["grade_api_sigma"],    p["grade_api_floor"])
    sulfur_score = _gaussian(supplier_grade_sulfur, ref_sulfur, p["grade_sulfur_sigma"], p["grade_sulfur_floor"])
    return round(max(0.0, min(1.0, p["grade_api_weight"] * api_score + p["grade_sulfur_weight"] * sulfur_score)), 4)


def best_compatibility(
    supplier_grade_api: float,
    supplier_grade_sulfur: float,
    grade_specs: list[GradeSpecView],
) -> float:
    """Best compatibility score across all of a refinery's configured grade specs."""
    if not grade_specs:
        return 0.5
    return max(
        compatibility_score(supplier_grade_api, supplier_grade_sulfur, s)
        for s in grade_specs
    )


def _gaussian(value: float, centre: float, sigma: float, floor: float) -> float:
    z = (value - centre) / sigma
    return floor + (1.0 - floor) * math.exp(-0.5 * z * z)
