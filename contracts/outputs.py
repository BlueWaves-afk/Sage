"""
C5 — Output episode data models.

Systems 2/3/4 write their numeric results through these models via the SAGE write API.
Rich outputs live in the episode body (for copilot citation) + a validated `data` field.
All outputs carry `scenario_id` so the full chain is retrievable in one graph hop.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Status = Literal["speculative", "confirmed"]


class ScenarioOutputData(BaseModel):
    """scenario_agent → write_scenario(). ARIO + GNN cascade result."""
    schema_version: str = "1.0.0"
    scenario_id: str
    trigger_entity: str
    status: Status
    confidence: float = Field(..., ge=0, le=1)
    gap_mbpd: float = Field(..., description="Projected supply gap, million bbl/day")
    gap_duration_days: float
    feedstock_gap_timeline: list[float] = Field(..., description="Per-day refinery feedstock gap, mbpd")
    price_impact_low: float = Field(..., description="USD/bbl, low uncertainty band")
    price_impact_high: float = Field(..., description="USD/bbl, high uncertainty band")
    spr_depletion_days: float = Field(..., description="Days of SPR cover remaining at projected draw rate")
    gdp_proxy_impact_pct: Optional[float] = None
    assumptions: dict = Field(default_factory=dict, description="Labelled, sourced, editable ARIO parameters")


class ProcurementOption(BaseModel):
    supplier: str
    grade: str
    route_via: str = Field(..., description="Corridor/Port used, e.g. 'Yanbu bypass'")
    landed_cost_usd_bbl: float
    lead_time_days: float
    grade_compatibility: float = Field(..., ge=0, le=1)
    corridor_risk: float = Field(..., ge=0, le=1)
    topsis_score: float = Field(..., ge=0, le=1, description="Multi-objective rank score")
    rationale: str = Field(..., description="Nova Pro one-paragraph rationale, cited to graph sources")


class ProcurementRecData(BaseModel):
    """alt_procurement_agent → write_procurement(). TOPSIS-ranked alternatives."""
    schema_version: str = "1.0.0"
    scenario_id: str
    status: Status
    ranked: list[ProcurementOption]


class SPRDay(BaseModel):
    day: int
    action: Literal["draw", "hold", "refill"]
    volume_mmt: float
    reserve_after_mmt: float
    days_cover_after: float


class SPRScheduleData(BaseModel):
    """reserve_optim_agent → write_spr_schedule(). SDP/CMDP drawdown schedule."""
    schema_version: str = "1.0.0"
    scenario_id: str
    status: Status
    daily_plan: list[SPRDay]
    prob_above_buffer: float = Field(..., ge=0, le=1, description="P(reserve stays > 3-day buffer)")
    policy_memo: str = Field(..., description="Nova Pro policy rationale memo")
