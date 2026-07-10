"""
Agent Activity Trace — live, human-readable "what is SAGE doing right now"
feed for the dashboard. Distinct from the pipeline-bar stage events
(orchestration/triggers.py's `_publish_stage`, which drive the SENSE→TRIAGE→
…→RESERVE bar) — this is a finer-grained, per-agent narration intended to be
read directly by an operator, similar to a coding agent's live tool-call feed.

Single write path: `publish_trace()`. Pushes to:
  1. `sage:events` pub/sub (same channel the pipeline bar already uses) so the
     existing `/ws` WebSocket fans it out with zero new infra — the frontend
     discriminates on `type: "agent_trace"`.
  2. A bounded Redis list `sage:agent_trace:recent` (cap 50) so a client that
     connects *after* an event fired still sees recent history on load,
     instead of an empty feed until the next event happens to occur.

Best-effort, never raises — a trace publish failure must never break the
actual agent work it's narrating.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Literal, Optional

log = logging.getLogger(__name__)

EVENTS_CHANNEL = "sage:events"
RECENT_KEY = "sage:agent_trace:recent"
RECENT_CAP = 50

System = Literal["1", "2", "3", "4"]
Agent = Literal[
    "ais", "news", "prices", "sanctions",   # System 1 sub-agents
    "fusion",                                # System 1 risk fusion
    "scenario",                              # System 2
    "procurement",                           # System 3
    "reserve",                               # System 4
]
Status = Literal["started", "done", "error"]


async def publish_trace(
    system: System,
    agent: Agent,
    action: str,
    status: Status = "done",
    entity: Optional[str] = None,
    origin: Optional[str] = None,   # "auto" | "user" — which pipeline triggered this, when relevant
) -> None:
    """Publish one agent-trace event. Best-effort; never raises."""
    event = {
        "type": "agent_trace",
        "system": system,
        "agent": agent,
        "action": action,
        "status": status,
        "entity": entity,
        "origin": origin,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"),
                                   decode_responses=True)
        try:
            payload = json.dumps(event)
            await client.publish(EVENTS_CHANNEL, payload)
            await client.lpush(RECENT_KEY, payload)
            await client.ltrim(RECENT_KEY, 0, RECENT_CAP - 1)
        finally:
            await client.aclose()
    except Exception as exc:
        log.debug("publish_trace failed (non-fatal): %s", exc)


async def get_recent_trace(limit: int = 30) -> list[dict]:
    """Read recent agent-trace events, newest first — cold-start feed for the UI."""
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"),
                                   decode_responses=True)
        try:
            raw = await client.lrange(RECENT_KEY, 0, limit - 1)
        finally:
            await client.aclose()
        return [json.loads(r) for r in raw]
    except Exception as exc:
        log.warning("get_recent_trace failed: %s", exc)
        return []
