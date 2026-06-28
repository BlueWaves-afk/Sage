"""
SDP / CMDP solver for SPR drawdown optimisation.

State space: (reserve_level, market_regime, price, day_in_crisis)
Low-dimensional — exact Bellman iteration is tractable (no GNN-MCTS needed).

CMDP: maximise expected utility subject to P(reserve < 3 days) ≤ 0.05.
Lagrangian relaxation of chance constraint — auditable, explainable, validated
in SPR economics literature.

India SPR facts (ISPRL):
  Vizag:     1.33 MMT
  Mangaluru: 1.50 MMT
  Padur:     2.50 MMT
  Total:     5.33 MMT (~9.5 days cover at ~0.56 MMT/day consumption)
"""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field


@dataclass
class SDPParams:
    spr_initial_mmt: float = 5.33       # MMT at crisis start
    daily_consumption_mmt: float = 0.56  # MMT/day India crude consumption
    gap_mbpd: float = 0.0               # supply gap from scenario_agent
    gap_duration_days: int = 30
    price_per_bbl: float = 80.0         # current Brent
    buffer_threshold_days: float = 3.0  # P(reserve < this) ≤ 0.05
    horizon_days: int = 90


@dataclass
class SDPResult:
    daily_plan: list[dict] = field(default_factory=list)   # {day, action, volume_mmt, reserve_after_mmt, days_cover}
    prob_above_buffer: float = 0.0
    policy_memo: str = ""


def solve(params: SDPParams) -> SDPResult:
    """
    Bellman iteration over (reserve × regime × price × day) state space.
    Returns optimal drawdown schedule and P(buffer maintained).
    Stub — implement in Week 2.
    """
    # TODO: define state grid (reserve_levels × regimes × prices × days)
    # TODO: define value function V[state] and policy pi[state]
    # TODO: backward induction: V[T] = terminal, V[t] = max_action { reward + E[V[t+1]] }
    # TODO: apply CMDP Lagrangian: penalise P(reserve < buffer_threshold_days) in reward
    # TODO: forward pass to extract daily_plan from pi
    # TODO: Monte Carlo estimate of prob_above_buffer
    return SDPResult()
