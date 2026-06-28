"""
C3 — Edge ontology + edge_type_map.

Passed to graphiti.add_episode(edge_types=..., edge_type_map=...).
("Entity", "Entity") wildcard covers RISK_STATE and AFFECTS_SCENARIO — valid between any node pair.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ExportsVia(BaseModel):
    """Supplier ships crude through this Corridor."""
    volume_mbpd: Optional[float] = Field(None, description="Volume on this lane, million bbl/day")


class Feeds(BaseModel):
    """Corridor feeds traffic into this Port."""


class Supplies(BaseModel):
    """Port supplies crude to this Refinery."""


class ConfiguredFor(BaseModel):
    """Refinery is configured to process this CrudeGrade. Determines grade-compatibility economics."""
    yield_pct: Optional[float] = Field(None, description="Product yield, 0..100 %")
    compatibility: Optional[float] = Field(None, description="Processing compatibility 0..1; 1 = perfect fit")


class SanctionedBy(BaseModel):
    """Vessel or Supplier is sanctioned by this Authority."""
    list_name: Optional[str] = Field(None, description="'OFAC' | 'EU' | 'UN'")
    effective_date: Optional[datetime] = Field(None, description="When the sanction took effect")


class BypassRoute(BaseModel):
    """Alternative routing from Supplier to Port, avoiding a blocked Corridor.
    Yanbu appears here automatically when Hormuz risk_score > 0.7."""
    cost_premium: Optional[float] = Field(None, description="Added landed cost vs primary route, USD/bbl")
    added_days: Optional[float] = Field(None, description="Extra transit days vs primary route")


class FeedsReserve(BaseModel):
    """Refinery draws from or refills this SPRCavern."""


class RiskState(BaseModel):
    """Current fused risk assessment for an entity, with factor breakdown.
    ⭐ The contract the autonomous loop runs on — field names are FROZEN after Day 3 sign-off."""
    score: float = Field(..., description="Fused risk 0..1")
    band: str = Field(..., description="'calm'|'watch'|'elevated'|'action'|'critical' — computed by SAGE at write time")
    factor_ais: float = Field(0.0, description="AIS / dark-vessel contribution 0..1")
    factor_gdelt: float = Field(0.0, description="News / GDELT tone contribution 0..1")
    factor_price: float = Field(0.0, description="Price / war-risk-premium contribution 0..1")
    factor_sanctions: float = Field(0.0, description="Sanctions contribution 0..1")
    rationale: Optional[str] = Field(None, description="One-line driver explanation from sensory_agent fusion")
    model_version: Optional[str] = Field(None, description="Fusion model version that produced this score")


class AffectsScenario(BaseModel):
    """Links any entity to a PendingScenario or ScenarioOutput about it.
    Allows full chain retrieval (signal → scenario → procurement → SPR) in one graph hop."""
    confidence: Optional[float] = Field(None, description="0..1")


EDGE_TYPES: dict[str, type] = {
    "EXPORTS_VIA":      ExportsVia,
    "FEEDS":            Feeds,
    "SUPPLIES":         Supplies,
    "CONFIGURED_FOR":   ConfiguredFor,
    "SANCTIONED_BY":    SanctionedBy,
    "BYPASS_ROUTE":     BypassRoute,
    "FEEDS_RESERVE":    FeedsReserve,
    "RISK_STATE":       RiskState,
    "AFFECTS_SCENARIO": AffectsScenario,
}

EDGE_TYPE_MAP: dict[tuple[str, str], list[str]] = {
    ("Supplier",  "Corridor"):   ["EXPORTS_VIA"],
    ("Corridor",  "Port"):       ["FEEDS"],
    ("Port",      "Refinery"):   ["SUPPLIES"],
    ("Refinery",  "CrudeGrade"): ["CONFIGURED_FOR"],
    ("Vessel",    "Authority"):  ["SANCTIONED_BY"],
    ("Supplier",  "Authority"):  ["SANCTIONED_BY"],
    ("Supplier",  "Port"):       ["BYPASS_ROUTE"],
    ("Refinery",  "SPRCavern"):  ["FEEDS_RESERVE"],
    # wildcard — RISK_STATE and AFFECTS_SCENARIO attach to any node type
    ("Entity",    "Entity"):     ["RISK_STATE", "AFFECTS_SCENARIO"],
}
