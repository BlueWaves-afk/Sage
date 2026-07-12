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
from datetime import datetime, timezone, timedelta
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


class GraphNodeView(BaseModel):
    """One knowledge-graph node, positioned for the geospatial map view."""
    id: str                       # entity uuid
    name: str                     # canonical display name
    type: str                     # C2 entity type (Corridor, Supplier, …)
    lat: Optional[float] = None
    lon: Optional[float] = None
    score: float = 0.0            # current risk score (0 if none)
    band: str = "CALM"            # risk band (traffic-light colouring)
    degree: int = 0               # link count → node prominence/size
    # Provenance — every node value traces to a real, cited source.
    prov_tier: Optional[str] = None          # real | derived | estimated
    prov_source_label: Optional[str] = None  # human-readable source
    prov_source_url: Optional[str] = None     # clickable citation link
    prov_as_of: Optional[str] = None
    prov_notes: Optional[str] = None


class GraphEdgeView(BaseModel):
    source: str                   # source uuid
    target: str                   # target uuid
    relation: str                 # SUPPLIES / FEEDS / EXPORTS_VIA / …


class GraphView(BaseModel):
    nodes: list[GraphNodeView]
    edges: list[GraphEdgeView]


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


class RiskHistoryPoint(BaseModel):
    """One bitemporal RISK_STATE observation (current or invalidated)."""
    valid_at: str
    score: float
    factor_ais: float = 0.0
    factor_gdelt: float = 0.0
    factor_price: float = 0.0
    factor_sanctions: float = 0.0


class WikiPage(BaseModel):
    entity: str
    content: str
    last_updated: Optional[str] = None


class CopilotSource(BaseModel):
    index: int              # 1-based citation number used inline as [n]
    entity: str             # entity display name (clickable → wiki)
    type: str = "Entity"    # C2 entity type
    kind: str = "wiki"      # "wiki" (narrative page) | "graph" (edge fact)
    snippet: Optional[str] = None


