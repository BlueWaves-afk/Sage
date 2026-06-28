"""
C7 — Read API. Typed wrappers over Graphiti search.

Every reader returns a typed *View Pydantic model — never a raw Graphiti EntityNode/EntityEdge.
Consumers depend on the View shape, insulating them from Graphiti internal changes.
Stubs — implement bodies in Week 2.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class RiskScoreView(BaseModel):
    """C4 canonical shape — matches §6.2 of the schema spec."""
    schema_version: str = "1.0.0"
    entity: str
    entity_uuid: str
    score: float
    band: str
    factors: dict[str, float]   # {"ais": .., "gdelt": .., "price": .., "sanctions": ..}
    rationale: Optional[str] = None
    model_version: Optional[str] = None
    valid_at: str       # ISO8601
    recorded_at: str    # ISO8601


class SubgraphView(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


class SupplierView(BaseModel):
    entity_uuid: str
    display_name: str
    country: Optional[str]
    daily_export_mbpd: Optional[float]
    risk_score: Optional[float]


class GradeSpecView(BaseModel):
    refinery: str
    grade: str
    api_gravity: Optional[float]
    sulfur_pct: Optional[float]
    yield_pct: Optional[float]
    compatibility: Optional[float]


class CorridorView(BaseModel):
    entity_uuid: str
    display_name: str
    risk_score: Optional[float]
    throughput_mbpd: Optional[float]
    h3_cells: list[str]


class SPRCavernView(BaseModel):
    entity_uuid: str
    display_name: str
    location: Optional[str]
    capacity_mmt: Optional[float]
    current_fill_mmt: Optional[float]


class WikiPage(BaseModel):
    entity: str
    content: str    # Markdown prose from /wiki store
    last_updated: Optional[str] = None


class CopilotAnswer(BaseModel):
    answer: str
    citations: list[str]    # Graphiti episode UUIDs
    route: str              # "vector" | "graph" — which EA-GraphRAG path was used
    latency_ms: Optional[float] = None


async def get_subgraph(entity: str, hops: int = 2) -> SubgraphView:
    """scenario_agent calls this to initialise a cascade. Returns connected nodes + properties."""
    raise NotImplementedError


async def get_available_suppliers(risk_max: float = 0.4) -> list[SupplierView]:
    """alt_procurement_agent. Returns suppliers with risk_score < risk_max AND not sanctioned."""
    raise NotImplementedError


async def get_grade_specs(refinery: str) -> list[GradeSpecView]:
    """alt_procurement_agent. Returns CONFIGURED_FOR edges + crude specs for a refinery."""
    raise NotImplementedError


async def get_routes(risk_max: float = 0.5) -> list[CorridorView]:
    """alt_procurement_agent. Returns corridors with risk_score below threshold."""
    raise NotImplementedError


async def get_spr_state() -> list[SPRCavernView]:
    """reserve_optim_agent. Returns all SPRCavern fill levels (Vizag, Mangaluru, Padur)."""
    raise NotImplementedError


async def get_risk_scores() -> list[RiskScoreView]:
    """LangGraph monitor + visualizer_agent. Returns all current RISK_STATE edges."""
    raise NotImplementedError


async def copilot_query(q: str) -> CopilotAnswer:
    """visualizer_agent copilot. EA-GraphRAG routed: simple → BM25+vector, complex → HippoRAG2 PPR."""
    raise NotImplementedError


async def get_wiki_page(entity: str) -> WikiPage:
    """visualizer_agent. Returns narrative synthesis page for a node click — retrieved, never generated."""
    raise NotImplementedError
