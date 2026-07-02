"""
TOPSIS multi-objective ranking for procurement options.

TOPSIS (Technique for Order of Preference by Similarity to Ideal Solution):
- Normalises each criterion to [0,1]
- Computes distance to ideal (best on all dimensions) and anti-ideal (worst)
- Score = dist_anti / (dist_ideal + dist_anti)
- Options closest to ideal and furthest from anti-ideal rank highest

Criterion weights (sourced from India energy security literature / IEA supply
security scoring framework):
  cost           0.35  — primary constraint for public procurement
  lead_time      0.25  — time to bridge supply gap
  compatibility  0.25  — yield loss affects refinery economics directly
  corridor_risk  0.15  — probability of the route itself being disrupted
"""
from __future__ import annotations

import math
from copy import deepcopy

from contracts.outputs import ProcurementOption, ScoreBreakdown

_WEIGHTS = {
    "cost":          0.35,
    "lead_time":     0.25,
    "compatibility": 0.25,
    "corridor_risk": 0.15,
}


def rank(options: list[ProcurementOption]) -> list[ProcurementOption]:
    """
    TOPSIS ranking over landed_cost, lead_time, grade_compatibility, corridor_risk.
    Returns a new list sorted by topsis_score descending, with score_breakdown populated.
    """
    if not options:
        return []
    if len(options) == 1:
        o = deepcopy(options[0])
        o.topsis_score = 1.0
        o.score_breakdown = ScoreBreakdown(
            cost_score=1.0, lead_time_score=1.0,
            grade_compatibility_score=o.grade_compatibility,
            corridor_risk_score=1.0 - o.corridor_risk,
        )
        return [o]

    costs   = [o.landed_cost_usd_bbl  for o in options]
    times   = [o.lead_time_days        for o in options]
    compats = [o.grade_compatibility   for o in options]
    risks   = [o.corridor_risk         for o in options]

    # Normalise to [0,1]: for cost/time/risk lower=better → invert after normalise
    def _norm(vals: list[float]) -> list[float]:
        lo, hi = min(vals), max(vals)
        if hi == lo:
            return [0.5] * len(vals)
        return [(v - lo) / (hi - lo) for v in vals]

    n_cost   = _norm(costs)
    n_time   = _norm(times)
    n_compat = _norm(compats)
    n_risk   = _norm(risks)

    # Ideal: cost=0 (cheapest), time=0 (fastest), compat=1 (best fit), risk=0 (lowest)
    # Anti-ideal: cost=1, time=1, compat=0, risk=1
    ideal      = [0.0, 0.0, 1.0, 0.0]
    anti_ideal = [1.0, 1.0, 0.0, 1.0]
    w = [_WEIGHTS["cost"], _WEIGHTS["lead_time"], _WEIGHTS["compatibility"], _WEIGHTS["corridor_risk"]]

    scores: list[float] = []
    breakdowns: list[ScoreBreakdown] = []

    for i in range(len(options)):
        v = [n_cost[i], n_time[i], n_compat[i], n_risk[i]]

        d_ideal = math.sqrt(sum(w[j] * (v[j] - ideal[j])**2      for j in range(4)))
        d_anti  = math.sqrt(sum(w[j] * (v[j] - anti_ideal[j])**2 for j in range(4)))

        topsis = d_anti / (d_ideal + d_anti) if (d_ideal + d_anti) > 0 else 0.5
        scores.append(round(topsis, 4))

        breakdowns.append(ScoreBreakdown(
            cost_score=            round(1.0 - n_cost[i], 4),    # inverted: high=cheap
            lead_time_score=       round(1.0 - n_time[i], 4),    # inverted: high=fast
            grade_compatibility_score=round(n_compat[i], 4),
            corridor_risk_score=   round(1.0 - n_risk[i], 4),    # inverted: high=safe
        ))

    ranked = []
    for i, opt in enumerate(options):
        o = deepcopy(opt)
        o.topsis_score   = scores[i]
        o.score_breakdown = breakdowns[i]
        ranked.append(o)

    ranked.sort(key=lambda o: o.topsis_score, reverse=True)
    return ranked