class CopilotAnswer(BaseModel):
    answer: str
    citations: list[str]              # legacy flat list (kept for compatibility)
    sources: list[CopilotSource] = []  # numbered, clickable sources (Perplexity-style)
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
    # graphiti-core stores all custom edges as RELATES_TO with the edge type in
    # r.name and the typed attributes as edge properties (r.score, r.band, …).
    query = """
    MATCH (src:Entity)-[r:RELATES_TO]->(tgt:Entity)
    WHERE r.name = 'RISK_STATE' AND r.invalid_at IS NULL
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


async def get_output(kind: str, scenario_id: Optional[str] = None) -> Optional[dict]:
    """
    Read back a structured agent output (System 2/3/4) from the Redis output cache.

    kind        : "scenario" | "procurement" | "spr"
    scenario_id : specific run id, or None for the most recent output of that kind.

    Returns the exact model_dump() the agent wrote (full fidelity — not parsed from
    episode prose), or None if nothing is cached. Drives /api/scenario, /api/procurement,
    /api/spr-schedule for the frontend.
    """
    import json
    import os
    if kind not in ("scenario", "procurement", "spr"):
        raise ValueError(f"unknown output kind: {kind}")
    key = f"sage:{kind}:{scenario_id or 'latest'}"
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"),
                                   decode_responses=True)
        try:
            raw = await client.get(key)
        finally:
            await client.aclose()
        return json.loads(raw) if raw else None
    except Exception as exc:
        log.warning("get_output(%s, %s) failed: %s", kind, scenario_id, exc)
        return None


# ---------------------------------------------------------------------------
# Scenario Library (Feature A) — durable index of every run (auto/user/preset)
# ---------------------------------------------------------------------------

async def list_scenarios(limit: int = 20, origin: str = "all") -> list[dict]:
    """
    Read the scenario library: newest-first cards from `sage:scenario:index`
    (a sorted set, score=epoch seconds) + their `sage:scenario:meta:{id}` hash.
    Cards outlive the 24h full-payload TTL (meta carries a 30-day TTL), so the
    library survives even after the underlying `sage:scenario:{id}` has expired
    (`payload_available` reflects that).
    """
    import os
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"),
                                   decode_responses=True)
        try:
            ids = await client.zrevrange("sage:scenario:index", 0, max(limit * 3, limit) - 1)
            cards: list[dict] = []
            for sid in ids:
                meta = await client.hgetall(f"sage:scenario:meta:{sid}")
                if not meta:
                    continue
                if origin != "all" and meta.get("origin") != origin:
                    continue
                payload_exists = bool(await client.exists(f"sage:scenario:{sid}"))
                cards.append({
                    "scenario_id": sid,
                    "label": meta.get("label", sid),
                    "origin": meta.get("origin", "user"),
                    "trigger_entity": meta.get("trigger_entity", ""),
                    "gap_mbpd": float(meta.get("gap_mbpd", 0) or 0),
                    "price_impact_high": float(meta.get("price_impact_high", 0) or 0),
                    "gdp_proxy_impact_pct": (
                        float(meta["gdp_proxy_impact_pct"]) if meta.get("gdp_proxy_impact_pct") not in (None, "", "None") else None
                    ),
                    "spr_depletion_days": float(meta.get("spr_depletion_days", 0) or 0),
                    "created_at": meta.get("created_at", ""),
                    "payload_available": payload_exists,
                })
                if len(cards) >= limit:
                    break
            return cards
        finally:
            await client.aclose()
    except Exception as exc:
        log.warning("list_scenarios failed: %s", exc)
        return []


async def get_custom_presets() -> list[dict]:
    """Read user-promoted scenario presets (curated, no TTL) from Redis."""
    import os
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"),
                                   decode_responses=True)
        try:
            slugs = await client.smembers("sage:preset:custom:index")
            presets = []
            for slug in slugs:
                h = await client.hgetall(f"sage:preset:custom:{slug}")
                if not h:
                    continue
                presets.append({
                    "id": f"custom_{slug}",
                    "label": h.get("label", slug),
                    "entity": h.get("entity", ""),
                    "disruption_fraction": float(h.get("disruption_fraction", 0) or 0),
                    "disruption_days": int(float(h.get("disruption_days", 0) or 0)),
                    "escalation_profile": h.get("escalation_profile", "constant"),
                    "bypass_compromised_frac": float(h.get("bypass_compromised_frac", 0) or 0),
                    "spr_policy": h.get("spr_policy", "moderate"),
                    "demand_destruction_pct": float(h.get("demand_destruction_pct", 0) or 0),
                    "blurb": h.get("blurb", ""),
                    "custom": True,
                    "source_scenario_id": h.get("source_scenario_id", ""),
                })
            return presets
        finally:
            await client.aclose()
    except Exception as exc:
        log.warning("get_custom_presets failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Scenario accuracy / calibration (Feature B) — reads for the Learning panel
# ---------------------------------------------------------------------------

def get_scenario_accuracy() -> Optional[dict]:
    """Aggregate prediction-vs-realized error from the scenario outcome ledger."""
    from knowledge.feedback import get_scenario_accuracy as _impl
    return _impl()


async def get_calibration_factors() -> dict:
    """Learned per-corridor gap/price correction factors (bounded, visible)."""
    import os
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"),
                                   decode_responses=True)
        try:
            entities = await client.smembers("sage:calib:index")
            out = {}
            for entity in entities:
                h = await client.hgetall(f"sage:calib:params:{entity}")
                if h:
                    out[entity] = {
                        "gap_x": float(h.get("gap_x", 1.0)),
                        "price_x": float(h.get("price_x", 1.0)),
                        "n": int(float(h.get("n", 0))),
                    }
            return out
        finally:
            await client.aclose()
    except Exception as exc:
        log.warning("get_calibration_factors failed: %s", exc)
        return {}


async def get_risk_history(entity: str, hours: int = 72) -> list[RiskHistoryPoint]:
    """
    Anticipatory sandbox (Stage 1 forecast input).

    Returns the bitemporal RISK_STATE time series for one entity over the last `hours`,
    oldest → newest. Includes both invalidated edges (past values) and the current edge
    (invalid_at IS NULL) — that IS the historical signal trajectory the forecaster projects.

    Falls back to an empty list when the entity has no risk history yet (e.g. before System 1
    has produced any signals for it); callers should degrade to a current-signal projection.
    """
    from datetime import datetime, timezone, timedelta

    query = """
    MATCH (src:Entity)-[r:RELATES_TO]->(tgt:Entity)
    WHERE r.name = 'RISK_STATE' AND src.name = $entity
    RETURN
      r.score            AS score,
      r.factor_ais       AS factor_ais,
      r.factor_gdelt     AS factor_gdelt,
      r.factor_price     AS factor_price,
      r.factor_sanctions AS factor_sanctions,
      r.valid_at         AS valid_at
    """
    rows = await _cypher(query, {"entity": entity})
    if not rows:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    points: list[RiskHistoryPoint] = []
    for row in rows:
        va = row.get("valid_at")
        ts = _parse_iso(str(va)) if va else None
        if ts is not None and ts < cutoff:
            continue
        try:
            points.append(RiskHistoryPoint(
                valid_at=str(va or _now_iso()),
                score=float(row.get("score", 0.0) or 0.0),
                factor_ais=float(row.get("factor_ais", 0.0) or 0.0),
                factor_gdelt=float(row.get("factor_gdelt", 0.0) or 0.0),
                factor_price=float(row.get("factor_price", 0.0) or 0.0),
                factor_sanctions=float(row.get("factor_sanctions", 0.0) or 0.0),
            ))
        except Exception as exc:
            log.warning("Malformed RISK_STATE history row: %s | error: %s", row, exc)

    points.sort(key=lambda p: p.valid_at)
    return points


def _parse_iso(s: str):
    """Best-effort ISO-8601 → aware datetime; None on failure."""
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


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

    # Subgraph within N hops. Nodes and edges are fetched in TWO separate queries
    # rather than one. The previous single query did
    #   UNWIND neighbors AS n UNWIND edge_lists AS edges
    # which forms a cartesian product (|neighbors| × |edge_lists|) before DISTINCT.
    # On a well-connected hub (Hormuz, ADNOC) that explodes to millions of
    # intermediate rows and times out at ~10s, holding one of FalkorDB's two
    # worker threads and starving every other query (including the ingest
    # consumer's risk-state writes). Two aggregations, each linear in the number
    # of matched paths, return the identical shape without the blow-up.
    hops = min(hops, 3)   # cap at 3 for performance on demo graph

    # Exclude bookkeeping edges from the traversal. RISK_STATE is a self-loop
    # (a)->(a) written once per risk update — there are ~1.7k of them, and a
    # variable-length expansion that walks them multiplies paths through every
    # hub until the query times out at ~10s. MENTIONS is likewise episode noise,
    # not supply-chain topology. Filtering them out is both the correct semantics
    # for the scenario cascade (it wants structural relationships) and the
    # difference between a 10s timeout and ~30ms on a hub like ADNOC/Hormuz.
    exclude = ["RISK_STATE", "MENTIONS"]
    _no_bookkeeping = "none(e IN relationships(path) WHERE e.name IN $exclude)"

    query_nodes = f"""
    MATCH path = (center:Entity {{uuid: $uuid}})-[*1..{hops}]-(neighbor:Entity)
    WHERE {_no_bookkeeping}
    RETURN collect(DISTINCT {{
        uuid: neighbor.uuid,
        display_name: neighbor.name,
        labels: neighbor.labels,
        attributes: neighbor {{.*}}
    }}) AS nodes
    """
    query_edges = f"""
    MATCH path = (center:Entity {{uuid: $uuid}})-[*1..{hops}]-(:Entity)
    WHERE {_no_bookkeeping}
    UNWIND relationships(path) AS r
    RETURN collect(DISTINCT {{
        fact: r.fact,
        relation_type: coalesce(r.name, type(r)),
        source_uuid: startNode(r).uuid,
        target_uuid: endNode(r).uuid,
        valid_at: r.valid_at,
        attributes: r {{.*}}
    }}) AS edges
    """
    node_rows = await _cypher(query_nodes, {"uuid": entity_uuid, "exclude": exclude})
    edge_rows = await _cypher(query_edges, {"uuid": entity_uuid, "exclude": exclude})

    nodes = (node_rows[0].get("nodes", []) if node_rows else []) or []
    edges = (edge_rows[0].get("edges", []) if edge_rows else []) or []
    return SubgraphView(nodes=nodes, edges=edges)


# ---------------------------------------------------------------------------
# Full knowledge graph — the geospatial "Obsidian on a map" view
# ---------------------------------------------------------------------------

# Structural relationships worth drawing as supply-chain arcs (everything except
# the internal RISK_STATE / MENTIONS bookkeeping edges).
_STRUCTURAL_RELATIONS = {
    "SUPPLIES", "FEEDS", "EXPORTS_VIA", "CONFIGURED_FOR", "BYPASS_ROUTE",
    "SANCTIONED_BY", "CONNECTS", "ROUTES_THROUGH",
}


def _band_from_score(score: float) -> str:
    if score >= 0.85:
        return "CRITICAL"
    if score >= 0.70:
        return "ACTION"
    if score >= 0.45:
        return "ELEVATED"
    if score >= 0.25:
        return "WATCH"
    return "CALM"


class IntelSignal(BaseModel):
    """One piece of intelligence the KB ingested — a real signal/episode."""
    id: str
    source: str            # news | gdelt | ais | price | sanctions | synthesis
    headline: str          # first line of the episode content
    detail: str = ""       # short excerpt
    source_url: str = ""   # clickable link to the original source
    entities: list[str] = []
    recorded_at: str = ""


_SOURCE_FALLBACK: dict[str, str] = {
    "sanctions":  "https://ofac.treasury.gov/sanctions-list-search",
    "ofac":       "https://ofac.treasury.gov/sanctions-list-search",
    "ais":        "https://www.marinetraffic.com/",
    "ais alerts": "https://www.marinetraffic.com/",
    "price":      "https://www.eia.gov/petroleum/",
    "price mvt":  "https://www.eia.gov/petroleum/",
    "synthesis":  "",
    "sage core":  "",
}


def _extract_url(content: str) -> str:
    """Pull the original source URL embedded in the raw-signal envelope."""
    import re
    m = re.search(r"source_url:\s*(\S+)", content or "")
    if m and m.group(1).lower().startswith("http"):
        return m.group(1).strip()
    return ""


def _source_of(source_desc: str, source: str) -> str:
    """Extract the real feed source (news/ais/price/sanctions) from an episode."""
    import re
    m = re.search(r"source=(\w+)", source_desc or "")
    if m:
        return m.group(1).lower()
    if "sandbox" in (source_desc or "").lower():
        return "synthesis"
    return (source or "synthesis").lower()


def _headline(content: str) -> str:
    """First substantive prose sentence — skips markdown headings/frontmatter/bullets
    and signal envelopes ([RAW] / [EXTRACT] prefixes)."""
    import re
    text = re.sub(r"^---[\s\S]*?---", "", content or "").strip()
    for raw in text.splitlines():
        ln = raw.strip().lstrip("#").lstrip("*").lstrip("-").strip()
        # Strip signal envelopes: "[RAW] source | ts | headline" or
        # "[EXTRACT] source | ts | entities: ... | headline"
        ln = re.sub(r"^\[(RAW|EXTRACT)\](?:[^|]*\|){2,4}\s*", "", ln).strip()
        ln = re.sub(r"\[\[([^\]]+)\]\]", r"\1", ln)  # strip [[wikilink]] markup
        if len(ln) > 15 and not ln.lower().startswith(("current assessment", "historical", "affected")):
            m = re.split(r"(?<=[.!?])\s", ln)
            return (m[0] if m else ln)[:160]
    return re.sub(r"\[\[([^\]]+)\]\]", r"\1", (text[:120] or "signal").replace("\n", " "))


async def get_recent_intelligence(limit: int = 15) -> list[IntelSignal]:
    """
    Recent ingested episodes — the live intelligence stream that drives risk. Powers
    the Command Center 'Live Intelligence' rail: real signals, newest first.
    """
    # Past 5 days of real intelligence signals (news/gdelt/ais/sanctions/price),
    # newest first, de-duplicated by headline. Episodes persist in FalkorDB, so
    # this survives page reloads and accumulates rather than being overwritten.
    since = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    scan = max(int(limit) * 8, 120)
    rows = await _cypher(
        f"MATCH (e:Episodic) WHERE e.created_at >= '{since}' "
        f"RETURN e.uuid, e.content, e.source_description, "
        f"       e.source, e.created_at, e.source_url "
        f"ORDER BY e.created_at DESC LIMIT {scan}"
    )
    out: list[IntelSignal] = []
    seen: set[str] = set()
    for r in rows or []:
        sd = r.get("e.source_description") or r.get("sd", "") or ""
        src = r.get("e.source") or r.get("src", "") or ""
        source = _source_of(sd, src)
        content = (r.get("e.content") or r.get("content") or "").strip()
        if source in ("text", "synthesis") or "risk level is assessed" in content.lower():
            continue
        head = _headline(content)
        # Drop raw GDELT event records — just actor→actor Goldstein scores, no useful prose.
        if "goldstein=" in head.lower() or head.lower().startswith("gdelt:"):
            continue
        key = head.lower().strip()[:80]
        if key in seen:            # collapse duplicates
            continue
        seen.add(key)
        raw_url = (r.get("e.source_url") or r.get("surl") or _extract_url(content) or
                   _SOURCE_FALLBACK.get(source.lower(), ""))
        out.append(IntelSignal(
            id=str(r.get("e.uuid") or r.get("uuid") or ""),
            source=source,
            headline=head,
            detail=content[:280],
            source_url=raw_url,
            recorded_at=str(r.get("e.created_at") or r.get("created_at") or ""),
        ))
        if len(out) >= limit:
            break
    return out


async def get_evidence_for(entity: str, limit: int = 12) -> list[IntelSignal]:
    """
    The source signals that drove an entity's risk — episodes MENTIONING it, newest
    first. Powers 'Supporting Evidence': lets a user see exactly what elevated a risk.
    """
    rows = await _cypher(
        "MATCH (e:Episodic)-[:MENTIONS]->(n:Entity {name:$entity}) "
        "RETURN e.uuid, e.content, e.source_description, "
        "       e.source, e.created_at, e.source_url "
        "ORDER BY e.created_at DESC LIMIT $limit",
        {"entity": entity, "limit": int(limit)},
    )
    out: list[IntelSignal] = []
    seen: set[str] = set()
    for r in rows or []:
        content = (r.get("e.content") or r.get("content") or "").strip()
        sd = r.get("e.source_description") or r.get("sd", "") or ""
        src = r.get("e.source") or r.get("src", "") or ""
        source = _source_of(sd, src)
        if source in ("text", "synthesis") or "risk level is assessed" in content.lower():
            continue
        head = _headline(content)
        key = head.lower().strip()[:80]
        if key in seen:
            continue
        seen.add(key)
        raw_url = (r.get("e.source_url") or r.get("surl") or _extract_url(content) or
                   _SOURCE_FALLBACK.get(source.lower(), ""))
        out.append(IntelSignal(
            id=str(r.get("e.uuid") or r.get("uuid") or ""),
            source=source,
            headline=head,
            detail=content[:280],
            source_url=raw_url,
            entities=[entity],
            recorded_at=str(r.get("e.created_at") or r.get("created_at") or ""),
        ))
    return out


class SupplyChainIndex(BaseModel):
    """India's overall geopolitical supply-chain risk — a KB-computed aggregate."""
    index: float                       # 0..1 importance-weighted risk
    band: str                          # CALM..CRITICAL
    method: str                        # how it's computed (transparency)
    contributors: list[dict] = []      # top entities driving the index (entity, risk, weight, contribution)
    entities_scored: int = 0


