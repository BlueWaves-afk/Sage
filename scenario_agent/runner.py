"""
scenario_agent entry point.

Triggered by LangGraph (Path A: sandbox, Path B: confirmed threshold crossing).
Reads subgraph, runs ARIO cascade, optionally runs GNN surrogate, writes result.
"""
from __future__ import annotations

import uuid
from typing import Literal

from contracts.outputs import ScenarioOutputData
from knowledge.api.read import get_subgraph
from knowledge.api.write import write_scenario
from scenario_agent.ario import ARIOParams, run as run_ario

Status = Literal["speculative", "confirmed"]


async def run(trigger_entity: str, status: Status = "confirmed") -> str:
    """
    Full scenario run. Returns scenario_id.
    Uses ARIO for confirmed scenarios; GNN surrogate for speculative (sandbox) runs.
    """
    scenario_id = f"scenario-{uuid.uuid4().hex[:8]}"
    subgraph = await get_subgraph(trigger_entity, hops=2)

    if status == "speculative":
        result = await _run_gnn(subgraph)
    else:
        params = _extract_ario_params(subgraph)
        result = run_ario(params)

    data = ScenarioOutputData(
        scenario_id=scenario_id,
        trigger_entity=trigger_entity,
        status=status,
        confidence=1.0 if status == "confirmed" else 0.0,  # TODO: real confidence
        gap_mbpd=0.0,              # TODO: from result
        gap_duration_days=0.0,
        feedstock_gap_timeline=result.feedstock_gap_timeline,
        price_impact_low=result.price_impact_low,
        price_impact_high=result.price_impact_high,
        spr_depletion_days=result.spr_depletion_days,
        gdp_proxy_impact_pct=result.gdp_proxy_impact_pct,
        assumptions=result.assumptions,
    )
    await write_scenario(data)
    return scenario_id


def _extract_ario_params(subgraph: object) -> ARIOParams:
    """Build ARIO params from live subgraph node properties. Stub."""
    # TODO: read inventory_days, throughput_mbpd from subgraph nodes
    return ARIOParams()


async def _run_gnn(subgraph: object) -> object:
    """Run GNN surrogate for sandbox speed. Stub."""
    # TODO: load CascadeGNN from checkpoint, run forward()
    return type("R", (), {"feedstock_gap_timeline": [], "price_impact_low": 0,
                          "price_impact_high": 0, "spr_depletion_days": 0,
                          "gdp_proxy_impact_pct": 0, "assumptions": {}})()
