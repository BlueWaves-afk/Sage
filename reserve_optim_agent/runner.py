"""
System 4 — Strategic Reserve Optimisation Agent.

Triggered in parallel with System 3 by a new ScenarioOutput.
  1. Reads live SPR cavern fill levels from KB
  2. Infers crisis-resolution probability from scenario escalation_profile
  3. Computes real-options value of waiting (before committing to drawdown)
  4. Runs SDP/CMDP Bellman solver → optimal day-by-day drawdown schedule
  5. Nova Pro generates policy memo (why this rate, which replenishment window, buffer prob)
  6. Writes SPRScheduleData to KB (episode + wiki reconciliation via write_spr_schedule)
"""
from __future__ import annotations

import logging
from typing import Literal

from contracts.outputs import SPRDay, SPRScheduleData
from knowledge.api.read import get_spr_state
from knowledge.api.write import write_spr_schedule
from reserve_optim_agent.sdp import SDPParams, SDPResult, solve
from reserve_optim_agent.options import option_value_of_waiting, waiting_recommendation

log = logging.getLogger(__name__)

Status = Literal["speculative", "confirmed"]

# Regime → P(crisis resolves in the next 5 days).
# Calibrated from IEA historical crisis resolution data.
_RESOLVE_PROB: dict[str, float] = {
    "resolving":  0.55,   # escalation_profile=resolving → high resolve prob
    "constant":   0.20,
    "escalating": 0.05,
}


async def run(
    scenario_id: str,
    gap_mbpd: float,
    gap_duration_days: int,
    status: Status = "confirmed",
    escalation_profile: str = "constant",
    price_per_bbl: float = 80.0,
) -> str:
    """
    Full SPR optimisation run. Returns scenario_id on completion.

    `escalation_profile` from the LLM-decided scenario shapes the real-options
    calculation: a resolving crisis → stronger case for waiting before drawing.
    """
    caverns         = await get_spr_state()
    total_fill_mmt  = sum(c.current_fill_mmt or 0.0 for c in caverns)
    total_cap_mmt   = sum(c.capacity_mmt     or 0.0 for c in caverns)
    fill_frac       = total_fill_mmt / total_cap_mmt if total_cap_mmt > 0 else 0.4

    log.info("[spr] SPR fill: %.2f MMT / %.2f MMT (%.0f%%)",
             total_fill_mmt, total_cap_mmt, fill_frac * 100)

    # Real-options valuation first — influences SDP horizon framing.
    p_resolve  = _RESOLVE_PROB.get(escalation_profile, 0.20)
    opt_val    = option_value_of_waiting(
        p_crisis_resolves      = p_resolve,
        resolution_days        = 5.0,
        refill_cost_premium    = 0.12,
        gap_mbpd               = gap_mbpd,
        price_per_bbl          = price_per_bbl,
    )
    wait_rec = waiting_recommendation(opt_val)
    log.info("[spr] real-options: opt_val=%.2f — %s", opt_val, wait_rec)

    # SDP/CMDP: solve for optimal day-by-day schedule
    params = SDPParams(
        spr_initial_mmt       = total_fill_mmt,
        gap_mbpd              = gap_mbpd,
        gap_duration_days     = gap_duration_days,
        price_per_bbl         = price_per_bbl,
        horizon_days          = max(gap_duration_days + 30, 60),
    )
    result: SDPResult = solve(params)

    # Nova Pro policy memo (augments the SDP auto-memo with narrative judgment)
    policy_memo = await _nova_memo(result, params, opt_val, wait_rec, escalation_profile)

    # Convert to contract type
    daily_plan = [
        SPRDay(
            day=d["day"],
            action=d["action"],
            volume_mmt=d["volume_mmt"],
            reserve_after_mmt=d["reserve_after_mmt"],
            days_cover_after=d["days_cover"],
            decision_driver=d.get("decision_driver"),
        )
        for d in result.daily_plan
    ]

    data = SPRScheduleData(
        scenario_id=scenario_id,
        status=status,
        daily_plan=daily_plan,
        prob_above_buffer=result.prob_above_buffer,
        constraint_satisfied=result.constraint_satisfied,
        lagrange_multiplier=result.lagrange_multiplier,
        option_value_of_waiting=opt_val,
        policy_memo=policy_memo,
    )
    await write_spr_schedule(data)
    log.info("[spr] wrote SPR schedule: %d days, P(buffer)=%.1%%",
             len(daily_plan), result.prob_above_buffer * 100)
    return scenario_id


async def _nova_memo(
    result: SDPResult,
    params: SDPParams,
    opt_val: float,
    wait_rec: str,
    profile: str,
) -> str:
    try:
        from knowledge.synthesis import _call_nova_pro
        total_draw  = sum(d["volume_mmt"] for d in result.daily_plan)
        peak_unmet  = max((d["unmet_mmt"] for d in result.daily_plan), default=0.0)
        draw_days   = sum(1 for d in result.daily_plan if d["action"] == "draw")

        prompt = (
            f"You are SAGE's SPR policy analyst. Write a concise policy memo (5-7 sentences) "
            f"for India's Strategic Petroleum Reserve drawdown.\n\n"
            f"Situation: {params.gap_mbpd:.2f} mbpd supply gap for {params.gap_duration_days} days "
            f"(escalation profile: {profile}). Current SPR: {params.spr_initial_mmt:.2f} MMT "
            f"(3-day buffer floor: {params.buffer_threshold_days:.2f} MMT).\n\n"
            f"Optimal policy computed (SDP/CMDP):\n"
            f"- Draw over {draw_days} of {params.horizon_days} days, total {total_draw:.3f} MMT\n"
            f"- Peak unmet demand: {peak_unmet:.4f} MMT/day\n"
            f"- P(reserve > 3-day buffer): {result.prob_above_buffer:.1%} "
            f"({'constraint satisfied' if result.constraint_satisfied else 'VIOLATED'})\n"
            f"- Lagrange multiplier (constraint tightness): {result.lagrange_multiplier:.2f}\n\n"
            f"Real-options valuation: {wait_rec}\n\n"
            f"Address: (1) recommended drawdown rate and timing, (2) buffer maintenance, "
            f"(3) replenishment window after crisis resolves, (4) key risk to the plan. "
            f"Cite the IEA 90-day norm where relevant. No bullet points."
        )
        return await _call_nova_pro(prompt, "India SPR")
    except Exception as exc:
        log.warning("[spr] Nova Pro memo failed: %s — using SDP auto-memo", exc)
        return result.policy_memo