async def get_supply_chain_index() -> SupplyChainIndex:
    """
    Compute India's overall supply-chain stability risk as the importance-weighted
    mean of every entity's fused RISK_STATE, where importance = the entity's
    structural centrality (graph degree) in the India supply graph. A crisis at a
    high-throughput chokepoint (e.g. the Strait of Hormuz, the most-connected node)
    moves the national index far more than a peripheral node — and it reflects ANY
    crisis, not one hardcoded scenario. Everything is derived from the knowledge
    base: risk scores from System-1 fusion, weights from the .context-sourced graph.
    """
    graph = await get_full_graph(placed_only=False)
    degree_by_name = {n.name: max(n.degree, 1) for n in graph.nodes}

    scores = await get_risk_scores()
    num = 0.0
    den = 0.0
    contribs: list[dict] = []
    for s in scores:
        w = float(degree_by_name.get(s.entity, 1))
        num += w * float(s.score)
        den += w
        contribs.append({
            "entity": s.entity, "risk": round(float(s.score), 4),
            "weight": w, "band": s.band,
        })

    index = round(num / den, 4) if den > 0 else 0.0
    # contribution share of the numerator (how much each entity drives the index)
    for c in contribs:
        c["contribution"] = round((c["weight"] * c["risk"]) / num, 4) if num > 0 else 0.0
    contribs.sort(key=lambda c: -c["contribution"])

    return SupplyChainIndex(
        index=index,
        band=_band_from_score(index),
        method="degree-weighted mean of per-entity RISK_STATE (importance = graph centrality)",
        contributors=contribs[:6],
        entities_scored=len(scores),
    )


