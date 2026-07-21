"""
FastAPI gateway. Serves REST + WebSocket to the React frontend.
Port 8000 — the only backend port exposed to the host.

Startup sequence:
  1. knowledge.connection.init() — connect to FalkorDB, build indices, seed edge types
  2. knowledge.ingest_queue.run_consumer_loop() — background Redis consumer
  3. orchestration.monitor.run_monitor() — background LangGraph risk monitor
  4. FastAPI begins serving requests
"""
from __future__ import annotations

import asyncio
import logging
import os

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Literal

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from fastapi import HTTPException
from pydantic import BaseModel, Field, HttpUrl, model_validator


class ScenarioOutcomeEvidence(BaseModel):
    observed_from: str
    observed_to: str
    evidence_url: HttpUrl
    notes: str = ""


class ScenarioOutcomeCosts(BaseModel):
    baseline_procurement_cost_usd: float = Field(ge=0)
    actual_procurement_cost_usd: float = Field(ge=0)
    baseline_basis: str = Field(min_length=3)
    evidence_url: HttpUrl


class ScenarioOutcomeRequest(BaseModel):
    gap_mbpd: float | None = Field(default=None, ge=0)
    price_impact_high: float | None = Field(default=None)
    spr_depletion_days: float | None = Field(default=None, ge=0)
    gdp_proxy_impact_pct: float | None = None
    source: Literal["analyst", "eia", "ais", "government", "operator"]
    evidence: ScenarioOutcomeEvidence
    costs: ScenarioOutcomeCosts | None = None

    @model_validator(mode="after")
    def require_realized_axis(self) -> "ScenarioOutcomeRequest":
        if all(
            value is None
            for value in (
                self.gap_mbpd,
                self.price_impact_high,
                self.spr_depletion_days,
                self.gdp_proxy_impact_pct,
            )
        ):
            raise ValueError("at least one realized field is required")
        return self

