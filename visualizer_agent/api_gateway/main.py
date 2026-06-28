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

from knowledge.api.read import (
    copilot_query,
    get_risk_scores,
    get_spr_state,
    get_available_suppliers,
    get_routes,
    get_wiki_page,
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
    answer = await copilot_query(body.get("question", ""))
    return answer.model_dump()


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
