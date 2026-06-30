"""
scenario_agent entry point.

Triggered by LangGraph (Path A: sandbox/speculative, Path B: confirmed threshold crossing).
Reads the supply-chain subgraph + SPR state from the KB, runs the ARIO cascade
(Monte-Carlo for bands), and writes a ScenarioOutputData back to the KB.

See .claude/design/system2_design.md.
"""
from __future__ import annotations

import uuid
from typing import Literal, Optional

from contracts.outputs import ScenarioOutputData
from knowledge.api.read import get_subgraph, get_spr_state
from knowledge.api.write import write_scenario
from scenario_agent.ario import ARIOParams, run as run_ario, run_monte_carlo

Status = Literal["speculative", "confirmed"]


async def run(
    trigger_entity: str,
    status: Status = "confirmed",
    disruption_fraction: float = 1.0,
    disruption_days: int = 30,
) -> str:
    """
    Full scenario run. Returns scenario_id.
    Confirmed → full ARIO + Monte-Carlo bands. Speculative → GNN surrogate (sandbox speed).
    """
    scenario_id = f"scenario-{uuid.uuid4().hex[:8]}"
    subgraph = await get_subgraph(trigger_entity, hops=2)
    spr      = await get_spr_state()

    params     = await _extract_ario_params(subgraph, spr, disruption_fraction, disruption_days)
    refineries = _extract_refineries(subgraph, trigger_entity)
    sectors    = _bundle_sectors()

    if status == "speculative":
        result, bands = await _run_gnn(subgraph, params), None
    else:
        result = run_ario(params, refineries, sectors)
        bands  = run_monte_carlo(params, n=300)

    # Dynamic war-risk premium (System 1): live fear/insurance premium on top of the
    # structural elasticity. 0 until System 1 produces price signals.
    premium = await _war_risk_premium(trigger_entity)
    if premium > 0:
        result.price_impact_low  = round(result.price_impact_low  * (1 + premium), 2)
        result.price_impact_high = round(result.price_impact_high * (1 + premium), 2)

    assumptions = dict(result.assumptions)
    if bands:
        assumptions["monte_carlo"] = bands   # p10/p50/p90 ranges for the UI uncertainty bands
    if premium > 0:
        assumptions["war_risk_premium"] = {"value": round(premium, 3), "unit": "frac", "source": "System 1 live price factor"}

    node_impacts = [
        {"node": n.node, "node_type": n.node_type, "exposure": n.exposure,
         "peak_gap_mbpd": n.peak_gap_mbpd, "onset_day": n.onset_day, "gap_timeline": n.gap_timeline}
        for n in result.node_impacts
    ]
    sector_impacts = [
        {"sector": s.sector, "petroleum_share": s.petroleum_share, "shortfall_mbpd": s.shortfall_mbpd,
         "gdp_weight": s.gdp_weight, "criticality": s.criticality}
        for s in result.sector_impacts
    ]

    data = ScenarioOutputData(
        scenario_id=scenario_id,
        trigger_entity=trigger_entity,
        status=status,
        confidence=1.0 if status == "confirmed" else 0.6,
        gap_mbpd=result.gap_mbpd,
        gap_duration_days=result.gap_duration_days,
        feedstock_gap_timeline=result.feedstock_gap_timeline,
        price_impact_low=result.price_impact_low,
        price_impact_high=result.price_impact_high,
        spr_depletion_days=result.spr_depletion_days,
        gdp_proxy_impact_pct=result.gdp_proxy_impact_pct,
        inflation_impact_pct=result.inflation_impact_pct,
        node_impacts=node_impacts,
        sector_impacts=sector_impacts,
        assumptions=assumptions,
    )
    await write_scenario(data)
    return scenario_id


import os

_PARAM_CACHE: dict | None = None


_SECTOR_CACHE: list | None = None


def _load_bundle():
    from knowledge.context import load_bundle
    return load_bundle(os.environ.get("SAGE_CONTEXT_BUNDLE", "data/india-energy-2026.context"))


