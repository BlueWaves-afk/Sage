"""
FastAPI gateway. Serves REST + WebSocket to the React frontend.
Port 8000 — the only backend port exposed to the host.
"""
from __future__ import annotations

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from knowledge.api.read import (
    copilot_query, get_risk_scores, get_wiki_page,
)

app = FastAPI(title="SAGE API Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten for production
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/api/risk-scores")
async def risk_scores() -> list:
    """All current RISK_STATE edges — drives map node colours."""
    scores = await get_risk_scores()
    return [s.model_dump() for s in scores]


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


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """
    WebSocket push channel.
    SAGE core and LangGraph emit state-change events here.
    Frontend subscribes to drive the pipeline bar + staged alerts.
    Stub — implement event loop in Week 2.
    """
    await ws.accept()
    # TODO: subscribe to Redis pub/sub for SAGE state change events
    # TODO: push JSON events to ws on: risk_score update, sandbox fork, threshold crossing, promotion
    await ws.send_json({"event": "connected"})
    try:
        while True:
            await ws.receive_text()   # keep-alive
    except Exception:
        pass
