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

from knowledge.api.read import GradeSpecView

_API_SIGMA    = 8.0   # one-sigma API tolerance (°API)
_SULFUR_SIGMA = 0.5   # one-sigma sulfur tolerance (wt %)
_API_FLOOR    = 0.25  # minimum for fully mismatched API (blending still possible)
_SULFUR_FLOOR = 0.30  # minimum for fully mismatched sulfur


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
    """
    # Bundle CONFIGURED_FOR edges may carry LP-calibrated compatibility directly.
    if refinery_spec.compatibility is not None:
        return float(refinery_spec.compatibility)

    ref_api    = refinery_spec.api_gravity
    ref_sulfur = refinery_spec.sulfur_pct
    if ref_api is None or ref_sulfur is None:
        return 0.5  # no spec data — neutral

    api_score    = _gaussian(supplier_grade_api,    ref_api,    _API_SIGMA,    _API_FLOOR)
    sulfur_score = _gaussian(supplier_grade_sulfur, ref_sulfur, _SULFUR_SIGMA, _SULFUR_FLOOR)
    return round(max(0.0, min(1.0, 0.6 * api_score + 0.4 * sulfur_score)), 4)


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
