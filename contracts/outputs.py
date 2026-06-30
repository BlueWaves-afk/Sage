"""
C5 — Output episode data models.

Systems 2/3/4 write their numeric results through these models via the SAGE write API.
Rich outputs live in the episode body (for copilot citation) + a validated `data` field.
All outputs carry `scenario_id` so the full chain is retrievable in one graph hop.

Explainability (Weakness 4) is a first-class citizen in this contract:
  - ScenarioOutputData.assumptions: every ARIO parameter labelled and sourced
  - ProcurementOption.score_breakdown: per-dimension TOPSIS scores for XAI radar chart
  - ProcurementOption.rationale: Nova Pro prose, cited to graph episodes
  - SPRScheduleData.policy_memo: Nova Pro memo with constraint satisfaction proof
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Status = Literal["speculative", "confirmed", "counterfactual"]


# ─────────────────────────────────────────────────────────────────────────────
# System 2 — Scenario cascade
# ─────────────────────────────────────────────────────────────────────────────

class ScenarioOutputData(BaseModel):
    """scenario_agent → write_scenario(). ARIO + GNN cascade result."""
    schema_version: str = "1.0.0"
    scenario_id: str
    trigger_entity: str
    status: Status
    confidence: float = Field(..., ge=0, le=1)

    # Core gap metrics
    gap_mbpd: float = Field(..., description="Projected supply gap, million bbl/day")
    gap_duration_days: float
    feedstock_gap_timeline: list[float] = Field(..., description="Per-day refinery feedstock gap, mbpd")

    # Economic cascade
    price_impact_low: float = Field(..., description="USD/bbl, low uncertainty band")
    price_impact_high: float = Field(..., description="USD/bbl, high uncertainty band")
    spr_depletion_days: float = Field(..., description="Days of SPR cover remaining at projected draw rate")
    gdp_proxy_impact_pct: Optional[float] = Field(None, description="GDP-growth hit %, price-driven (NIPFP)")
    inflation_impact_pct: Optional[float] = Field(None, description="CPI inflation rise %, price-driven (NIPFP)")
    sector_impacts: list[dict] = Field(default_factory=list, description=(
        "Reduced-form IO sectoral cascade. Each: {sector, petroleum_share, shortfall_mbpd, "
        "gdp_weight, criticality}. Shows which downstream sectors bear the oil shortage "
        "(transport hit hardest; agriculture food-security-critical)."
    ))

    # Per-node propagation — how the shock spreads through the graph (powers the System 5
    # digital-twin animation: which refinery/port is hit, when, how much).
    node_impacts: list[dict] = Field(default_factory=list, description=(
        "Per-node cascade impact. Each: {node, node_type, exposure, peak_gap_mbpd, "
        "onset_day, gap_timeline}. Distributes the national gap across nodes by exposure "
        "to the disrupted corridor (Jamnagar hit hard, Paradip barely)."
    ))

    # Explainability — every parameter labelled and sourced (judging criterion)
    assumptions: dict = Field(default_factory=dict, description=(
        "Labelled, sourced, editable ARIO parameters. "
        "Keys include the value, unit, and source. Example: "
        "{'import_dependence_pct': {'value': 88.2, 'unit': '%', 'source': 'PPAC 2025'}}. "
        "All assumptions must be explicit — no hidden constants."
    ))
    # Counterfactual tag — links back to the sandbox counterfactual that generated this
    counterfactual_type: Optional[str] = Field(None, description=(
        "If status='counterfactual', one of: 'crisis_resolves_5d', 'brent_below_65', "
        "'russia_export_surge'. Null for confirmed/speculative scenarios."
    ))


# ─────────────────────────────────────────────────────────────────────────────
# System 3 — Procurement
# ─────────────────────────────────────────────────────────────────────────────

class ScoreBreakdown(BaseModel):
    """
    Per-dimension TOPSIS scores for one procurement option.
    Powers the XAI radar chart in System 5. Judges can see exactly why
    Yanbu ranked above Iraq — it is not a black box.
    """
    cost_score: float = Field(..., ge=0, le=1,
        description="Normalised landed cost score; 1=cheapest option")
    lead_time_score: float = Field(..., ge=0, le=1,
        description="Normalised lead time score; 1=fastest option")
    grade_compatibility_score: float = Field(..., ge=0, le=1,
        description="RF+PR-EOS compatibility with target refinery; 1=perfect fit")
    corridor_risk_score: float = Field(..., ge=0, le=1,
        description="Inverse of corridor RISK_STATE score; 1=safest route")
    carbon_score: Optional[float] = Field(None, ge=0, le=1,
        description="Normalised emissions score from voyage distance + vessel efficiency; 1=lowest")
    supplier_reliability_score: Optional[float] = Field(None, ge=0, le=1,
        description="Historical on-time delivery rate for this supplier; 1=most reliable")
    political_stability_score: Optional[float] = Field(None, ge=0, le=1,
        description="Inverse of country political risk index (ICRG/PRS); 1=most stable")
    insurance_premium_score: Optional[float] = Field(None, ge=0, le=1,
        description="Normalised war-risk insurance premium; 1=lowest")

    # TOPSIS weights applied — explicit so judges can challenge them
    weights_used: dict[str, float] = Field(default_factory=lambda: {
        "cost": 0.30, "lead_time": 0.20, "grade_compatibility": 0.20,
        "corridor_risk": 0.15, "carbon": 0.05, "supplier_reliability": 0.05,
        "political_stability": 0.03, "insurance_premium": 0.02,
    })


class ProcurementOption(BaseModel):
    supplier: str
    grade: str
    route_via: str = Field(..., description="Corridor/Port used, e.g. 'Yanbu bypass'")

    # Raw metrics
    landed_cost_usd_bbl: float
    lead_time_days: float
    grade_compatibility: float = Field(..., ge=0, le=1)
    corridor_risk: float = Field(..., ge=0, le=1)
    estimated_carbon_intensity: Optional[float] = Field(None,
        description="kg CO₂e per tonne of crude transported — from voyage distance × vessel emissions factor")
    insurance_premium_usd_bbl: Optional[float] = Field(None,
        description="War-risk insurance premium for this route, USD/bbl")

    # Multi-objective ranking
    topsis_score: float = Field(..., ge=0, le=1, description="Final TOPSIS rank score")
    score_breakdown: Optional[ScoreBreakdown] = Field(None,
        description="Per-dimension scores for XAI radar chart — why this option ranked here")

    # Natural language explanation (cited to Graphiti episodes)
    rationale: str = Field(...,
        description="Nova Pro one-paragraph rationale citing graph episode UUIDs")
    episode_citations: list[str] = Field(default_factory=list,
        description="Graphiti episode UUIDs supporting this rationale")


class ProcurementRecData(BaseModel):
    """alt_procurement_agent → write_procurement(). TOPSIS-ranked alternatives."""
    schema_version: str = "1.0.0"
    scenario_id: str
    status: Status
    target_refinery: Optional[str] = None
    ranked: list[ProcurementOption]


# ─────────────────────────────────────────────────────────────────────────────
# System 4 — SPR
# ─────────────────────────────────────────────────────────────────────────────

class SPRDay(BaseModel):
    day: int
    action: Literal["draw", "hold", "refill"]
    volume_mmt: float
    reserve_after_mmt: float
    days_cover_after: float
    # Explainability: why this action on this day
    decision_driver: Optional[str] = Field(None,
        description="One-line reason for this day's action, e.g. 'price regime stressed, preserve buffer'")


class SPRScheduleData(BaseModel):
    """reserve_optim_agent → write_spr_schedule(). SDP/CMDP drawdown schedule."""
    schema_version: str = "1.0.0"
    scenario_id: str
    status: Status
    daily_plan: list[SPRDay]
    prob_above_buffer: float = Field(..., ge=0, le=1,
        description="P(reserve stays > 3-day buffer) from Monte Carlo over CMDP policy")
    # Constraint satisfaction — explicit for judges
    constraint_satisfied: bool = Field(True,
        description="True if P(reserve < 3 days) ≤ 0.05 (the CMDP chance constraint)")
    lagrange_multiplier: Optional[float] = Field(None,
        description="Lagrange multiplier on the chance constraint — size indicates constraint tightness")
    option_value_of_waiting: Optional[float] = Field(None,
        description="USD/bbl value of delaying drawdown by 5 days under current uncertainty")
    policy_memo: str = Field(...,
        description="Nova Pro policy memo: why this drawdown rate, which replenishment window, buffer probability")