async def get_full_graph(placed_only: bool = True) -> GraphView:
    """
    Return the entity graph — nodes plus their structural relationships — positioned
    geographically so the frontend can render it on a map like Obsidian renders its
    force graph. Node identity, type and edges come straight from the live graph
    (FalkorDB); coordinates resolve from the registry + geo module; risk band comes
    from current RISK_STATE edges.

    `placed_only=True` (default) returns just the wiki-backed entities that have a
    real map position — the same set that has Obsidian pages — and drops edges whose
    endpoints fall outside that set. Duplicate names (Graphiti sometimes extracts a
    second generic node for the same entity) are collapsed to the highest-degree one.
    """
    from knowledge.api.geo import resolve_coordinates

    # 1. All entity nodes with their type label and useful attributes.
    node_rows = await _cypher(
        """
        MATCH (n:Entity)
        RETURN n.uuid AS uuid, n.name AS name, n.labels AS labels,
               n.country AS country, n.origin AS origin,
               n.lat AS lat, n.lon AS lon,
               n.prov_tier AS prov_tier, n.prov_source_label AS prov_source_label,
               n.prov_source_url AS prov_source_url, n.prov_as_of AS prov_as_of,
               n.prov_notes AS prov_notes
        """
    )

    # 2. All structural edges (Graphiti stores custom edges as RELATES_TO with the
    #    real type in r.name; type() covers any natively-typed edges too).
    edge_rows = await _cypher(
        """
        MATCH (s:Entity)-[r]->(t:Entity)
        WHERE r.invalid_at IS NULL
        RETURN s.uuid AS source, t.uuid AS target,
               coalesce(r.name, type(r)) AS relation
        """
    )

    # 3. Current risk scores by entity name (for band colouring).
    risk_by_name: dict[str, float] = {}
    try:
        for rs in await get_risk_scores():
            risk_by_name[rs.entity] = rs.score
    except Exception as exc:
        log.warning("get_full_graph: risk lookup failed: %s", exc)

    # Registry lookup by canonical name (authoritative coordinates + type).
    reg_by_name: dict[str, Any] = {}
    try:
        from knowledge.registry import REGISTRY
        reg_by_name = {e.canonical_name: e for e in REGISTRY.values()}
    except Exception as exc:
        log.warning("get_full_graph: registry unavailable: %s", exc)

    # Degree count for node sizing.
    degree: dict[str, int] = {}
    structural_edges: list[GraphEdgeView] = []
    for e in edge_rows:
        rel = str(e.get("relation") or "").upper()
        if rel in {"RISK_STATE", "MENTIONS", "RELATES_TO"} and rel not in _STRUCTURAL_RELATIONS:
            continue
        src, tgt = e.get("source"), e.get("target")
        if not src or not tgt or src == tgt:
            continue
        structural_edges.append(GraphEdgeView(source=src, target=tgt, relation=rel or "RELATED"))
        degree[src] = degree.get(src, 0) + 1
        degree[tgt] = degree.get(tgt, 0) + 1

    # Build nodes; collapse duplicate names to the highest-degree instance.
    best_by_name: dict[str, GraphNodeView] = {}
    for n in node_rows:
        name = str(n.get("name") or "")
        if not name:
            continue
        labels = n.get("labels") or []
        etype = next((l for l in labels if l != "Entity"), None) or "Entity"
        reg = reg_by_name.get(name)
        if reg:
            etype = reg.entity_type

        coords = resolve_coordinates(
            name=name,
            entity_type=etype,
            country=n.get("country"),
            origin=n.get("origin"),
            registry_coords=(reg.coordinates if reg else None)
            or ({"lat": n.get("lat"), "lon": n.get("lon")} if n.get("lat") is not None else None),
        )
        if placed_only and coords is None:
            continue

        uuid = str(n.get("uuid") or name)
        score = risk_by_name.get(name, 0.0)
        node = GraphNodeView(
            id=uuid,
            name=name,
            type=etype,
            lat=coords["lat"] if coords else None,
            lon=coords["lon"] if coords else None,
            score=score,
            band=_band_from_score(score),
            degree=degree.get(uuid, 0),
            prov_tier=n.get("prov_tier"),
            prov_source_label=n.get("prov_source_label"),
            prov_source_url=n.get("prov_source_url"),
            prov_as_of=n.get("prov_as_of"),
            prov_notes=n.get("prov_notes"),
        )
        prev = best_by_name.get(name)
        if prev is None or node.degree > prev.degree:
            best_by_name[name] = node

    nodes = list(best_by_name.values())

    # Drop edges whose endpoints didn't survive the node filter/dedup, and remap
    # collapsed-duplicate uuids to the surviving node's uuid (by name).
    keep_ids = {n.id for n in nodes}
    edges: list[GraphEdgeView] = []
    seen_edges: set[tuple[str, str, str]] = set()
    for e in structural_edges:
        if e.source not in keep_ids or e.target not in keep_ids:
            continue
        key = (e.source, e.target, e.relation)
        if key in seen_edges:
            continue
        seen_edges.add(key)
        edges.append(e)

    return GraphView(nodes=nodes, edges=edges)


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
    OPTIONAL MATCH (s)-[r:RELATES_TO]->(x:Entity)
      WHERE r.name = 'RISK_STATE' AND r.invalid_at IS NULL
    RETURN
      s.uuid             AS uuid,
      s.name             AS display_name,
      s.country          AS country,
      s.daily_export_mbpd AS daily_export_mbpd,
      r.score            AS risk_score
    ORDER BY risk_score ASC
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
    MATCH (r:Entity)-[e:RELATES_TO]->(g:Entity)
    WHERE e.name = 'CONFIGURED_FOR' AND 'Refinery' IN r.labels AND r.name = $refinery
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