def _bundle_params() -> dict:
    """Load the ARIO economic coefficients from the context bundle (sourced, cached)."""
    global _PARAM_CACHE
    if _PARAM_CACHE is None:
        try:
            _PARAM_CACHE = {k: float(v["value"]) for k, v in _load_bundle().model_params.items()}
        except Exception:
            _PARAM_CACHE = {}
    return _PARAM_CACHE


def _bundle_sectors() -> list[dict]:
    """Load the economic sectors (IO cascade) from the bundle, cached."""
    global _SECTOR_CACHE
    if _SECTOR_CACHE is None:
        try:
            _SECTOR_CACHE = _load_bundle().sectors
        except Exception:
            _SECTOR_CACHE = []
    return _SECTOR_CACHE


async def _extract_ario_params(
    subgraph, spr_caverns, disruption_fraction: float, disruption_days: int,
) -> ARIOParams:
    """
    Build ARIO params from (1) the sourced bundle params, (2) live KB state (SPR fill,
    refinery inventory), (3) the scenario inputs. No hardcoded economic constants —
    every coefficient is provenance-tracked in data/<bundle>.context/params/.
    """
    p = ARIOParams(disruption_fraction=disruption_fraction, disruption_days=disruption_days)

    # (1) Override defaults with the sourced bundle coefficients.
    for k, v in _bundle_params().items():
        if hasattr(p, k):
            setattr(p, k, v)

    # SPR fill from live cavern state
    total_cap  = sum((c.capacity_mmt or 0.0) for c in spr_caverns)
    total_fill = sum((c.current_fill_mmt or 0.0) for c in spr_caverns)
    if total_cap > 0:
        p.spr_total_mmt = round(total_cap, 3)
        p.spr_fill_frac = round(total_fill / total_cap, 3)

    # Average refinery crude inventory from the subgraph
    inv = [
        float(n["attributes"]["inventory_days"])
        for n in subgraph.nodes
        if "Refinery" in (n.get("labels") or []) and n["attributes"].get("inventory_days")
    ]
    if inv:
        p.refinery_inventory_days = round(sum(inv) / len(inv), 1)

    return p


def _extract_refineries(subgraph, trigger_entity: str) -> list[dict]:
    """
    Build [{name, capacity_mbpd, exposure}] for refineries in the subgraph, where
    exposure = the EXPOSES edge weight from the disrupted corridor (materialised at
    ingestion). Refineries with no EXPOSES edge to the trigger corridor get exposure 0.
    """
    # uuid → name, and refinery capacities
    name_by_uuid, cap_by_name = {}, {}
    for n in subgraph.nodes:
        name_by_uuid[n.get("uuid")] = n.get("display_name")
        if "Refinery" in (n.get("labels") or []):
            cap_by_name[n.get("display_name")] = float(n["attributes"].get("capacity_mbpd") or 0)

    # EXPOSES edges from the trigger corridor → refinery
    exposure_by_name: dict[str, float] = {}
    for e in subgraph.edges:
        if e.get("relation_type") != "EXPOSES":
            continue
        src = name_by_uuid.get(e.get("source_uuid"))
        dst = name_by_uuid.get(e.get("target_uuid"))
        if src == trigger_entity and dst in cap_by_name:
            exposure_by_name[dst] = max(exposure_by_name.get(dst, 0.0),
                                        float(e.get("attributes", {}).get("exposure_pct") or 0))

    return [
        {"name": name, "capacity_mbpd": cap, "exposure": exposure_by_name.get(name, 0.0)}
        for name, cap in cap_by_name.items()
    ]


async def _war_risk_premium(trigger_entity: str) -> float:
    """Live war-risk premium for the corridor (System 1 price factor), 0 if none yet."""
    try:
        from knowledge.api.read import get_risk_scores
        scores = await get_risk_scores()
        hit = next((s for s in scores if s.entity == trigger_entity), None)
        return float(hit.factors.get("price", 0.0)) if hit else 0.0
    except Exception:
        return 0.0


async def _run_gnn(subgraph, params: ARIOParams):
    """
    GNN surrogate for sandbox speed (<150ms). Falls back to ARIO until the model
    is trained (gnn/train.py). Stub returns the analytic ARIO result for now.
    """
    # TODO: load CascadeGNN from checkpoint, run forward() on subgraph features
    return run_ario(params)
