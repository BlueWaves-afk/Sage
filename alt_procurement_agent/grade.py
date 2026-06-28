"""
Crude grade compatibility model.

Semi-empirical Random Forest + Peng-Robinson EOS:
yield profiles and processing penalties per supplier-refinery-grade combination.
Validated against refinery LP (PIMS-style) — not presented as superior to rigorous simulation.

Crude is NOT fungible: API gravity + sulfur determine refinery processing economics.
"""
from __future__ import annotations

from knowledge.api.read import GradeSpecView


def compatibility_score(
    supplier_grade_api: float,
    supplier_grade_sulfur: float,
    refinery_spec: GradeSpecView,
) -> float:
    """
    Returns compatibility 0..1 for a supplier grade against a refinery's configured spec.
    Stub — implement RF + PR-EOS in Week 2.
    """
    # TODO: load trained Random Forest model
    # TODO: compute Peng-Robinson EOS yield penalty for API/sulfur deviation
    # TODO: return weighted compatibility score
    raise NotImplementedError