async def get_most_exposed_refinery(entity: str) -> Optional[str]:
    """
    Resolve the refinery most exposed to a disruption at `entity`.

    If `entity` is itself a refinery, returns it unchanged. Otherwise (a corridor,
    port, or other node), looks up the deterministic EXPOSES edges written by
    knowledge.context.dedup.derive_exposures() (Σ_port FEEDS(corridor→port) ×
    SUPPLIES(port→refinery)) and returns the highest-exposure refinery.

    Callers (procure_node, orchestration.triggers._run_procurement) need a REFINERY
    name to pass to alt_procurement_agent.runner.run(trigger_refinery=...) — passing
    the corridor's own name there is a bug (there is no refinery called "Strait of
    Hormuz"), so this is the single place that resolves "which refinery is actually
    short of feedstock" from the real KB structure, no hardcoding.
    """
    try:
        from knowledge.registry import REGISTRY
        entry = next((e for e in REGISTRY.values() if e.canonical_name == entity), None)
        if entry and entry.entity_type == "Refinery":
            return entity
    except Exception:
        pass

    rows = await _cypher(
        """
        MATCH (c:Entity {name: $entity})-[r:RELATES_TO]->(ref:Entity)
        WHERE r.name = 'EXPOSES' AND 'Refinery' IN ref.labels
        RETURN ref.name AS name, r.exposure_pct AS exposure
        ORDER BY r.exposure_pct DESC
        LIMIT 1
        """,
        {"entity": entity},
    )
    if rows and rows[0].get("name"):
        return str(rows[0]["name"])

    log.warning(
        "get_most_exposed_refinery: no EXPOSES edge found for '%s' — "
        "falling back to Jamnagar Refinery (India's largest refinery)", entity,
    )
    return "Jamnagar Refinery"


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
    OPTIONAL MATCH (c)-[r:RELATES_TO]->(x:Entity)
      WHERE r.name = 'RISK_STATE' AND r.invalid_at IS NULL
    RETURN
      c.uuid           AS uuid,
      c.name           AS display_name,
      r.score          AS risk_score,
      c.throughput_mbpd AS throughput_mbpd,
      c.h3_cells        AS h3_cells
    ORDER BY risk_score ASC
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


