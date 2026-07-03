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

    yield   # Application is running

    log.info("SAGE API Gateway shutting down.")


app = FastAPI(title="SAGE API Gateway", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten for production
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

    return {
        "threat_level": threat,
        "active_alerts": active_alerts,
        "spr_coverage_pct": spr_pct,
        "brent_usd_bbl": brent,
        "brent_source": brent_source,
        "monitoring_entities": node_count,
        "bottlenecks": bottlenecks,
        "top_risk_entity": scores[0].entity if scores else None,
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


@app.post("/api/copilot")
async def copilot(body: dict) -> dict:
    """EA-GraphRAG routed copilot endpoint."""
    import re as _re

    q = body.get("query") or body.get("question") or ""
    answer = await copilot_query(q)
    out = answer.model_dump()

    # Structure flat citation strings into {entity, episode_id} for the UI.
    # UUID-shaped strings are episode/edge ids; the rest are entity names.
    uuid_re = _re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-", _re.I)
    structured = []
    for c in out.get("citations", []):
        s = str(c)
        if uuid_re.match(s):
            structured.append({"entity": "graph edge", "episode_id": s[:8]})
        else:
            structured.append({"entity": s, "episode_id": "wiki"})
    out["citations"] = structured
    return out


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
