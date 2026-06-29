"""
C7 — Read API. Typed wrappers over Graphiti search + FalkorDB Cypher.

IMPORT BOUNDARY: agents import from here only. None of them touch graphiti_core directly.

Two query strategies:
  1. Semantic (graphiti.search) — copilot_query(), get_subgraph(), supplier filtering.
     Returns EntityEdge objects; we parse .fact and .attributes for structured data.

  2. Structural (Cypher via graphiti._driver) — get_risk_scores(), get_spr_state(),
     get_available_suppliers() exact filter. Graphiti stores nodes and edges in FalkorDB
     as labelled property graph; Cypher gives exact, deterministic results.

Cypher schema (as written by Graphiti ≥ 0.17 into FalkorDB):
  Nodes: (:Entity {uuid, name, group_id, labels, created_at, summary, ...custom_attrs})
  Edges: (:Entity)-[:EDGE_TYPE {uuid, fact, valid_at, invalid_at, created_at,
                                source_node_uuid, target_node_uuid, ...custom_attrs}]->(:Entity)

  The entity type label is also stored in `labels` property as a list,
  and as a node label (Graphiti sets both).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel

# EpisodeRef is the canonical return type — import from write to avoid duplication
from knowledge.api.write import EpisodeRef  # noqa: F401 — re-exported for consumers

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# View models (C7 return types — immutable, never raw Graphiti internals)
# ---------------------------------------------------------------------------

class RiskScoreView(BaseModel):
    """C4 canonical shape — matches §6.2 of the schema spec."""
    schema_version: str = "1.0.0"
    entity: str
    entity_uuid: str
    score: float
    band: str
    factors: dict[str, float]
    rationale: Optional[str] = None
    model_version: Optional[str] = None
    valid_at: str
    recorded_at: str


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
    content: str
    last_updated: Optional[str] = None


class CopilotAnswer(BaseModel):
    answer: str
    citations: list[str]
    route: str   # "vector" | "graph" | "hybrid"
    latency_ms: Optional[float] = None


# ---------------------------------------------------------------------------
# Cypher execution helper
# ---------------------------------------------------------------------------

async def _cypher(query: str, params: Optional[dict] = None) -> list[dict[str, Any]]:
    """
    Execute a Cypher query against FalkorDB via the Graphiti driver.

    Graphiti's FalkorDriver exposes execute_query() which returns a list of
    result records. Each record is a dict mapping return variable names to values.
    """
    from knowledge.connection import _get_graphiti
    g = _get_graphiti()
    driver = g.driver   # FalkorDriver instance (graphiti_core stores it as .driver)

    try:
        # FalkorDriver.execute_query returns (rows: list[dict], columns: list[str], stats)
        raw = await driver.execute_query(query, **(params or {}))
        if isinstance(raw, tuple):
            rows = raw[0]
        else:
            rows = raw
        return rows if isinstance(rows, list) else []
    except Exception as exc:
        log.error("Cypher execution failed: %s | query: %.200s", exc, query)
        return []


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# C7.2 — get_risk_scores()
# ---------------------------------------------------------------------------

async def get_risk_scores() -> list[RiskScoreView]:
    """
    LangGraph monitor + visualizer_agent.
    Returns all current (non-invalidated) RISK_STATE edges.

    Uses Cypher for deterministic results — semantic search on risk state
    would miss entities at calm/watch band (no salient risk keywords in fact text).
    """
    # Cypher: find all RISK_STATE edges where invalid_at is null (current facts)
    query = """
    MATCH (src:Entity)-[r:RISK_STATE]->(tgt:Entity)
    WHERE r.invalid_at IS NULL
    RETURN
      src.uuid        AS entity_uuid,
      src.name        AS entity_name,
      r.score         AS score,
      r.band          AS band,
      r.factor_ais    AS factor_ais,
      r.factor_gdelt  AS factor_gdelt,
      r.factor_price  AS factor_price,
      r.factor_sanctions AS factor_sanctions,
      r.rationale     AS rationale,
      r.model_version AS model_version,
      r.valid_at      AS valid_at,
      r.created_at    AS recorded_at
    ORDER BY r.score DESC
    """
    rows = await _cypher(query)

    # Fallback: use semantic search if Cypher returns nothing
    # (e.g. during early graph state when no RISK_STATE edges exist yet)
    if not rows:
        return await _get_risk_scores_semantic()

    results = []
    for row in rows:
        try:
            results.append(RiskScoreView(
                entity=str(row.get("entity_name", "")),
                entity_uuid=str(row.get("entity_uuid", "")),
                score=float(row.get("score", 0.0)),
                band=str(row.get("band", "calm")),
                factors={
                    "ais":        float(row.get("factor_ais", 0.0)),
                    "gdelt":      float(row.get("factor_gdelt", 0.0)),
                    "price":      float(row.get("factor_price", 0.0)),
                    "sanctions":  float(row.get("factor_sanctions", 0.0)),
                },
                rationale=row.get("rationale"),
                model_version=row.get("model_version"),
                valid_at=str(row.get("valid_at") or _now_iso()),
                recorded_at=str(row.get("recorded_at") or _now_iso()),
            ))
        except Exception as exc:
            log.warning("Malformed RISK_STATE row: %s | error: %s", row, exc)

    return results


async def _get_risk_scores_semantic() -> list[RiskScoreView]:
    """
    Semantic fallback for get_risk_scores when Cypher returns empty results.
    Parses risk score from edge fact text.
    """
    from knowledge.connection import _get_graphiti
    g = _get_graphiti()

    try:
        edges = await g.search(
            query="current risk score RISK_STATE elevated action critical calm",
            num_results=30,
        )
    except Exception as exc:
        log.warning("Semantic risk score search failed: %s", exc)
        return []

    results = []
    for edge in edges:
        if not hasattr(edge, "attributes"):
            continue
        attrs = edge.attributes or {}
        score = attrs.get("score")
        if score is None:
            continue
        try:
            results.append(RiskScoreView(
                entity=str(attrs.get("entity_name", "")),
                entity_uuid=str(getattr(edge, "source_node_uuid", "")),
                score=float(score),
                band=attrs.get("band", "calm"),
                factors={
                    "ais":       float(attrs.get("factor_ais", 0.0)),
                    "gdelt":     float(attrs.get("factor_gdelt", 0.0)),
                    "price":     float(attrs.get("factor_price", 0.0)),
                    "sanctions": float(attrs.get("factor_sanctions", 0.0)),
                },
                rationale=attrs.get("rationale"),
                model_version=attrs.get("model_version"),
                valid_at=str(getattr(edge, "valid_at", _now_iso())),
                recorded_at=str(getattr(edge, "created_at", _now_iso())),
            ))
        except Exception:
            continue

    return results


# ---------------------------------------------------------------------------
# C7.2 — get_subgraph()
# ---------------------------------------------------------------------------

async def get_subgraph(entity: str, hops: int = 2) -> SubgraphView:
    """
    scenario_agent calls this to initialise a cascade.
    Returns all entity nodes and edges within `hops` graph hops of `entity`.
    """
    # First: resolve entity UUID
    query_uuid = """
    MATCH (n:Entity)
    WHERE n.name = $name
    RETURN n.uuid AS uuid
    LIMIT 1
    """
    rows = await _cypher(query_uuid, {"name": entity})
    entity_uuid = rows[0].get("uuid") if rows else None

    if entity_uuid is None:
        # Fuzzy fallback: partial name match
        rows = await _cypher(
            "MATCH (n:Entity) WHERE n.name CONTAINS $name RETURN n.uuid AS uuid LIMIT 1",
            {"name": entity.split()[0]},   # use first word
        )
        entity_uuid = rows[0].get("uuid") if rows else None

    if entity_uuid is None:
        log.warning("Entity not found in graph: %s", entity)
        return SubgraphView(nodes=[], edges=[])

    # Subgraph query: all nodes within N hops
    hops = min(hops, 3)   # cap at 3 for performance on demo graph
    query_sub = f"""
    MATCH path = (center:Entity {{uuid: $uuid}})-[*1..{hops}]-(neighbor:Entity)
    WITH collect(DISTINCT neighbor) AS neighbors,
         collect(DISTINCT relationships(path)) AS edge_lists
    UNWIND neighbors AS n
    UNWIND edge_lists AS edges
    UNWIND edges AS r
    RETURN
      collect(DISTINCT {{
        uuid: n.uuid,
        display_name: n.name,
        labels: n.labels,
        attributes: n {{.*}}
      }}) AS nodes,
      collect(DISTINCT {{
        fact: r.fact,
        relation_type: type(r),
        source_uuid: startNode(r).uuid,
        target_uuid: endNode(r).uuid,
        valid_at: r.valid_at,
        attributes: r {{.*}}
      }}) AS edges
    """
    rows = await _cypher(query_sub, {"uuid": entity_uuid})
    if not rows:
        return SubgraphView(nodes=[], edges=[])

    row    = rows[0]
    nodes  = row.get("nodes", []) or []
    edges  = row.get("edges", []) or []
    return SubgraphView(nodes=nodes, edges=edges)


# ---------------------------------------------------------------------------
# C7.2 — get_available_suppliers()
# ---------------------------------------------------------------------------

async def get_available_suppliers(risk_max: float = 0.4) -> list[SupplierView]:
    """
    alt_procurement_agent. Returns Suppliers with latest risk_score < risk_max
    and not marked sanctioned.
    """
    query = """
    MATCH (s:Entity)
    WHERE 'Supplier' IN s.labels AND (s.sanctioned IS NULL OR s.sanctioned = false)
    OPTIONAL MATCH (s)-[r:RISK_STATE]->(x:Entity)
      WHERE r.invalid_at IS NULL
    RETURN
      s.uuid             AS uuid,
      s.name             AS display_name,
      s.country          AS country,
      s.daily_export_mbpd AS daily_export_mbpd,
      r.score            AS risk_score
    ORDER BY r.score ASC NULLS LAST
    """
    rows = await _cypher(query)

    results = []
    for row in rows:
        risk = row.get("risk_score")
        if risk is not None and float(risk) >= risk_max:
            continue
        results.append(SupplierView(
            entity_uuid=str(row.get("uuid", "")),
            display_name=str(row.get("display_name", "")),
            country=row.get("country"),
            daily_export_mbpd=_safe_float(row.get("daily_export_mbpd")),
            risk_score=_safe_float(risk),
        ))

    return results


# ---------------------------------------------------------------------------
# C7.2 — get_grade_specs()
# ---------------------------------------------------------------------------

async def get_grade_specs(refinery: str) -> list[GradeSpecView]:
    """
    alt_procurement_agent. Returns CONFIGURED_FOR edges for a named refinery,
    joined with CrudeGrade attributes.
    """
    query = """
    MATCH (r:Entity)-[e:CONFIGURED_FOR]->(g:Entity)
    WHERE 'Refinery' IN r.labels AND r.name = $refinery
      AND 'CrudeGrade' IN g.labels
    RETURN
      r.name      AS refinery,
      g.name      AS grade,
      g.api_gravity  AS api_gravity,
      g.sulfur_pct   AS sulfur_pct,
      e.yield_pct    AS yield_pct,
      e.compatibility AS compatibility
    """
    rows = await _cypher(query, {"refinery": refinery})

    return [
        GradeSpecView(
            refinery=str(row.get("refinery", refinery)),
            grade=str(row.get("grade", "")),
            api_gravity=_safe_float(row.get("api_gravity")),
            sulfur_pct=_safe_float(row.get("sulfur_pct")),
            yield_pct=_safe_float(row.get("yield_pct")),
            compatibility=_safe_float(row.get("compatibility")),
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# C7.2 — get_routes()
# ---------------------------------------------------------------------------

async def get_routes(risk_max: float = 0.5) -> list[CorridorView]:
    """
    alt_procurement_agent. Returns Corridors with latest risk_score < risk_max.
    """
    query = """
    MATCH (c:Entity)
    WHERE 'Corridor' IN c.labels
    OPTIONAL MATCH (c)-[r:RISK_STATE]->(x:Entity)
      WHERE r.invalid_at IS NULL
    RETURN
      c.uuid           AS uuid,
      c.name           AS display_name,
      r.score          AS risk_score,
      c.throughput_mbpd AS throughput_mbpd,
      c.h3_cells        AS h3_cells
    ORDER BY r.score ASC NULLS LAST
    """
    rows = await _cypher(query)

    results = []
    for row in rows:
        risk = row.get("risk_score")
        if risk is not None and float(risk) >= risk_max:
            continue
        h3 = row.get("h3_cells") or []
        if isinstance(h3, str):
            h3 = [h3]
        results.append(CorridorView(
            entity_uuid=str(row.get("uuid", "")),
            display_name=str(row.get("display_name", "")),
            risk_score=_safe_float(risk),
            throughput_mbpd=_safe_float(row.get("throughput_mbpd")),
            h3_cells=h3,
        ))

    return results


# ---------------------------------------------------------------------------
# C7.2 — get_spr_state()
# ---------------------------------------------------------------------------

async def get_spr_state() -> list[SPRCavernView]:
    """
    reserve_optim_agent. Returns all SPRCavern fill levels.
    India has 3 sites: Vizag (1.33 MMT), Mangaluru (1.5 MMT), Padur (2.5 MMT).
    """
    query = """
    MATCH (s:Entity)
    WHERE 'SPRCavern' IN s.labels
    RETURN
      s.uuid            AS uuid,
      s.name            AS display_name,
      s.location        AS location,
      s.capacity_mmt    AS capacity_mmt,
      s.current_fill_mmt AS current_fill_mmt
    """
    rows = await _cypher(query)

    return [
        SPRCavernView(
            entity_uuid=str(row.get("uuid", "")),
            display_name=str(row.get("display_name", "")),
            location=row.get("location"),
            capacity_mmt=_safe_float(row.get("capacity_mmt")),
            current_fill_mmt=_safe_float(row.get("current_fill_mmt")),
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# C7.2 — get_wiki_page()
# ---------------------------------------------------------------------------

async def get_wiki_page(entity: str) -> WikiPage:
    """
    visualizer_agent. Returns narrative synthesis page for a node click.
    Retrieved from /wiki store, not generated on demand.
    """
    from knowledge.synthesis import load_wiki_page, _wiki_path

    content = load_wiki_page(entity)
    path    = _wiki_path(entity)

    last_updated: Optional[str] = None
    if path.exists():
        mtime = path.stat().st_mtime
        last_updated = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return WikiPage(entity=entity, content=content, last_updated=last_updated)


# ---------------------------------------------------------------------------
# C7.2 — copilot_query() — EA-GraphRAG router
# ---------------------------------------------------------------------------

_COMPLEX_PATTERN = re.compile(
    r"\b(why|how|compare|difference|explain|which|what would happen|"
    r"trade.?off|impact|cascade|affect|relationship|between|versus|vs)\b",
    re.IGNORECASE,
)


async def copilot_query(q: str) -> CopilotAnswer:
    """
    visualizer_agent copilot.

    EA-GraphRAG routing:
      SIMPLE  → vector + BM25 hybrid search (~380ms) — factual lookups
      COMPLEX → graph-augmented PPR (Personalized PageRank) (~1,800ms)
                for multi-hop reasoning and causal questions

    Routing heuristic: complex if query contains reasoning/comparison keywords
    OR if query length > 12 words (long questions imply multi-hop reasoning).
    """
    import time
    t0 = time.monotonic()

    is_complex = bool(_COMPLEX_PATTERN.search(q)) or len(q.split()) > 12
    route      = "graph" if is_complex else "vector"

    if is_complex:
        answer, citations = await _graph_ppr_query(q)
    else:
        answer, citations = await _vector_bm25_query(q)

    latency_ms = (time.monotonic() - t0) * 1000

    return CopilotAnswer(
        answer=answer,
        citations=citations,
        route=route,
        latency_ms=round(latency_ms, 1),
    )


async def _vector_bm25_query(q: str) -> tuple[str, list[str]]:
    """
    Simple path: Graphiti hybrid search (vector + BM25), then Nova Lite synthesis.
    Used for factual lookups: "What is the current risk score for Hormuz?",
    "Is NIOC sanctioned?", "What is Jamnagar's capacity?"
    """
    from knowledge.connection import _get_graphiti
    from knowledge.bedrock import nova_pro

    g = _get_graphiti()

    edges = await g.search(query=q, num_results=10)
    facts     = [getattr(e, "fact", str(e)) for e in edges]
    citations = [str(getattr(e, "uuid", "")) for e in edges if getattr(e, "uuid", "")]

    context = "\n".join(f"- {f}" for f in facts[:8])

    messages = [
        {
            "role": "system",
            "content": (
                "You are the SAGE intelligence copilot for India's oil supply chain. "
                "Answer the user's question concisely using only the provided context. "
                "If the context doesn't contain enough information, say so. "
                "Do not speculate beyond what the context states."
            ),
        },
        {
            "role": "user",
            "content": f"Context:\n{context}\n\nQuestion: {q}",
        },
    ]

    try:
        llm    = g.llm_client
        result = await llm.generate(messages=messages)
        answer = result if isinstance(result, str) else str(result)
    except Exception as exc:
        log.warning("Copilot LLM call failed: %s — returning raw facts", exc)
        answer = context or "No relevant information found in the knowledge base."

    return answer.strip(), citations


async def _graph_ppr_query(q: str) -> tuple[str, list[str]]:
    """
    Complex path: semantic search + graph traversal for multi-hop reasoning.

    Implementation:
    1. Identify anchor entities from query (semantic search, top-3 results)
    2. For each anchor, expand 2-hop subgraph via Cypher
    3. Collect all unique facts from subgraph
    4. Pass to Nova Pro for synthesis with full graph context

    This approximates HippoRAG2 PPR without requiring a separate index:
    the FalkorDB graph IS the PPR graph.
    """
    from knowledge.connection import _get_graphiti

    g = _get_graphiti()

    # Step 1: anchor entities via semantic search
    seed_edges = await g.search(query=q, num_results=5)
    anchor_uuids = list({
        getattr(e, "source_node_uuid", None) for e in seed_edges
        if getattr(e, "source_node_uuid", None)
    })

    # Step 2: 2-hop expansion from anchors
    all_facts: list[str] = []
    all_citations: list[str] = []

    for anchor_uuid in anchor_uuids[:3]:
        query_expand = """
        MATCH (n:Entity {uuid: $uuid})-[r*1..2]-(m:Entity)
        RETURN r AS rels
        LIMIT 20
        """
        rows = await _cypher(query_expand, {"uuid": anchor_uuid})
        for row in rows:
            rels = row.get("rels") or []
            if not isinstance(rels, list):
                rels = [rels]
            for rel in rels:
                if isinstance(rel, dict):
                    fact = rel.get("fact", "")
                    uid  = rel.get("uuid", "")
                elif hasattr(rel, "fact"):
                    fact = rel.fact
                    uid  = getattr(rel, "uuid", "")
                else:
                    continue
                if fact:
                    all_facts.append(str(fact))
                if uid:
                    all_citations.append(str(uid))

    # Also include seed edge facts
    for e in seed_edges:
        fact = getattr(e, "fact", None)
        uid  = getattr(e, "uuid", None)
        if fact:
            all_facts.append(str(fact))
        if uid:
            all_citations.append(str(uid))

    # Deduplicate
    all_facts    = list(dict.fromkeys(all_facts))[:20]
    all_citations = list(dict.fromkeys(all_citations))

    context = "\n".join(f"- {f}" for f in all_facts)

    messages = [
        {
            "role": "system",
            "content": (
                "You are the SAGE intelligence copilot. You specialise in multi-hop "
                "reasoning over India's oil supply chain knowledge graph. "
                "Answer the user's question by synthesising the provided graph facts. "
                "Explain causal chains and cascade effects where relevant. "
                "Be analytical and precise. Cite specific entities and relationships."
            ),
        },
        {
            "role": "user",
            "content": f"Graph context ({len(all_facts)} facts):\n{context}\n\nQuestion: {q}",
        },
    ]

    try:
        llm    = g.llm_client
        result = await llm.generate(messages=messages)
        answer = result if isinstance(result, str) else str(result)
    except Exception as exc:
        log.warning("Graph PPR LLM call failed: %s — returning facts", exc)
        answer = context or "No relevant graph context found."

    return answer.strip(), all_citations


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
