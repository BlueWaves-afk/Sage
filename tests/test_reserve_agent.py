"""
System 4 (reserve_optim_agent) unit tests — no live services required.

Covers the SDP/CMDP Bellman solver and the real-options valuation.
"""
from __future__ import annotations

from reserve_optim_agent.sdp import SDPParams, solve
from reserve_optim_agent.options import option_value_of_waiting, waiting_recommendation


def test_sdp_plan_spans_horizon():
    res = solve(SDPParams(spr_initial_mmt=2.13, gap_mbpd=1.0, gap_duration_days=20, horizon_days=60))
    assert len(res.daily_plan) == 60
    assert 0.0 <= res.prob_above_buffer <= 1.0
    assert isinstance(res.constraint_satisfied, bool)


def test_sdp_reserve_non_increasing():
    """Reserve level only ever draws down (never spontaneously increases) within the plan."""
    res = solve(SDPParams(spr_initial_mmt=2.13, gap_mbpd=1.5, gap_duration_days=30, horizon_days=60))
    reserves = [d["reserve_after_mmt"] for d in res.daily_plan]
    assert all(reserves[i + 1] <= reserves[i] + 1e-6 for i in range(len(reserves) - 1))


def test_sdp_no_gap_holds_reserve():
    """With no supply gap, the optimal policy holds the reserve (no drawdown)."""
    res = solve(SDPParams(spr_initial_mmt=2.13, gap_mbpd=0.0, gap_duration_days=0, horizon_days=45))
    assert sum(d["volume_mmt"] for d in res.daily_plan) == 0.0


def test_sdp_policy_memo_present():
    res = solve(SDPParams(gap_mbpd=1.0, gap_duration_days=20, horizon_days=60))
    assert isinstance(res.policy_memo, str) and len(res.policy_memo) > 0


def test_option_value_resolving_favours_waiting():
    """A high resolution probability yields positive option value → WAIT."""
    val = option_value_of_waiting(
        p_crisis_resolves=0.55, resolution_days=5.0, refill_cost_premium=0.12,
        gap_mbpd=1.0, price_per_bbl=80.0,
    )
    assert val > 0
    assert "WAIT" in waiting_recommendation(val)


def test_option_value_escalating_favours_drawing():
    """A low resolution probability yields negative option value → DRAW NOW."""
    val = option_value_of_waiting(
        p_crisis_resolves=0.05, resolution_days=5.0, refill_cost_premium=0.12,
        gap_mbpd=1.0, price_per_bbl=80.0,
    )
    assert val < 0
    assert "DRAW NOW" in waiting_recommendation(val)


def test_option_value_zero_gap_is_zero():
    assert option_value_of_waiting(0.5, 5.0, 0.12, gap_mbpd=0.0) == 0.0