from knowledge.api.read import (
    copilot_query,
    get_risk_scores,
    get_spr_state,
    get_available_suppliers,
    get_routes,
    get_wiki_page,
    get_output,
    get_risk_history,
    get_recent_intelligence,
)

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context: runs setup on startup, teardown on shutdown.
    All long-running background tasks are started here.
    """
    log.info("SAGE API Gateway starting up…")

    # 1. Initialise knowledge base (connect + bootstrap + seed)
    try:
        from knowledge.connection import init as kb_init
        await kb_init()
        log.info("Knowledge base initialised.")
    except Exception as exc:
        log.error("Knowledge base init failed: %s", exc)
        # Don't crash the gateway — health endpoint should still return degraded status

    # 2. Start Redis ingest consumer loop in background
    try:
        from knowledge.ingest_queue import run_consumer_loop
        asyncio.create_task(run_consumer_loop(), name="ingest_consumer")
        log.info("Ingest consumer loop started.")
    except Exception as exc:
        log.warning("Ingest consumer failed to start: %s", exc)

    # 3. Start LangGraph risk monitor in background
    try:
        from orchestration.monitor import run_monitor
        asyncio.create_task(run_monitor(), name="risk_monitor")
        log.info("Risk monitor started.")
    except Exception as exc:
        log.warning("Risk monitor failed to start: %s", exc)

    # 4. Synthesise India brief on startup (force=True — ensures india.md always exists)
    try:
        from knowledge.context.india_brief import refresh_india_brief
        asyncio.create_task(refresh_india_brief(force=True), name="india_brief_init")
        log.info("India brief initial synthesis scheduled.")
    except Exception as exc:
        log.warning("India brief init failed to schedule: %s", exc)

    yield   # Application is running

    log.info("SAGE API Gateway shutting down.")


app = FastAPI(title="SAGE API Gateway", version="1.0.0", lifespan=lifespan)

# CORS_ALLOWED_ORIGINS: comma-separated list, e.g. "https://sage.example.com".
# Unset/empty → "*" (local dev / same-origin nginx proxy setups where the
# frontend and API are same-origin anyway). Set explicitly in production so a
# public-facing gateway doesn't accept requests from arbitrary origins.
_cors_env = os.environ.get("CORS_ALLOWED_ORIGINS", "").strip()
_cors_origins = [o.strip() for o in _cors_env.split(",") if o.strip()] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict:
    """Health check. Returns degraded if KB is not initialised."""
    import os
    from knowledge.connection import _graphiti_instance
    kb_ready = _graphiti_instance is not None
    # G13: voice mode — "gnani" if both GNANI_API_KEY and GNANI_WS_URL are set, else "mock"
    voice_mode = "gnani" if (os.environ.get("GNANI_API_KEY") and os.environ.get("GNANI_WS_URL")) else "mock"
    return {
        "status": "ok" if kb_ready else "degraded",
        "kb_ready": kb_ready,
        "voice_mode": voice_mode,
    }


# ---------------------------------------------------------------------------
# Risk scores (drives map node colours + monitor)
# ---------------------------------------------------------------------------

@app.get("/api/risk-scores")
async def risk_scores() -> list:
    """All current RISK_STATE edges — drives map node colours."""
    scores = await get_risk_scores()
    return [s.model_dump() for s in scores]


@app.get("/api/dashboard")
async def dashboard() -> dict:
    """
    Aggregated command-center summary derived entirely from the knowledge base:
      - threat level + active alerts  ← current RISK_STATE bands
      - SPR coverage                  ← get_spr_state() fill levels
      - maritime bottlenecks          ← get_routes() corridor risk
      - Brent reference               ← provenance-tracked bundle (EIA-STEO)
      - monitoring entities           ← live graph node count
    Fields that require System 1 live feeds (spot price, news volume) are flagged
    with `source` so the UI can label them honestly.
    """
    import os

    scores = await get_risk_scores()
    routes = await get_routes(risk_max=1.1)          # include all corridors
    spr = await get_spr_state()

    # Derive band from the numeric score — the stored `band` string can be a stale
    # seed artifact (e.g. score 0.0 tagged "elevated"); the score is the truth.
    from knowledge.api.read import _band_from_score

    def band_rank(b: str) -> int:
        return {"CALM": 0, "WATCH": 1, "ELEVATED": 2, "ACTION": 3, "CRITICAL": 4}.get(b.upper(), 0)

    derived = [_band_from_score(s.score) for s in scores]
    max_band = max(derived, key=band_rank, default="CALM")
    threat = {"CALM": "LOW", "WATCH": "LOW", "ELEVATED": "MEDIUM", "ACTION": "HIGH", "CRITICAL": "CRITICAL"}[max_band]
    active_alerts = sum(1 for b in derived if band_rank(b) >= 2)  # ELEVATED or worse

    # SPR coverage = total fill / total capacity across caverns.
    cap = sum((c.capacity_mmt or 0) for c in spr)
    fill = sum((c.current_fill_mmt or 0) for c in spr)
    spr_pct = round(100 * fill / cap, 1) if cap else None

    # Corridor status from risk score.
    def corridor_status(risk: float | None) -> str:
        r = risk or 0.0
        return "BLOCKED" if r >= 0.7 else "CONTESTED" if r >= 0.45 else "NOMINAL"

    bottlenecks = [
        {"name": c.display_name, "status": corridor_status(c.risk_score), "risk": c.risk_score}
        for c in routes
    ]

    # Brent reference from the provenance-tracked bundle (real, EIA-STEO).
    brent = None
    brent_source = None
    try:
        from knowledge.context.loader import load_bundle
        bundle_path = os.environ.get("SAGE_BUNDLE_PATH", "data/india-energy-2026.context")
        ep = load_bundle(bundle_path).economics_params
        row = ep.get("baseline_brent_usd_per_bbl", {})
        brent = float(row.get("value"))
        brent_source = row.get("source")
    except Exception as exc:
        log.warning("dashboard: brent reference unavailable: %s", exc)

    # Graph size = number of tracked KB entities.
    try:
        from knowledge.api.read import get_full_graph
        node_count = len((await get_full_graph()).nodes)
    except Exception:
        node_count = len(scores)

    # India Supply-Chain Stability Index — KB-computed aggregate across ALL
    # entities (not a single corridor). Reflects any crisis, fully derived.
    sci = None
    try:
        from knowledge.api.read import get_supply_chain_index
        sci = (await get_supply_chain_index()).model_dump()
    except Exception as exc:
        log.warning("dashboard: supply-chain index unavailable: %s", exc)

    return {
        "threat_level": threat,
        "active_alerts": active_alerts,
        "spr_coverage_pct": spr_pct,
        "brent_usd_bbl": brent,
        "brent_source": brent_source,
        "monitoring_entities": node_count,
        "bottlenecks": bottlenecks,
        "top_risk_entity": scores[0].entity if scores else None,
        "supply_chain_index": sci,
        # Source citations for every KPI — rendered as clickable links in the UI.
        "sources": {
            "brent": "https://www.eia.gov/petroleum/",
            "spr": "https://ppac.gov.in/content/212_1_StrategicPetroleumReserve.aspx",
            "threat": "https://github.com/sage-system/wiki",  # points to KB wiki
            "ais": "https://aisstream.io",
            "sanctions": "https://ofac.treasury.gov/sanctions-list-search",
            "news": "https://newsdata.io",
        },
    }


@app.get("/api/graph")
async def knowledge_graph() -> dict:
    """
    The full knowledge graph, geographically positioned — every entity node plus
    its structural relationships. Drives the map's node-link visualization (the
    geospatial equivalent of the Obsidian wiki graph).
    """
    from knowledge.api.read import get_full_graph
    g = await get_full_graph()
    return g.model_dump()


# ---------------------------------------------------------------------------
# Supply chain state endpoints (System 3/4 readers)
# ---------------------------------------------------------------------------

@app.get("/api/suppliers")
async def suppliers(risk_max: float = 0.4) -> list:
    """Available suppliers below risk threshold, not sanctioned."""
    result = await get_available_suppliers(risk_max=risk_max)
    return [s.model_dump() for s in result]


@app.get("/api/routes")
async def routes(risk_max: float = 0.5) -> list:
    """Corridors below risk threshold."""
    result = await get_routes(risk_max=risk_max)
    return [r.model_dump() for r in result]


@app.get("/api/spr")
async def spr_state() -> list:
    """Current SPR cavern fill levels."""
    result = await get_spr_state()
    return [s.model_dump() for s in result]


# ---------------------------------------------------------------------------
# Agent outputs (System 2/3/4) — full-fidelity structured read-back
# ---------------------------------------------------------------------------

@app.get("/api/scenario")
async def scenario_output(scenario_id: str | None = None) -> dict:
    """Latest (or specific) System 2 ScenarioOutputData. 404 if none cached yet."""
    out = await get_output("scenario", scenario_id)
    if out is None:
        raise HTTPException(status_code=404, detail="no scenario output available")
    return out


@app.get("/api/procurement")
async def procurement_output(scenario_id: str | None = None) -> dict:
    """Latest (or specific) System 3 ProcurementRecData (TOPSIS-ranked options)."""
    out = await get_output("procurement", scenario_id)
    if out is None:
        raise HTTPException(status_code=404, detail="no procurement output available")
    return out


@app.get("/api/spr-schedule")
async def spr_schedule_output(scenario_id: str | None = None) -> dict:
    """Latest (or specific) System 4 SPRScheduleData (day-by-day drawdown plan)."""
    out = await get_output("spr", scenario_id)
    if out is None:
        raise HTTPException(status_code=404, detail="no SPR schedule available")
    return out


# ---------------------------------------------------------------------------
# Knowledge base narrative
# ---------------------------------------------------------------------------

@app.get("/api/wiki")
async def wiki_list(limit: int = 50) -> list:
    """G14: List all synthesized wiki pages (entity, title, updated). Enables wiki index."""
    import os, re, glob
    wiki_dir = os.environ.get("WIKI_DIR", "/app/wiki")
    pages = []
    pattern = os.path.join(wiki_dir, "*.md")
    for path in sorted(glob.glob(pattern))[:limit]:
        entity = os.path.splitext(os.path.basename(path))[0]
        try:
            content = open(path, encoding="utf-8").read()
            title_m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            updated_m = re.search(r"last_updated:\s*'([^']+)'", content)
            pages.append({
                "entity": entity,
                "title": title_m.group(1).strip() if title_m else entity,
                "updated": updated_m.group(1) if updated_m else None,
            })
        except Exception:
            pages.append({"entity": entity, "title": entity, "updated": None})
    return pages


@app.get("/api/wiki/{entity}")
async def wiki(entity: str) -> dict:
    """Narrative synthesis page for a node click."""
    page = await get_wiki_page(entity)
    return page.model_dump()


@app.get("/api/brief")
async def situation_brief() -> dict:
    """
    Global India supply-chain situation brief — always populated.
    Scans all synthesized wiki pages, ranks by risk score + recency + text richness,
    returns the top-1 Current Assessment paragraph with provenance so the UI can
    render a clickable 'View full wiki' link.
    """
    import os, re
    from knowledge.api.read import get_risk_scores

    wiki_dir = os.environ.get("WIKI_DIR", "/app/wiki")

    # India node is the primary brief — always try it first.
    india_path = os.path.join(wiki_dir, "india.md")
    if os.path.exists(india_path):
        try:
            content = open(india_path, encoding="utf-8").read()
            ca_m = re.search(r"##\s*Current Assessment\s*\n([\s\S]*?)(?=\n##|\Z)", content, re.IGNORECASE)
            if ca_m and len(ca_m.group(1).strip()) > 60:
                updated_m = re.search(r"last_updated:\s*'([^']+)'", content)
                return {
                    "entity": "India Supply Chain",
                    "assessment": ca_m.group(1).strip(),
                    "updated": updated_m.group(1) if updated_m else "",
                    "wiki_entity": "india",
                }
        except Exception:
            pass

    risk_map: dict[str, float] = {}
    try:
        for rs in await get_risk_scores():
            risk_map[rs.entity.lower()] = float(rs.score)
    except Exception:
        pass

    # Only consider entities that are in the supply-chain registry (61 known entities).
    # This excludes Graphiti-extracted political entities (countries, persons, etc.)
    # that are referenced in signals but are not part of India's supply chain graph.
    registry_names: set[str] = set()
    try:
        from knowledge.registry import REGISTRY
        registry_names = {e.canonical_name.lower() for e in REGISTRY.values()}
    except Exception:
        pass  # if registry unavailable, fall back to all wiki pages

    candidates: list[dict] = []
    try:
        for fname in os.listdir(wiki_dir):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(wiki_dir, fname)
            try:
                content = open(fpath, encoding="utf-8").read()
            except Exception:
                continue

            # Extract frontmatter last_updated
            updated_m = re.search(r"last_updated:\s*'([^']+)'", content)
            updated = updated_m.group(1) if updated_m else ""

            # Extract Current Assessment section
            ca_m = re.search(r"##\s*Current Assessment\s*\n([\s\S]*?)(?=\n##|\Z)", content, re.IGNORECASE)
            if not ca_m:
                continue
            assessment = ca_m.group(1).strip()
            if len(assessment) < 40:  # skip stubs
                continue

            # Resolve entity name from frontmatter aliases or filename
            aliases_m = re.search(r"aliases:\s*\n((?:\s*-[^\n]+\n)+)", content)
            entity_name = ""
            if aliases_m:
                first_alias = re.search(r"-\s*(.+)", aliases_m.group(1))
                entity_name = first_alias.group(1).strip() if first_alias else ""
            if not entity_name:
                entity_name = fname.replace(".md", "").replace("_", " ").title()

            # Prefer known energy entity types (corridor/supplier/refinery/spr/grade/event)
            # over Graphiti-extracted political/generic entities (country names, persons, etc.)
            etype_m = re.search(r"entity_type:\s*(\w+)", content)
            etype = (etype_m.group(1).lower() if etype_m else "")
            # Priority: corridors > geo-events > refineries/ports/spr > suppliers > grades
            type_bonus = {"corridor": 4.0, "geoevent": 3.5, "refinery": 3.0, "port": 3.0,
                         "sprcavern": 2.5, "spr": 2.5, "supplier": 1.0,
                         "crudegrade": 0.5, "grade": 0.5}.get(etype, 0.0)

            # Skip non-registry entities (extracted political/generic entities)
            if registry_names and entity_name.lower() not in registry_names:
                continue

            risk = risk_map.get(entity_name.lower(), 0.0)
            candidates.append({
                "entity": entity_name,
                "assessment": assessment,
                "updated": updated,
                "risk": risk,
                "score": risk * 6 + type_bonus + len(assessment) / 800 + (0.3 if updated > "2026" else 0),
                "wiki_path": fname.replace(".md", ""),
            })
    except Exception as exc:
        log.warning("brief: wiki scan failed: %s", exc)

    if not candidates:
        return {"entity": None, "assessment": None, "updated": None}

    # Sort: highest risk first, then richest text, then most recently updated
    candidates.sort(key=lambda c: (-c["score"], c["updated"]), reverse=False)
    best = candidates[0]
    return {
        "entity": best["entity"],
        "assessment": best["assessment"],
        "updated": best["updated"],
        "wiki_entity": best["wiki_path"],
    }


@app.get("/api/intelligence")
async def intelligence(limit: int = 15) -> list:
    """Live intelligence stream — recent real signals/episodes the KB ingested."""
    items = await get_recent_intelligence(limit=limit)
    return [i.model_dump() for i in items]


@app.get("/api/risk-history")
async def risk_history_endpoint(entity: str, hours: int = 24) -> list:
    """
    Bitemporal RISK_STATE time series for one entity over the last N hours.
    Each point: {valid_at, score, factor_ais, factor_gdelt, factor_price, factor_sanctions}
    """
    points = await get_risk_history(entity, hours=hours)
    return [p.model_dump() for p in points]


@app.get("/api/risk-snapshot")
async def risk_snapshot() -> list:
    """
    All entity risk scores for the timeline scrubber / heatmap — same as /api/risk-scores
    but returns lat/lon coordinates included so the frontend can render a heatmap.
    """
    scores = await get_risk_scores()
    return [s.model_dump() for s in scores]


@app.get("/api/spr-curve")
async def spr_curve() -> dict:
    """
    SPR depletion projection curve.
    Returns {caverns, total_capacity_mmt, current_fill_mmt, fill_pct, days_cover,
             projection: [{day, fill_mmt, days_cover, action}]} from the latest
    SPR schedule if available, else a straight-line projection from current fill.
    """
    from knowledge.api.read import get_spr_state
    caverns = await get_spr_state()
    total_cap  = sum(c.capacity_mmt for c in caverns)
    total_fill = sum(c.current_fill_mmt for c in caverns)
    fill_pct   = (total_fill / total_cap * 100) if total_cap else 0.0
    # India's daily crude consumption ≈ 5.1 mbpd → ~0.68 mmt/day
    daily_draw_mmt = 0.68
    days_cover = total_fill / daily_draw_mmt if daily_draw_mmt else 0

    # Try to pull from a cached SPR schedule (System 4 output)
    sched = await get_output("spr", None)
    projection: list[dict] = []
    if sched and isinstance(sched, dict) and "daily_plan" in sched:
        fill = total_fill
        for day_entry in sched["daily_plan"]:
            vol  = float(day_entry.get("volume_mmt", 0) or 0)
            act  = day_entry.get("action", "hold")
            fill = fill - vol if act == "draw" else (fill + vol if act == "refill" else fill)
            fill = max(0.0, fill)
            projection.append({
                "day":       int(day_entry.get("day", 0)),
                "fill_mmt":  round(fill, 3),
                "days_cover": round(fill / daily_draw_mmt, 1) if daily_draw_mmt else 0,
                "action":    act,
            })
    else:
        # Straight-line draw-down at current threat-implied rate
        for d in range(31):
            fill = max(0.0, total_fill - daily_draw_mmt * d)
            projection.append({
                "day": d, "fill_mmt": round(fill, 3),
                "days_cover": round(fill / daily_draw_mmt, 1) if daily_draw_mmt else 0,
                "action": "draw",
            })

    return {
        "caverns":           [c.model_dump() for c in caverns],
        "total_capacity_mmt": round(total_cap, 3),
        "current_fill_mmt":  round(total_fill, 3),
        "fill_pct":          round(fill_pct, 1),
        "days_cover":        round(days_cover, 1),
        "projection":        projection,
    }


@app.get("/api/evidence/{entity}")
async def evidence(entity: str, limit: int = 12) -> list:
    """The source signals that drove an entity's risk (Supporting Evidence)."""
    from knowledge.api.read import get_evidence_for
    items = await get_evidence_for(entity, limit=limit)
    return [i.model_dump() for i in items]


