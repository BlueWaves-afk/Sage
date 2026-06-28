"""
reserve_optim_agent entry point.

Triggered in parallel with alt_procurement_agent by the same ScenarioOutput node.
Reads SPR state from KB, runs SDP/CMDP, generates policy memo via Nova Pro, writes result.
"""
from __future__ import annotations

from typing import Literal

from contracts.outputs import SPRDay, SPRScheduleData
from knowledge.api.read import get_spr_state
from knowledge.api.write import write_spr_schedule
from reserve_optim_agent.sdp import SDPParams, solve

Status = Literal["speculative", "confirmed"]


async def run(
    scenario_id: str,
    gap_mbpd: float,
    gap_duration_days: int,
    status: Status = "confirmed",
) -> None:
    """Full SPR optimisation run. Reads KB, solves SDP/CMDP, writes schedule."""
    caverns = await get_spr_state()
    total_fill_mmt = sum(c.current_fill_mmt or 0 for c in caverns)

    params = SDPParams(
        spr_initial_mmt=total_fill_mmt,
        gap_mbpd=gap_mbpd,
        gap_duration_days=gap_duration_days,
    )
    result = solve(params)

    daily_plan = [
        SPRDay(
            day=d["day"],
            action=d["action"],
            volume_mmt=d["volume_mmt"],
            reserve_after_mmt=d["reserve_after_mmt"],
            days_cover_after=d["days_cover"],
        )
        for d in result.daily_plan
    ]

    # TODO: call Nova Pro to generate policy_memo from result
    policy_memo = result.policy_memo or "[STUB] Policy memo — implement Nova Pro call in Week 2."

    data = SPRScheduleData(
        scenario_id=scenario_id,
        status=status,
        daily_plan=daily_plan,
        prob_above_buffer=result.prob_above_buffer,
        policy_memo=policy_memo,
    )
    await write_spr_schedule(data)