async def get_port_congestion() -> dict[str, float]:
    """
    G5: Return {port_display_name → congestion_float} for Port entities in the graph.
    Port.congestion is in [0,1]: 0 = clear, 1 = fully congested.
    Used by alt_procurement_agent/routing.py to compute berth-wait delays.
    """
    query = """
    MATCH (p:Entity)
    WHERE 'Port' IN p.labels AND p.congestion IS NOT NULL
    RETURN p.name AS name, p.congestion AS congestion
    """
    try:
        rows = await _cypher(query)
        return {str(r["name"]): float(r["congestion"]) for r in rows if r.get("name") and r.get("congestion") is not None}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# C7.2 — get_spr_state()
# ---------------------------------------------------------------------------

async def get_spr_state() -> list[SPRCavernView]:
    """
    reserve_optim_agent. Returns all SPRCavern fill levels.
    India has exactly 3 sites: Vizag (1.33 MMT), Mangaluru (1.5 MMT), Padur (2.5 MMT).

    Filtered to the registry's known canonical cavern names rather than "any node
    labelled SPRCavern": Graphiti's LLM extraction will occasionally spawn a bogus
    aggregate node (e.g. a generic "SPR" entity with capacity_mmt = the SUM of the
    three real sites) from narrative text that mentions the total reserve figure.
    Since India's SPR sites are a small, fixed, real-world set, filtering to the
    registry is strictly more correct than trusting arbitrary extracted labels, and
    prevents that aggregate node from silently doubling get_spr_state()'s totals.
    """
    try:
        from knowledge.registry import REGISTRY
        canonical_names = [e.canonical_name for e in REGISTRY.values() if e.entity_type == "SPRCavern"]
    except Exception:
        canonical_names = ["Vizag SPR", "Mangaluru SPR", "Padur SPR"]

    query = """
    MATCH (s:Entity)
    WHERE 'SPRCavern' IN s.labels AND s.name IN $names
    RETURN
      s.uuid            AS uuid,
      s.name            AS display_name,
      s.location        AS location,
      s.capacity_mmt    AS capacity_mmt,
      s.current_fill_mmt AS current_fill_mmt
    """
    rows = await _cypher(query, {"names": canonical_names})

    # Dedup by name (keep the entry with the higher fill == the earlier, well-formed
    # writes) in case more than one node matches a canonical name.
    by_name: dict[str, dict] = {}
    for row in rows:
        name = str(row.get("display_name", ""))
        prev = by_name.get(name)
        if prev is None or (row.get("current_fill_mmt") or 0) > (prev.get("current_fill_mmt") or 0):
            by_name[name] = row

    return [
        SPRCavernView(
            entity_uuid=str(row.get("uuid", "")),
            display_name=str(row.get("display_name", "")),
            location=row.get("location"),
            capacity_mmt=_safe_float(row.get("capacity_mmt")),
            current_fill_mmt=_safe_float(row.get("current_fill_mmt")),
        )
        for row in by_name.values()
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
        answer, citations, sources = await _graph_ppr_query(q)
    else:
        answer, citations, sources = await _vector_bm25_query(q)

    latency_ms = (time.monotonic() - t0) * 1000

    return CopilotAnswer(
        answer=answer,
        citations=citations,
        sources=sources,
        route=route,
        latency_ms=round(latency_ms, 1),
    )


# Perplexity-style answer contract shared by both retrieval paths.
_COPILOT_STYLE = (
    "Format your answer as clean Markdown for an intelligence analyst:\n"
    "- Open with a 1–2 sentence direct answer.\n"
    "- Use ## short section headings when the answer has multiple parts.\n"
    "- Use bullet lists for factors and numbered lists for sequences/steps.\n"
    "- Use a Markdown table when comparing options across attributes.\n"
    "- **Bold** key entities, numbers, and verdicts.\n"
    "- Cite sources inline as [n] using the numbered SOURCES list — place the "
    "marker right after the clause it supports. Only cite numbers that appear in "
    "SOURCES. Do not invent sources or add a references section.\n"
    "- If the context is insufficient, say so plainly."
)


def _number_sources(entities: list[str], edge_facts: list[str] | None = None) -> tuple[list[CopilotSource], str]:
    """
    Build a numbered, clickable source list (entities first, then key graph facts)
    and the SOURCES block to hand the LLM so it can cite [n] inline.
    """
    try:
        from knowledge.registry import REGISTRY
        type_by_name = {e.canonical_name: e.entity_type for e in REGISTRY.values()}
    except Exception:
        type_by_name = {}

    sources: list[CopilotSource] = []
    lines: list[str] = []
    n = 0
    for ent in entities:
        n += 1
        sources.append(CopilotSource(index=n, entity=ent, type=type_by_name.get(ent, "Entity"), kind="wiki"))
        lines.append(f"[{n}] {ent} — SAGE wiki assessment")
    for fact in (edge_facts or [])[:4]:
        n += 1
        short = fact if len(fact) < 90 else fact[:87] + "…"
        sources.append(CopilotSource(index=n, entity=short, type="Relationship", kind="graph", snippet=fact))
        lines.append(f"[{n}] graph fact: {fact}")
    return sources, "\n".join(lines)


def _entities_in_query(q: str) -> list[str]:
    """Resolve any tracked-entity names mentioned in the query to canonical names."""
    try:
        from knowledge.registry import ALIAS_TO_ENTITY, canonical_name
    except Exception:
        return []
    ql = f" {q.lower()} "
    found: list[str] = []
    for alias, eid in ALIAS_TO_ENTITY.items():
        if len(alias) < 4:
            continue
        if f" {alias} " in ql or ql.strip().endswith(alias) or alias in ql:
            cn = canonical_name(eid)
            if cn and cn not in found:
                found.append(cn)
    return found[:5]


def _wiki_context(entities: list[str]) -> tuple[list[str], list[str]]:
    """
    Load the reconciled wiki page for each named entity and pull its narrative
    sections (the LLM-synthesised prose). Returns (context_blocks, citations).
    """
    from knowledge.synthesis import load_wiki_page

    blocks: list[str] = []
    cites: list[str] = []
    for ent in entities:
        try:
            content = load_wiki_page(ent)
        except Exception:
            continue
        if not content or "No wiki" in content[:40]:
            continue
        # Strip YAML frontmatter, keep the prose body.
        body = re.sub(r"^---[\s\S]*?---", "", content).strip()
        if body:
            blocks.append(f"[{ent}]\n{body[:900]}")
            cites.append(ent)
    return blocks, cites


async def _vector_bm25_query(q: str) -> tuple[str, list[str], list[CopilotSource]]:
    """
    Simple path: entity-aware wiki retrieval + Graphiti hybrid search (vector +
    BM25), then Nova synthesis. Used for factual lookups: "What is Hormuz's risk?",
    "Is NIOC sanctioned?", "What is Jamnagar's capacity?"
    """
    from knowledge.connection import _get_graphiti

    g = _get_graphiti()

    # Entity-aware retrieval: pull reconciled wiki narrative for named entities.
    entities = _entities_in_query(q)
    wiki_blocks, wiki_cites = _wiki_context(entities)

    edges = await g.search(query=q, num_results=10)
    facts     = [getattr(e, "fact", str(e)) for e in edges]
    edge_cites = [str(getattr(e, "uuid", "")) for e in edges if getattr(e, "uuid", "")]

    # Numbered, clickable sources (entities that had wiki pages + top facts).
    sources, source_block = _number_sources(wiki_cites, facts)

    context = "\n".join(wiki_blocks)
    if facts:
        context += "\n\nRelated facts:\n" + "\n".join(f"- {f}" for f in facts[:8])
    citations = wiki_cites + edge_cites

    messages = [
        {
            "role": "system",
            "content": (
                "You are the SAGE intelligence copilot for India's oil supply chain. "
                "Answer using only the provided context. Do not speculate beyond it.\n\n"
                + _COPILOT_STYLE
            ),
        },
        {
            "role": "user",
            "content": f"CONTEXT:\n{context}\n\nSOURCES:\n{source_block}\n\nQUESTION: {q}",
        },
    ]

    try:
        llm    = g.llm_client
        result = await llm.generate(messages=messages)
        answer = result if isinstance(result, str) else str(result)
    except Exception as exc:
        log.warning("Copilot LLM call failed: %s — returning raw facts", exc)
        answer = context or "No relevant information found in the knowledge base."

    return answer.strip(), citations, sources


async def _graph_ppr_query(q: str) -> tuple[str, list[str], list[CopilotSource]]:
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

    # Step 0: entity-aware wiki retrieval — the reconciled narrative that holds
    # the "why/how" descriptive content graph edge-facts don't capture.
    wiki_blocks, wiki_cites = _wiki_context(_entities_in_query(q))

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
    all_citations = list(dict.fromkeys(wiki_cites + all_citations))

    # Numbered clickable sources (wiki entities + key graph facts).
    sources, source_block = _number_sources(wiki_cites, all_facts)

    context = ""
    if wiki_blocks:
        context += "Entity assessments:\n" + "\n".join(wiki_blocks) + "\n\n"
    context += "Graph relationships:\n" + "\n".join(f"- {f}" for f in all_facts)

    messages = [
        {
            "role": "system",
            "content": (
                "You are the SAGE intelligence copilot specialising in multi-hop "
                "reasoning over India's oil supply chain knowledge graph. Synthesise "
                "the provided assessments and graph facts; explain causal chains and "
                "cascade effects. Use only the provided context.\n\n" + _COPILOT_STYLE
            ),
        },
        {
            "role": "user",
            "content": f"CONTEXT:\n{context}\n\nSOURCES:\n{source_block}\n\nQUESTION: {q}",
        },
    ]

    try:
        llm    = g.llm_client
        result = await llm.generate(messages=messages)
        answer = result if isinstance(result, str) else str(result)
    except Exception as exc:
        log.warning("Graph PPR LLM call failed: %s — returning facts", exc)
        answer = context or "No relevant graph context found."

    return answer.strip(), all_citations, sources


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