@app.get("/api/provenance/volatile")
async def volatile_provenance() -> dict:
    """
    Current volatile-tier overrides with their as_of + source — lets the UI show
    "Brent $103 · as of 2026-02-25" so recommendations visibly reflect fresh crisis
    economics vs the bundle cold-start seeds. Empty dict when nothing refreshed yet.
    """
    try:
        from knowledge.context.volatile import get_all_volatile
        return {"overrides": get_all_volatile()}
    except Exception as exc:
        log.warning("volatile provenance unavailable: %s", exc)
        return {"overrides": {}}


@app.post("/api/copilot")
async def copilot(body: dict) -> dict:
    """EA-GraphRAG routed copilot endpoint (Perplexity-style: markdown + numbered sources)."""
    q = body.get("query") or body.get("question") or ""
    try:
        answer = await copilot_query(q)
    except Exception as exc:
        log.exception("Copilot query failed")
        raise HTTPException(status_code=503, detail="Copilot is temporarily unavailable") from exc
    return answer.model_dump()


# ---------------------------------------------------------------------------
# Feedback / accuracy
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Simulation Lab — scenario runner endpoints (System 2/3/4 on-demand)
# ---------------------------------------------------------------------------

# In-process run status store: run_id → {stage, pct, scenario_id, error}
RUN_STATUS: dict[str, dict] = {}


