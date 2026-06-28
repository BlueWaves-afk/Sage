"""
Real-options valuation for SPR drawdown timing.

Values the option of WAITING before a major drawdown.
If there is a 30% chance the crisis resolves in 5 days, waiting has positive option value —
drawing down now is irreversible and expensive to refill.

Used to adjust the SDP policy when crisis duration is uncertain.
"""
from __future__ import annotations


def option_value_of_waiting(
    p_crisis_resolves: float,
    resolution_days: float,
    refill_cost_premium: float,
    gap_mbpd: float,
) -> float:
    """
    Returns option value (USD/bbl equivalent) of delaying drawdown by `resolution_days`.
    Positive value → wait. Negative → draw now.
    Stub — implement binomial option model in Week 2.
    """
    # TODO: model drawdown as irreversible investment (binomial tree over crisis scenarios)
    # TODO: compare NPV(draw now) vs NPV(wait × p_resolve + draw × (1-p_resolve))
    return 0.0
