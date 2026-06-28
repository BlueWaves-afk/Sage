"""
alt_procurement_agent entry point.

Triggered by LangGraph on new ScenarioOutput node.
Reads three Graphiti queries, runs routing + grade + TOPSIS, writes ProcurementRecData.
"""
from __future__ import annotations

from typing import Literal

from contracts.outputs import ProcurementOption, ProcurementRecData
from knowledge.api.read import get_available_suppliers, get_grade_specs, get_routes
from knowledge.api.write import write_procurement

Status = Literal["speculative", "confirmed"]


async def run(scenario_id: str, trigger_refinery: str, status: Status = "confirmed") -> None:
    """Full procurement run. Reads KB, ranks alternatives, writes result."""
    suppliers  = await get_available_suppliers(risk_max=0.4)
    grade_specs = await get_grade_specs(trigger_refinery)
    routes     = await get_routes(risk_max=0.5)

    # TODO: call grade.compatibility_score for each supplier × refinery pair
    # TODO: call routing.solve to get optimal routes
    # TODO: build ProcurementOption list
    # TODO: call rank.rank(options)
    # TODO: for top-3 options, call Nova Pro for rationale

    options: list[ProcurementOption] = []  # TODO: replace with real ranked list

    data = ProcurementRecData(
        scenario_id=scenario_id,
        status=status,
        ranked=options,
    )
    await write_procurement(data)