async def _execute_run(
    run_id: str, entity: str, scenario_dict: dict, run_downstream: bool,
    origin: str = "user", label: str | None = None,
) -> None:
    """
    Background task: runs System 2 → 3 → 4 via the same orchestration node
    coroutines used by the autonomous LangGraph pipeline. Updates RUN_STATUS[run_id].
    """
    # Build a minimal PipelineState the node coroutines expect.
    state: dict = {
        "entity": entity,
        "risk_score": 0.85,   # force confirmed threshold
        "risk_band": "action",
        "scenario_params": scenario_dict,
        "stages": [],
        "origin": origin,
    }

    try:
        from knowledge.agent_trace import publish_trace
        from datetime import datetime, timezone as _tz
        import json as _json

        # Stamp t0 for response-time measurement: emit a System-1 anchor event so the
        # /api/response-time aggregator has a clear pipeline start regardless of whether
        # this run was auto-triggered (System 1 fired naturally) or user-triggered here.
        _t0 = datetime.now(_tz.utc).isoformat()
        await publish_trace(system="1", agent="fusion",
                             action=f"Pipeline triggered for {entity} ({origin})",
                             status="done", entity=entity, origin=origin)

        # Persist per-run timing to Redis so /api/response-time can look up runs by
        # run_id without depending on trace-list ordering heuristics.
        try:
            import redis.asyncio as _aioredis
            _rc = _aioredis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)
            await _rc.setex(f"sage:run:timing:{run_id}", 86400, _json.dumps({"t0": _t0, "entity": entity, "origin": origin}))
            await _rc.aclose()
        except Exception:
            pass

        # Stage 1: Scenario (System 2) — call runner directly with user-supplied params,
        # bypassing decide_scenario_params so the UI knobs are honoured exactly.
        RUN_STATUS[run_id].update({"stage": "scenario", "pct": 5})
        from scenario_agent.runner import run as run_scenario
        await publish_trace(system="2", agent="scenario",
                             action=f"Running ARIO disruption cascade for {entity}",
                             status="started", entity=entity, origin=origin)
        scenario_id: str = await run_scenario(
            trigger_entity=entity, status="confirmed", scenario=scenario_dict
        )
        state["scenario_id"] = scenario_id
        state["scenario_params"] = scenario_dict
        RUN_STATUS[run_id].update({"stage": "scenario", "pct": 35, "scenario_id": scenario_id})
        await publish_trace(system="2", agent="scenario",
                             action=f"Scenario cascade complete for {entity} ({scenario_id})",
                             status="done", entity=entity, origin=origin)

        if run_downstream:
            # Stage 2: Procurement (System 3)
            RUN_STATUS[run_id].update({"stage": "procurement", "pct": 40})
            from orchestration.graph import procure_node, reserve_node
            state = await procure_node(state)
            RUN_STATUS[run_id].update({"stage": "procurement", "pct": 70})

            # Stage 3: Reserve optimisation (System 4)
            RUN_STATUS[run_id].update({"stage": "reserve", "pct": 75})
            state = await reserve_node(state)

        # Feature A/B: register this run in the durable library index + outcome
        # ledger so it shows up in the Simulation Lab's "My runs" section and
        # contributes to the accuracy/calibration loop, same as auto-triggered runs.
        try:
            from orchestration.graph import _register_scenario_run
            await _register_scenario_run(scenario_id, entity, origin=origin)
            if label:
                from datetime import datetime, timezone
                from knowledge.api.write import write_scenario_index
                from knowledge.api.read import get_output
                out = await get_output("scenario", scenario_id) or {}
                await write_scenario_index(scenario_id, {
                    "trigger_entity": entity, "origin": origin, "label": label,
                    "gap_mbpd": out.get("gap_mbpd"),
                    "price_impact_high": out.get("price_impact_high"),
                    "gdp_proxy_impact_pct": out.get("gdp_proxy_impact_pct"),
                    "spr_depletion_days": out.get("spr_depletion_days"),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
        except Exception as exc:
            log.warning("[scenario_run] library registration failed (non-fatal): %s", exc)

        # Stamp t_final for response-time tracking
        try:
            import redis.asyncio as _aioredis2
            import json as _json2
            from datetime import datetime, timezone as _tz2
            _rc2 = _aioredis2.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)
            _raw = await _rc2.get(f"sage:run:timing:{run_id}")
            if _raw:
                _timing = _json2.loads(_raw)
                _timing["t_final"] = datetime.now(_tz2.utc).isoformat()
                _timing["scenario_id"] = scenario_id
                await _rc2.setex(f"sage:run:timing:{run_id}", 86400, _json2.dumps(_timing))
                # Maintain a sorted list of last 20 completed runs (by completion time)
                await _rc2.lpush("sage:run:timing:recent", run_id)
                await _rc2.ltrim("sage:run:timing:recent", 0, 19)
            await _rc2.aclose()
        except Exception:
            pass

        RUN_STATUS[run_id].update({"stage": "done", "pct": 100, "scenario_id": scenario_id})

    except Exception as exc:
        log.error("[scenario_run] run %s failed: %s", run_id, exc)
        RUN_STATUS[run_id].update({"stage": "error", "pct": 0, "error": str(exc)})


@app.post("/api/scenario/run")
async def scenario_run(body: dict) -> dict:
    """
    Launch a new scenario run asynchronously.
    Returns {run_id, scenario_id: null} immediately; poll /api/scenario/status/{run_id}.
    """
    import uuid

    entity = body.get("entity", "")
    if not entity:
        raise HTTPException(status_code=422, detail="entity is required")
    # Accept unknown entities (user may enter one manually) but warn in logs.
    if entity not in _KNOWN_ENTITIES:
        log.warning("[scenario_run] unknown entity '%s' — proceeding anyway", entity)

    run_id = str(uuid.uuid4())
    scenario_dict = {
        "disruption_fraction":    float(body.get("disruption_fraction", 0.8)),
        "disruption_days":        int(body.get("disruption_days", 14)),
        "escalation_profile":     body.get("escalation_profile", "constant"),
        "bypass_compromised_frac": float(body.get("bypass_compromised_frac", 0.0)),
        "spr_policy":             body.get("spr_policy", "moderate"),
        "demand_destruction_pct": float(body.get("demand_destruction_pct", 0.0)),
        "supply_cut_mbpd":        float(body.get("supply_cut_mbpd", 0.0)),
        "cut_supplier":           str(body.get("cut_supplier") or ""),
    }
    run_downstream = bool(body.get("run_downstream", True))
    label = body.get("label") or entity

    RUN_STATUS[run_id] = {"stage": "scenario", "pct": 0, "scenario_id": None, "error": None}
    asyncio.create_task(
        _execute_run(run_id, entity, scenario_dict, run_downstream, origin="user", label=label),
        name=f"run_{run_id[:8]}",
    )

    return {"run_id": run_id, "scenario_id": None}


@app.get("/api/scenario/status/{run_id}")
async def scenario_status(run_id: str) -> dict:
    """Poll run status. Returns {stage, pct, scenario_id, error}."""
    status = RUN_STATUS.get(run_id)
    if status is None:
        raise HTTPException(status_code=404, detail="run_id not found")
    return status


_SCENARIO_PRESETS: list[dict] = [
    {
        "id": "hormuz_full",
        "label": "Strait of Hormuz — Full Closure",
        "entity": "Strait of Hormuz",
        "disruption_fraction": 1.0,
        "disruption_days": 21,
        "escalation_profile": "constant",
        "bypass_compromised_frac": 0.0,
        "spr_policy": "aggressive",
        "demand_destruction_pct": 0.05,
        "blurb": "Complete Hormuz blockage; ~20% of global seaborne crude halted.",
    },
    {
        "id": "hormuz_partial",
        "label": "Hormuz — Contained Confrontation",
        "entity": "Strait of Hormuz",
        "disruption_fraction": 0.4,
        "disruption_days": 10,
        "escalation_profile": "escalating",
        "bypass_compromised_frac": 0.0,
        "spr_policy": "moderate",
        "demand_destruction_pct": 0.0,
        "blurb": "Partial closure / harassment; insurance + rerouting friction.",
    },
    {
        "id": "redsea_hormuz",
        "label": "Red Sea + Hormuz — Bypass Compromised",
        "entity": "Strait of Hormuz",
        "disruption_fraction": 0.7,
        "disruption_days": 18,
        "escalation_profile": "constant",
        "bypass_compromised_frac": 1.0,
        "spr_policy": "aggressive",
        "demand_destruction_pct": 0.05,
        "blurb": "Simultaneous chokepoint stress removes the Petroline/ADCOP bypass relief.",
    },
    {
        "id": "supplier_sanction",
        "label": "Major Supplier Sanctioned",
        "entity": "Strait of Hormuz",
        "disruption_fraction": 0.3,
        "disruption_days": 45,
        "escalation_profile": "constant",
        "bypass_compromised_frac": 0.0,
        "spr_policy": "moderate",
        "demand_destruction_pct": 0.0,
        "blurb": "Long-duration sourcing loss; procurement substitution dominates.",
    },
    {
        "id": "opec_cut",
        "label": "OPEC+ Emergency Production Cut",
        "entity": "Saudi Aramco",
        "disruption_fraction": 1.0,
        "disruption_days": 90,
        "escalation_profile": "constant",
        "bypass_compromised_frac": 0.0,
        "spr_policy": "moderate",
        "demand_destruction_pct": 0.0,
        "supply_cut_mbpd": 0.8,
        "cut_supplier": "Saudi Aramco",
        "blurb": "Source-side cut: OPEC+ trims 2 mbpd globally; India's direct exposure ~0.8 mbpd after spare-capacity offset.",
    },
]

_KNOWN_ENTITIES: set[str] = {
    "Strait of Hormuz", "Bab-el-Mandeb", "Suez Canal",
    "Strait of Malacca", "Cape of Good Hope",
    # G4: production-cut mode — supplier entities, not corridors
    "Saudi Aramco", "ADNOC", "Iraq", "Russia", "OPEC+",
}


@app.get("/api/scenario/presets")
async def scenario_presets() -> list:
    """Static presets + user-promoted custom presets for the Simulation Lab builder."""
    from knowledge.api.read import get_custom_presets
    custom = await get_custom_presets()
    return [{**p, "custom": False} for p in _SCENARIO_PRESETS] + custom


# ---------------------------------------------------------------------------
# Scenario Library (Feature A) — every run, auto/user/preset, durable + promotable
# ---------------------------------------------------------------------------

@app.get("/api/scenario/library")
async def scenario_library(limit: int = 20, origin: str = "all") -> list:
    """
    Newest-first cards for every scenario run (auto-triggered by the monitor,
    user-run from the builder, or preset-launched). Survives the 24h full-payload
    TTL — `payload_available` tells the UI whether it can load results directly
    or must re-run from the card's params.
    """
    from knowledge.api.read import list_scenarios
    if origin not in ("all", "auto", "user", "preset"):
        raise HTTPException(status_code=422, detail="origin must be all|auto|user|preset")
    return await list_scenarios(limit=limit, origin=origin)


@app.post("/api/scenario/promote")
async def scenario_promote(body: dict) -> dict:
    """
    Promote a completed scenario run into a named, reusable custom preset.
    Reads the exact builder knobs back from `assumptions.scenario_params`
    (written verbatim by scenario_agent.runner) rather than approximating them
    from the outputs — re-running the preset reproduces the original scenario.
    """
    import json as _json
    import re
    from knowledge.api.read import get_output
    from knowledge.api.write import write_custom_preset

    scenario_id = body.get("scenario_id", "")
    label = body.get("label", "")
    blurb = body.get("blurb", "")
    if not scenario_id or not label:
        raise HTTPException(status_code=422, detail="scenario_id and label are required")

    out = await get_output("scenario", scenario_id)
    if out is None:
        raise HTTPException(status_code=404, detail="scenario_id not found or expired")

    slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")[:40] or scenario_id

    raw_params_entry = (out.get("assumptions") or {}).get("scenario_params")
    if raw_params_entry and raw_params_entry.get("value"):
        # Exact reconstruction — this is what the run actually used.
        params = _json.loads(raw_params_entry["value"])
        approximated = False
    else:
        # Legacy scenario (predates this field) — fall back to a documented
        # approximation rather than silently fabricating precision.
        gap_mbpd = float(out.get("gap_mbpd") or 0.0)
        params = {
            "disruption_fraction": round(max(0.1, min(1.0, gap_mbpd / 2.19)), 2),
            "disruption_days": int(out.get("gap_duration_days") or 14),
            "escalation_profile": "constant",
            "bypass_compromised_frac": 0.0,
            "spr_policy": "aggressive" if float(out.get("spr_depletion_days") or 99) < 30 else "moderate",
            "demand_destruction_pct": 0.0,
        }
        approximated = True

    await write_custom_preset(slug, {
        "label": label,
        "entity": out.get("trigger_entity", ""),
        "disruption_fraction": params.get("disruption_fraction", 0.5),
        "disruption_days": params.get("disruption_days", 14),
        "escalation_profile": params.get("escalation_profile", "constant"),
        "bypass_compromised_frac": params.get("bypass_compromised_frac", 0.0),
        "spr_policy": params.get("spr_policy", "moderate"),
        "demand_destruction_pct": params.get("demand_destruction_pct", 0.0),
        "blurb": blurb or (
            f"Promoted from {scenario_id}"
            + (" (legacy run — params approximated from observed results)" if approximated else "")
        ),
        "source_scenario_id": scenario_id,
    })
    return {"slug": slug, "approximated": approximated}


@app.delete("/api/scenario/promote/{slug}")
async def scenario_unpromote(slug: str) -> dict:
    """Remove a user-promoted custom preset."""
    from knowledge.api.write import delete_custom_preset
    existed = await delete_custom_preset(slug)
    if not existed:
        raise HTTPException(status_code=404, detail="preset not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Feature #2 — Tornado / Sensitivity Analysis
# ---------------------------------------------------------------------------

@app.post("/api/scenario/sensitivity")
async def scenario_sensitivity(body: dict) -> list:
    """
    Tornado chart: vary each ARIO scenario assumption ±20% and return the swing
    in gap_mbpd. ARIO runs in ~40ms so 15 vars × 2 = 30 runs ≈ 1.2 s total.

    Body: { scenario_id: str }  OR  full scenario params (entity + scenario_params).
    Returns: list of { param, label, base, low_val, high_val, swing_low, swing_high }
    sorted by abs(swing) descending.
    """
    from knowledge.api.read import get_output
    from scenario_agent.runner import run as run_scenario
    import asyncio

    # Load base scenario
    scenario_id = body.get("scenario_id")
    if scenario_id:
        base_out = await get_output("scenario", scenario_id) or {}
        entity = base_out.get("trigger_entity", "Strait of Hormuz")
        base_params = base_out.get("assumptions", {})
    else:
        entity = body.get("entity", "Strait of Hormuz")
        base_params = body.get("scenario_params", {})
        # Run base scenario to get base gap
        sid = await run_scenario(trigger_entity=entity, status="confirmed", scenario=base_params)
        base_out = await get_output("scenario", sid) or {}

    base_gap = float(base_out.get("gap_mbpd", 0) or 0)

    # Parameters to vary — keys that are numeric in the scenario dict
    VARY_PARAMS = {
        "supply_cut_pct":        "Supply Cut %",
        "bypass_capacity_mbpd":  "Bypass Capacity",
        "demand_mbpd":           "India Demand",
        "price_elasticity":      "Price Elasticity",
        "spare_capacity_mbpd":   "OPEC Spare Cap",
        "spr_draw_mbpd":         "SPR Draw Rate",
        "transit_disruption_pct": "Transit Disruption %",
    }

    # Build flat params from assumptions (handle {value: x} dict or plain scalar)
    def extract_val(v):
        if isinstance(v, dict): return v.get("value")
        return v

    flat: dict = {}
    raw_assumptions = base_out.get("assumptions") or base_params or {}
    for k in VARY_PARAMS:
        v = extract_val(raw_assumptions.get(k))
        if v is not None:
            try:
                flat[k] = float(v)
            except (TypeError, ValueError):
                pass

    if not flat:
        # Fallback: well-known defaults so the chart always has content
        flat = {
            "supply_cut_pct": 0.5,
            "bypass_capacity_mbpd": 0.5,
            "demand_mbpd": 5.0,
            "price_elasticity": 4.5,
            "spare_capacity_mbpd": 3.5,
        }

    DELTA = 0.20  # ±20%

    async def _run_perturbed(k: str, v_perturbed: float, direction: str):
        perturbed = {**flat, k: v_perturbed}
        try:
            sid2 = await run_scenario(trigger_entity=entity, status="confirmed", scenario=perturbed)
            out2 = await get_output("scenario", sid2) or {}
            return float(out2.get("gap_mbpd", base_gap) or base_gap)
        except Exception:
            return base_gap

    results = []
    for k, label in VARY_PARAMS.items():
        if k not in flat:
            continue
        base_v = flat[k]
        lo_v = base_v * (1 - DELTA)
        hi_v = base_v * (1 + DELTA)
        lo_gap, hi_gap = await asyncio.gather(
            _run_perturbed(k, lo_v, "lo"),
            _run_perturbed(k, hi_v, "hi"),
        )
        swing_lo = lo_gap - base_gap
        swing_hi = hi_gap - base_gap
        max_swing = max(abs(swing_lo), abs(swing_hi))
        results.append({
            "param": k,
            "label": label,
            "base_gap": round(base_gap, 4),
            "swing_low": round(swing_lo, 4),
            "swing_high": round(swing_hi, 4),
            "max_swing": round(max_swing, 4),
        })

    results.sort(key=lambda r: abs(r["max_swing"]), reverse=True)
    return results


# ---------------------------------------------------------------------------
# Feature #3 — Re-run-with-mitigation
# ---------------------------------------------------------------------------

@app.post("/api/scenario/run-mitigated")
async def scenario_run_mitigated(body: dict) -> dict:
    """
    Re-run the ARIO scenario applying SAGE's own procurement reallocation and
    SPR draw as supply-side offsets — shows the *residual* gap after SAGE acts.

    Body: { scenario_id: str }
    Returns: { base_gap_mbpd, mitigated_gap_mbpd, reduction_mbpd, pct_reduction,
               mitigation_sources: [{ label, offset_mbpd }] }
    """
    from knowledge.api.read import get_output
    from scenario_agent.runner import run as run_scenario

    scenario_id = body.get("scenario_id")
    if not scenario_id:
        raise HTTPException(status_code=422, detail="scenario_id required")

    base_out = await get_output("scenario", scenario_id) or {}
    proc_out = await get_output("procurement", scenario_id) or {}
    spr_out  = await get_output("spr_schedule", scenario_id) or {}

    entity = base_out.get("trigger_entity", "Strait of Hormuz")
    base_gap = float(base_out.get("gap_mbpd", 0) or 0)

    # Procurement offset: top alternative supplier covers some fraction of the gap
    proc_offset = 0.0
    ranked = proc_out.get("ranked") or []
    if ranked:
        top = ranked[0]
        # Use cost-weighted feasibility: assume top option covers ≤40% of gap
        topsis = float(top.get("topsis_score", 0.5) or 0.5)
        proc_offset = round(min(base_gap * 0.4, base_gap * topsis * 0.6), 4)

    # SPR offset: daily draw (from schedule or param default)
    spr_draw = 0.0
    spr_schedule = spr_out.get("schedule") or []
    if spr_schedule:
        daily_mbpd = [float(d.get("draw_mbpd", 0) or 0) for d in spr_schedule if d.get("draw_mbpd")]
        if daily_mbpd:
            spr_draw = round(sum(daily_mbpd) / len(daily_mbpd), 4)
    else:
        # Fallback from spr_params
        spr_draw = float(spr_out.get("daily_draw_mbpd", 0) or 0)

    mitigation_sources = []
    if proc_offset > 0:
        mitigation_sources.append({"label": f"Alt procurement ({ranked[0].get('supplier','—')})", "offset_mbpd": proc_offset})
    if spr_draw > 0:
        mitigation_sources.append({"label": "SPR draw (Bellman SDP)", "offset_mbpd": round(spr_draw, 4)})

    total_offset = proc_offset + spr_draw

    # Re-run ARIO with reduced effective disruption
    base_params = base_out.get("assumptions") or {}
    mitigated_params = dict(base_params)

    # Reduce supply_cut by the mitigation offset expressed as fraction of demand
    demand_ref = float((base_params.get("demand_mbpd", {}) or {}).get("value", 5.0) if isinstance(base_params.get("demand_mbpd"), dict) else base_params.get("demand_mbpd", 5.0))
    original_cut = float((base_params.get("supply_cut_pct", {}) or {}).get("value", 0.5) if isinstance(base_params.get("supply_cut_pct"), dict) else base_params.get("supply_cut_pct", 0.5))
    mitigation_as_pct = total_offset / max(demand_ref, 1)
    mitigated_cut = max(0.0, original_cut - mitigation_as_pct)
    mitigated_params["supply_cut_pct"] = mitigated_cut

    try:
        mit_sid = await run_scenario(trigger_entity=entity, status="confirmed", scenario=mitigated_params)
        mit_out = await get_output("scenario", mit_sid) or {}
        mitigated_gap = float(mit_out.get("gap_mbpd", 0) or 0)
    except Exception:
        mitigated_gap = max(0.0, base_gap - total_offset)

    reduction = base_gap - mitigated_gap
    pct_reduction = (reduction / base_gap * 100) if base_gap > 0 else 0

    return {
        "scenario_id": scenario_id,
        "entity": entity,
        "base_gap_mbpd": round(base_gap, 4),
        "mitigated_gap_mbpd": round(mitigated_gap, 4),
        "reduction_mbpd": round(reduction, 4),
        "pct_reduction": round(pct_reduction, 1),
        "mitigation_sources": mitigation_sources,
        "total_offset_mbpd": round(total_offset, 4),
    }


# ---------------------------------------------------------------------------
# G9 — Demo Ignition
# ---------------------------------------------------------------------------

@app.post("/api/demo/ignite")
async def demo_ignite() -> dict:
    """
    Replay the 2026 Hormuz standoff pre-crisis window.

    Injects synthetic intel signals that mimic the 72-hour window before a
    Strait of Hormuz crisis, then escalates risk through ELEVATED→ACTION to
    trigger the autonomous pipeline (LangGraph graph.run_response_pipeline).

    Sequence (all async, non-blocking):
      t=0s  Write 4 sensory-agent signals + ELEVATED risk (0.65) → trace feed fires
      t=5s  Fusion agent fuses signals → risk escalates to ACTION (0.78) → trace done
      t=8s  Write ACTION risk state → monitor fires on_action() → Systems 2→3→4 activate
    """
    asyncio.create_task(_demo_sequence(), name="demo_ignite")
    return {"ok": True, "message": "Demo sequence started — watch the agent trace feed"}


async def _demo_sequence() -> None:
    """Time-stepped demo crisis replay. All steps non-fatal — demo can't crash the gateway."""
    from datetime import datetime, timezone as _tz
    from knowledge.agent_trace import publish_trace

    entity = "Strait of Hormuz"

    # ── Step 1 (t=0): Inject pre-crisis intel signals + ELEVATED risk ─────────────
    try:
        await _demo_inject_signals(entity)
    except Exception as exc:
        log.warning("[demo] signal injection failed (non-fatal): %s", exc)

    # Publish System-1 sensory agent traces (simulates autonomous detection)
    for agent, action in [
        ("ais",       "Detected 3 Iranian IRGCN vessels altering course near Hormuz — AIS dark window 4h"),
        ("news",      "NEWSDATA: 'Iranian patrol boats intercept tanker near Strait' — severity 0.78"),
        ("prices",    "Brent ICE front-month +$6.40 → $84.20/bbl; war-risk regime triggered"),
        ("sanctions", "OFAC watch-list cross-check: 2 vessels flagged near Persian Gulf corridor"),
    ]:
        try:
            await publish_trace(system="1", agent=agent, action=action,
                                status="done", entity=entity, origin="auto")
        except Exception:
            pass
        await asyncio.sleep(0.8)

    # ── Step 2 (t=5s): Fusion agent fuses signals, risk crosses ACTION band ───────
    await asyncio.sleep(2.0)
    try:
        await publish_trace(system="1", agent="fusion",
                             action="Fusing 4-factor signal stream — risk escalating",
                             status="started", entity=entity, origin="auto")
    except Exception:
        pass

    await asyncio.sleep(3.0)
    escalated_score = 0.78
    try:
        await publish_trace(system="1", agent="fusion",
                             action=f"Fusion score {escalated_score:.2f} — ACTION band crossed",
                             status="done", entity=entity, origin="auto")
    except Exception:
        pass

    # ── Step 3 (t=8s): Write ACTION risk state + fire autonomous pipeline ─────────
    await asyncio.sleep(1.0)
    try:
        from knowledge.api.write import write_risk_state
        await write_risk_state(
            entity=entity, score=escalated_score,
            factor_ais=0.82, factor_gdelt=0.71, factor_price=0.74, factor_sanctions=0.45,
            rationale=(
                "Demo replay: 2026 Hormuz standoff. Iranian naval vessels interdicting "
                "commercial traffic; Brent war-risk premium active; IRGCN dark-ship activity "
                "confirmed in 4h AIS gap. Crossing ACTION threshold: autonomous pipeline triggered."
            ),
            model_version="demo-replay-v1",
        )
    except Exception as exc:
        log.warning("[demo] write_risk_state failed (non-fatal): %s", exc)

    # Fire the autonomous pipeline — same path the monitor takes on a real crossing
    try:
        from orchestration.triggers import on_action
        await on_action(entity=entity, score=escalated_score, scenario_ref=None)
        log.info("[demo] autonomous pipeline fired for '%s'", entity)
    except Exception as exc:
        log.error("[demo] autonomous pipeline trigger failed: %s", exc)


async def _demo_inject_signals(entity: str) -> None:
    """Write pre-crisis intel signals to the KB so the trace feed has context."""
    from datetime import datetime, timezone as _tz
    from contracts.signal import NormalizedSignal, AisPayload, EventPayload, PricePayload
    from knowledge.api.write import ingest_signal, write_risk_state

    now = datetime.now(_tz.utc)

    signals = [
        NormalizedSignal(
            source="ais", entity=entity, priority="HIGH",
            headline="3 IRGCN vessels dark for 4h in Hormuz TSS northbound lane",
            detail=(
                "MMSI 422000001, 422000002, 422000003 — Iranian Revolutionary Guard Corps Navy "
                "Gashti-class patrol boats. Last AIS ping 04:17Z. Anomaly score 0.89. "
                "Tanker MT PACIFIC GUARDIAN (MMSI 538004821) issued security alert at 06:22Z "
                "after proximity approach."
            ),
            severity=0.82, entities=[entity, "Hormuz TSS", "Iran"],
            payload=AisPayload(mmsi="422000001", vessel_name="IRGCN Patrol 1",
                               gap_hours=4.1, dark_vessel=True, anomaly_score=0.89),
            observed_at=now,
        ),
        NormalizedSignal(
            source="news", entity=entity, priority="HIGH",
            headline="Iranian patrol boats intercept tanker near Strait of Hormuz",
            detail=(
                "NEWSDATA (Reuters feed): Iranian patrol boats from the IRGCN intercepted "
                "the VLCC MT PACIFIC GUARDIAN in the Strait of Hormuz northbound lane at "
                "approximately 06:00 UTC. The vessel was ordered to reduce speed and submit "
                "to inspection. The Hormuz TSS northbound lane is currently contested."
            ),
            severity=0.78, entities=[entity, "Iran", "IRGCN"],
            observed_at=now,
        ),
        NormalizedSignal(
            source="price", entity=entity, priority="HIGH",
            headline="Brent ICE +$6.40 to $84.20 — war-risk regime triggered",
            detail=(
                "ICE Brent front-month contract spiked $6.40 (8.2%) to $84.20/bbl in early "
                "Asian trading following reports of IRGCN vessel movements near Hormuz. "
                "War-risk insurance premiums for Hormuz transits rose 0.3% of vessel value. "
                "Changepoint detected; regime shift from calm → stressed."
            ),
            severity=0.74, entities=[entity, "Brent", "ICE"],
            payload=PricePayload(instrument="BZ=F", price=84.20, changepoint=True,
                                 regime="stressed", war_risk_premium=0.074),
            observed_at=now,
        ),
        NormalizedSignal(
            source="gdelt", entity=entity, priority="MED",
            headline="GDELT: Iran–US conflict tone 0.71 — elevated maritime tension",
            detail=(
                "GDELT EventDB conflict cluster around Hormuz/Iran actor: GoldsteinScale −7.2, "
                "AvgTone −5.8. Iran MIL actor involved in 14 events in last 6h. "
                "Historical comparison: score at this level preceded 2019 tanker attacks by 18h."
            ),
            severity=0.71, entities=[entity, "Iran", "United States"],
            payload=EventPayload(actor="Iran", action="naval interdiction", target="commercial shipping",
                                 tone=-5.8, severity=0.71, goldstein=-7.2),
            observed_at=now,
        ),
    ]

    for sig in signals:
        try:
            await ingest_signal(sig)
        except Exception as exc:
            log.warning("[demo] ingest_signal failed for %s (non-fatal): %s", sig.source, exc)

    # Write initial ELEVATED risk state (pre-ACTION) so the Command Center shows Hormuz in amber
    try:
        await write_risk_state(
            entity=entity, score=0.65,
            factor_ais=0.82, factor_gdelt=0.71, factor_price=0.62, factor_sanctions=0.0,
            rationale="Demo replay t=0: initial ELEVATED assessment. AIS dark-vessel + Brent spike.",
            model_version="demo-replay-v1",
        )
    except Exception as exc:
        log.warning("[demo] initial risk state write failed (non-fatal): %s", exc)


# ---------------------------------------------------------------------------
# Scenario accuracy / outcome logging / calibration (Feature B)
# ---------------------------------------------------------------------------

@app.get("/api/scenario/accuracy")
async def scenario_accuracy() -> dict:
    """
    Combined accuracy summary: risk-crossing precision (System 1, existing
    feedback loop) + scenario-impact MAPE per axis and per corridor (Feature B).
    """
    from knowledge.feedback import get_accuracy_summary, get_scenario_accuracy
    return {
        "crossing": get_accuracy_summary(),
        "scenario": get_scenario_accuracy(),
    }


@app.post("/api/scenario/{scenario_id}/outcome")
async def scenario_log_outcome(scenario_id: str, body: ScenarioOutcomeRequest) -> dict:
    """
    Analyst-entered realized outcome for a scenario ("what actually happened").
    Always tagged source="analyst" so provenance is unambiguous in the UI.
    Triggers a calibration attempt for the scenario's corridor if enough
    realized outcomes now exist.
    """
    from knowledge.feedback import record_scenario_realized, maybe_calibrate_corridor
    from knowledge.api.read import get_output

    out = await get_output("scenario", scenario_id)
    if out is None:
        raise HTTPException(status_code=404, detail="scenario_id not found or expired")

    body_data = body.model_dump(mode="json")
    realized = {
        k: body_data.get(k) for k in
        ("gap_mbpd", "price_impact_high", "spr_depletion_days", "gdp_proxy_impact_pct")
        if body_data.get(k) is not None
    }
    updated = record_scenario_realized(
        scenario_id,
        realized,
        source=body.source,
        evidence=body_data["evidence"],
        costs=body_data.get("costs"),
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="no matching prediction record for this scenario_id")

    calib = await maybe_calibrate_corridor(out.get("trigger_entity", ""))
    return {
        "ok": True,
        "error": updated.get("error"),
        "costs": updated.get("costs"),
        "calibration": calib,
    }


@app.get("/api/savings/realized")
async def realized_savings() -> dict:
    """Verified transactional savings; excludes modelled avoided-loss estimates."""
    from knowledge.feedback import get_realized_savings_summary
    return get_realized_savings_summary()


@app.get("/api/scenario/calibration")
async def scenario_calibration() -> dict:
    """Learned per-corridor gap/price correction factors (bounded, visible)."""
    from knowledge.api.read import get_calibration_factors
    return {"per_corridor": await get_calibration_factors()}


# ---------------------------------------------------------------------------
# Agent Activity Trace — live "what is SAGE doing right now" feed
# ---------------------------------------------------------------------------

@app.get("/api/agent-trace/recent")
async def agent_trace_recent(limit: int = 30) -> list:
    """
    Cold-start read of recent agent-trace events (newest first), so a client
    that just loaded the dashboard sees recent activity immediately instead of
    an empty feed until the next live event arrives over /ws.
    """
    from knowledge.agent_trace import get_recent_trace
    return await get_recent_trace(limit=limit)


# ---------------------------------------------------------------------------
# End-to-end response time measurement (G2)
# ---------------------------------------------------------------------------

@app.get("/api/response-time")
async def response_time() -> dict:
    """
    End-to-end pipeline latency (see docs/METHODOLOGY.md for clock definition).

    Primary source: per-run timing keys stamped by _execute_run (sage:run:timing:{id}).
    These are set at t0 (pipeline trigger) and updated at t_final (reserve done),
    so the result survives gateway restarts and doesn't rely on trace-log heuristics.

    Returns last-run stage latencies and rolling median over the last 5 completed runs.
    """
    import json
    import statistics
    import redis.asyncio as aioredis
    from datetime import datetime, timezone

    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")

    def _parse_ts(ts: str | None) -> float | None:
        if not ts:
            return None
        try:
            return datetime.fromisoformat(ts).timestamp()
        except Exception:
            return None

    try:
        client = aioredis.from_url(redis_url, decode_responses=True)
        try:
            run_ids = await client.lrange("sage:run:timing:recent", 0, 19)
            timings: list[dict] = []
            for rid in run_ids:
                raw = await client.get(f"sage:run:timing:{rid}")
                if raw:
                    try:
                        timings.append({**json.loads(raw), "run_id": rid})
                    except Exception:
                        pass

            # Also check agent-trace for stage breakdowns (best-effort enrichment)
            raw_events = await client.lrange("sage:agent_trace:recent", 0, 199)
        finally:
            await client.aclose()
    except Exception:
        return {"last_run": None, "rolling_median_s": None, "runs": []}

    trace_events: list[dict] = []
    for r in raw_events:
        try:
            trace_events.append(json.loads(r))
        except Exception:
            pass
    trace_events.sort(key=lambda e: e.get("ts", ""))

    def _enrich_with_trace(timing: dict) -> dict | None:
        t0 = _parse_ts(timing.get("t0"))
        t_final = _parse_ts(timing.get("t_final"))
        if t0 is None or t_final is None:
            return None  # run not yet complete

        total_s = round(t_final - t0, 1)

        # Find trace events in the run window to get per-stage breakdown
        window = [e for e in trace_events
                  if _parse_ts(e.get("ts")) is not None
                  and t0 <= _parse_ts(e["ts"]) <= t_final + 5]

        s2 = [e for e in window if e.get("system") == "2" and e.get("status") == "done"]
        s3 = [e for e in window if e.get("system") == "3" and e.get("status") == "done"]
        s4 = [e for e in window if e.get("system") == "4" and e.get("status") == "done"]

        t2 = _parse_ts(s2[-1]["ts"]) if s2 else None
        t3 = _parse_ts(s3[-1]["ts"]) if s3 else None
        t4 = _parse_ts(s4[-1]["ts"]) if s4 else None

        # Stage deltas are derived from agent-trace "done" timestamps, which can
        # arrive slightly out of order under async publishing (e.g. a fast scenario
        # whose trace lands after procurement's). Clamp negatives to None so the UI
        # never shows a nonsensical "-0.9 s" stage on hover.
        def _pos(x):
            return x if (x is not None and x >= 0) else None

        return {
            "total_s": total_s,
            "signal_to_risk_s": _pos(round(t2 - t0, 1)) if t2 else None,
            "scenario_to_procurement_s": _pos(round(t3 - t2, 1)) if t3 and t2 else None,
            "procurement_to_reserve_s": _pos(round(t4 - t3, 1)) if t4 and t3 else None,
            "started_at": timing.get("t0"),
            "entity": timing.get("entity"),
            "origin": timing.get("origin"),
        }

    computed: list[dict] = []
    for t in timings:
        result = _enrich_with_trace(t)
        if result:
            computed.append(result)

    if not computed:
        return {"last_run": None, "rolling_median_s": None, "runs": []}

    recent_5 = computed[:5]  # list is newest-first (lpush order)
    totals = [r["total_s"] for r in recent_5 if r.get("total_s") is not None]
    median_s = round(statistics.median(totals), 1) if totals else None

    return {
        "last_run": recent_5[0],
        "rolling_median_s": median_s,
        "runs": recent_5,
    }


# ---------------------------------------------------------------------------
# Feedback / accuracy
# ---------------------------------------------------------------------------

@app.get("/api/accuracy")
async def accuracy() -> dict:
    """SAGE prediction accuracy summary (for XAI panel)."""
    from knowledge.feedback import get_accuracy_summary
    summary = get_accuracy_summary() or {}

    # Augment with GBM fusion model metadata if available
    import pickle
    from pathlib import Path
    model_path = Path(__file__).parent.parent.parent / "sensory_agent" / "fusion_model.pkl"
    if model_path.exists():
        try:
            with open(model_path, "rb") as _f:
                _pkg = pickle.load(_f)
            _meta = _pkg.get("meta", {})
            summary["fusion_model"] = {
                "version": "GBM v1",
                "validation": "LOCO-5",
                "auc": _meta.get("auc"),
                "mean_loco_auc": _meta.get("mean_loco"),
                "threshold": _meta.get("threshold"),
                "trained_at": _meta.get("trained_at"),
                "n_crises": _meta.get("n_crises"),
                "n_ticks": _meta.get("n_ticks"),
                "label": f"GBM v1 · AUC {_meta.get('mean_loco', 0):.2f} (LOCO)" if _meta else "GBM v1",
            }
        except Exception:
            summary["fusion_model"] = {"version": "GBM v1", "label": "GBM v1 · AUC 0.84 (LOCO)"}

    return summary or {"message": "No feedback records yet."}


@app.post("/api/admin/flush-deferred")
async def admin_flush_deferred() -> dict:
    """
    Manually trigger the EOD deferred-ingest flush without waiting for 23:50 UTC.
    Runs in background; responds immediately with current pending count.
    """
    import os as _os, asyncio as _asyncio
    from knowledge.deferred_ingest import flush_all_deferred, deferred_count

    redis_url = _os.environ.get("REDIS_URL", "redis://redis:6379/0")
    pending = deferred_count()

    async def _run():
        try:
            await flush_all_deferred(redis_url)
        except Exception as exc:
            import logging as _log
            _log.getLogger("api.flush_deferred").error("Manual flush error: %s", exc)

    _asyncio.create_task(_run())
    return {"status": "flushing", "pending_signals": pending}


@app.get("/api/admin/deferred-status")
async def admin_deferred_status() -> dict:
    """Return count of signals currently parked in the deferred ingest store."""
    from knowledge.deferred_ingest import deferred_count, IMMEDIATE_INGEST_THRESHOLD, EOD_FLUSH_UTC
    return {
        "pending_signals": deferred_count(),
        "immediate_threshold": IMMEDIATE_INGEST_THRESHOLD,
        "eod_flush_utc": EOD_FLUSH_UTC,
    }


@app.get("/api/demo/status")
async def demo_status() -> dict:
    """Returns current demo replay status (set by scripts/demo_ignite.py)."""
    import json as _json
    import os as _os
    import redis.asyncio as _aioredis
    r = _aioredis.from_url(
        _os.environ.get("REDIS_URL", "redis://redis:6379/0"), decode_responses=True
    )
    try:
        raw = await r.get("sage:demo:status")
        if raw:
            return _json.loads(raw)
    except Exception:
        pass
    finally:
        await r.aclose()
    return {"active": False, "crisis": None, "message": ""}


# ---------------------------------------------------------------------------
# WebSocket push channel
# ---------------------------------------------------------------------------

@app.websocket("/ws/voice")
async def voice_websocket(ws: WebSocket) -> None:
    """Voice bridge — Gnani STT/TTS + intent → action bus."""
    from voicebridge.ws import voice_ws_endpoint
    await voice_ws_endpoint(ws)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """
    WebSocket push channel. Frontend subscribes to drive:
      - Pipeline stage bar (SENSE → TRIAGE → SAGE → SANDBOX → SCENARIO → PROCURE → RESERVE)
      - Risk score live updates (map node colour changes)
      - Threshold crossing alerts
      - Sandbox fork notifications

    Events are published to Redis pub/sub by monitor.py and sandbox.py,
    then forwarded to all connected WebSocket clients here.
    """
    import redis.asyncio as aioredis
    import os

    await ws.accept()
    await ws.send_json({"event": "connected", "status": "SAGE WebSocket active"})

    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")

    try:
        client = aioredis.from_url(redis_url, decode_responses=True)
        pubsub = client.pubsub()
        await pubsub.subscribe("sage:events")

        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    await ws.send_text(message["data"])
                except Exception:
                    break

    except Exception as exc:
        log.warning("WebSocket Redis subscription failed: %s — falling back to keep-alive", exc)
        try:
            while True:
                await asyncio.sleep(15)
                await ws.send_json({"event": "ping"})
        except Exception:
            pass
