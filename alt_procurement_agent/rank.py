"""
TOPSIS multi-objective ranking.

Ranks procurement options over: total landed cost, lead time,
grade compatibility, corridor risk. Returns Pareto-optimal ordered list.
"""
from __future__ import annotations

from contracts.outputs import ProcurementOption


def rank(options: list[ProcurementOption]) -> list[ProcurementOption]:
    """
    TOPSIS ranking over the four objective dimensions.
    Returns options sorted by topsis_score descending.
    Stub — implement TOPSIS in Week 2.
    """
    # TODO: normalise each dimension to [0,1]
    # TODO: apply weights: cost 0.35, lead_time 0.25, compatibility 0.25, risk 0.15
    # TODO: compute TOPSIS ideal/anti-ideal distances
    # TODO: return sorted list with topsis_score populated
    raise NotImplementedError
