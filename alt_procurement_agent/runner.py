"""
System 3 — Adaptive Procurement Orchestrator.

Triggered in parallel with System 4 by a new ScenarioOutput.
  1. Reads non-sanctioned suppliers (risk < 0.4) from KB
  2. Reads refinery's configured grade specs
  3. Reads open corridors (risk < 0.5) + bypass edges from bundle
  4. Scores grade compatibility for each supplier × spec
  5. Routes each supplier to minimum-cost open corridor
  6. Builds ProcurementOption list, applies TOPSIS ranking
  7. Nova Pro writes one-paragraph rationale for top-3 options
  8. Writes ProcurementRecData to KB (episode + wiki)
"""
from __future__ import annotations

import logging
import os
from typing import Literal

from contracts.outputs import ProcurementOption, ProcurementRecData
from knowledge.api.read import get_available_suppliers, get_grade_specs, get_routes
from knowledge.api.write import write_procurement

from alt_procurement_agent.grade import best_compatibility
from alt_procurement_agent.routing import solve as solve_routes
from alt_procurement_agent.rank import rank as topsis_rank

log = logging.getLogger(__name__)

Status = Literal["speculative", "confirmed"]

# Grade specs for suppliers not in CONFIGURED_FOR edges — lookup by country.
# Source: crude_grades.csv (api_gravity / sulfur_pct from real assays).
_SUPPLIER_GRADE: dict[str, tuple[float, float]] = {
    "Saudi Arabia":         (32.8, 1.96),   # Arab Light representative
    "Iraq":                 (27.9, 3.00),   # Basrah Medium
    "United Arab Emirates": (40.2, 0.79),   # Murban
    "Kuwait":               (31.0, 2.55),   # Kuwait Export Crude
    "Qatar":                (36.0, 1.40),   # Qatar Marine
    "Russia":               (31.3, 1.30),   # Urals
    "Nigeria":              (38.0, 0.37),   # Bonny Light
    "United States":        (40.0, 0.40),   # WTI Midland
    "Brazil":               (29.0, 0.40),   # Tupi
    "Venezuela":            (16.0, 2.50),   # Merey (heavy sour)
    "Kazakhstan":           (45.0, 0.55),   # CPC Blend
    "Angola":               (32.0, 0.13),   # Cabinda
}

# Bypass edges (from bundle facts/edges/bypass_routes.csv)
# Added_days and cost_premium from IEA/Petroline sources.
_BYPASS_EDGES = [
    {"src": "Saudi Aramco", "via_corridor": "Suez Canal",        "cost_premium": 2.50, "added_days": 10.0},
    {"src": "ADNOC",         "via_corridor": "Cape of Good Hope", "cost_premium": 1.20, "added_days": 2.0},
]


async def run(
    scenario_id: str,
    trigger_refinery: str,
    status: Status = "confirmed",
    gap_mbpd: float = 0.5,
) -> str:
    """
    Full procurement run. Returns scenario_id on completion.
    `gap_mbpd` from ScenarioOutputData scopes how much volume to source.
    """
    suppliers  = await get_available_suppliers(risk_max=0.4)
    grade_specs = await get_grade_specs(trigger_refinery)
    corridors  = await get_routes(risk_max=0.5)

    if not suppliers:
        log.warning("[procurement] no non-sanctioned suppliers returned from KB")

    # Route each supplier to their best open corridor
    routes = solve_routes(suppliers, corridors, _BYPASS_EDGES, risk_max=0.5)

    options: list[ProcurementOption] = []
    for supplier in suppliers:
        route = routes.get(supplier.display_name)
        if route is None:
            continue  # all routes blocked for this supplier

        country = supplier.country or ""
        api, sulfur = _SUPPLIER_GRADE.get(country, (32.0, 1.8))
        compat = best_compatibility(api, sulfur, grade_specs)

        options.append(ProcurementOption(
            supplier=supplier.display_name,
            grade=_grade_name(country),
            route_via=route.corridor,
            landed_cost_usd_bbl=route.landed_cost_usd_bbl,
            lead_time_days=route.lead_time_days,
            grade_compatibility=compat,
            corridor_risk=route.corridor_risk,
            topsis_score=0.0,      # populated by topsis_rank
            rationale="",          # populated below for top-3
            episode_citations=[],
        ))

    ranked = topsis_rank(options)

    # Nova Pro rationale for top-3 (best-effort — doesn't block the write)
    for opt in ranked[:3]:
        opt.rationale = await _nova_rationale(opt, trigger_refinery, gap_mbpd)

    # Minimal rationale for the rest
    for opt in ranked[3:]:
        opt.rationale = (
            f"{opt.supplier} ({opt.grade}) via {opt.route_via}: "
            f"TOPSIS {opt.topsis_score:.2f}, cost ${opt.landed_cost_usd_bbl:.2f}/bbl, "
            f"{opt.lead_time_days:.0f}d lead, compatibility {opt.grade_compatibility:.2f}."
        )

    data = ProcurementRecData(
        scenario_id=scenario_id,
        status=status,
        target_refinery=trigger_refinery,
        ranked=ranked,
    )
    await write_procurement(data)
    log.info("[procurement] wrote %d ranked options for %s (scenario %s)",
             len(ranked), trigger_refinery, scenario_id)
    return scenario_id


async def _nova_rationale(opt: ProcurementOption, refinery: str, gap_mbpd: float) -> str:
    try:
        from knowledge.synthesis import _call_nova_pro
        prompt = (
            f"You are SAGE's procurement analyst. Write ONE concise paragraph (4-6 sentences) "
            f"explaining why {opt.supplier} ({opt.grade}) routed via {opt.route_via} "
            f"is a strong option to bridge a {gap_mbpd:.2f} mbpd supply gap at {refinery}.\n"
            f"TOPSIS score: {opt.topsis_score:.2f}. "
            f"Landed cost: ${opt.landed_cost_usd_bbl:.2f}/bbl. "
            f"Lead time: {opt.lead_time_days:.0f} days. "
            f"Grade compatibility: {opt.grade_compatibility:.2f}/1.0. "
            f"Corridor risk: {opt.corridor_risk:.2f}/1.0. "
            f"Score breakdown: {opt.score_breakdown}.\n"
            f"Be specific about the grade's processing characteristics, the route's risk profile, "
            f"and any trade-offs (e.g. longer lead time offset by lower cost, or high compatibility "
            f"offsetting a slightly elevated corridor risk). Do not use bullet points."
        )
        return await _call_nova_pro(prompt, opt.supplier)
    except Exception as exc:
        log.warning("[procurement] Nova Pro rationale failed for %s: %s", opt.supplier, exc)
        return (
            f"{opt.supplier} ({opt.grade}) via {opt.route_via}: "
            f"TOPSIS {opt.topsis_score:.2f}, cost ${opt.landed_cost_usd_bbl:.2f}/bbl, "
            f"{opt.lead_time_days:.0f}d lead time, compatibility {opt.grade_compatibility:.2f}."
        )


def _grade_name(country: str) -> str:
    return {
        "Saudi Arabia":         "Arab Light",
        "Iraq":                 "Basrah Medium",
        "United Arab Emirates": "Murban",
        "Kuwait":               "Kuwait Export Crude",
        "Qatar":                "Qatar Marine",
        "Russia":               "Urals",
        "Nigeria":              "Bonny Light",
        "United States":        "WTI Midland",
        "Brazil":               "Tupi",
        "Venezuela":            "Merey",
        "Kazakhstan":           "CPC Blend",
        "Angola":               "Cabinda",
    }.get(country, "Unknown Grade")
