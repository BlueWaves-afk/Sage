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
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from fastapi import HTTPException

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
    from knowledge.connection import _graphiti_instance
    kb_ready = _graphiti_instance is not None
    return {
        "status": "ok" if kb_ready else "degraded",
        "kb_ready": kb_ready,
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
    answer = await copilot_query(q)
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
        # Stage 1: Scenario (System 2) — call runner directly with user-supplied params,
        # bypassing decide_scenario_params so the UI knobs are honoured exactly.
        RUN_STATUS[run_id].update({"stage": "scenario", "pct": 5})
        from scenario_agent.runner import run as run_scenario
        from knowledge.agent_trace import publish_trace
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
]

_KNOWN_ENTITIES: set[str] = {
    "Strait of Hormuz", "Bab-el-Mandeb", "Suez Canal",
    "Strait of Malacca", "Cape of Good Hope",
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
async def scenario_log_outcome(scenario_id: str, body: dict) -> dict:
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

    realized = {
        k: body.get(k) for k in
        ("gap_mbpd", "price_impact_high", "spr_depletion_days", "gdp_proxy_impact_pct")
        if body.get(k) is not None
    }
    if not realized:
        raise HTTPException(status_code=422, detail="at least one realized field is required")

    updated = record_scenario_realized(scenario_id, realized, source="analyst")
    if updated is None:
        raise HTTPException(status_code=404, detail="no matching prediction record for this scenario_id")

    calib = await maybe_calibrate_corridor(out.get("trigger_entity", ""))
    return {"ok": True, "error": updated.get("error"), "calibration": calib}


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
# Feedback / accuracy
# ---------------------------------------------------------------------------

@app.get("/api/accuracy")
async def accuracy() -> dict:
    """SAGE prediction accuracy summary (for XAI panel)."""
    from knowledge.feedback import get_accuracy_summary
    summary = get_accuracy_summary()
    return summary or {"message": "No feedback records yet."}


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
