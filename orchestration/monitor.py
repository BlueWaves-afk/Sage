"""
LangGraph threshold monitor.

Polls get_risk_scores() every 30 seconds. On band crossing:
  elevated → fire sandbox fork if no pending scenario exists yet
  action   → promote pending scenario (fast path) OR cold-trigger pipeline
  critical → escalation alert + action path

Pending scenario tracking uses Redis keys `sage:pending:{entity}` with a 72h TTL
set by ingest_queue._maybe_sandbox_fork(). When the TTL expires, Redis deletes the
key automatically — this implements the C6 PendingScenario 72h expiry contract.

On each poll cycle the monitor also scans for recently expired scenarios and calls
record_expired_outcome() to close the feedback loop (false positive detection).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Optional

import redis.asyncio as aioredis

from contracts.bands import ACTION_THRESHOLD, CRITICAL_THRESHOLD, SANDBOX_FORK_THRESHOLD
from knowledge.api.read import get_risk_scores

log = logging.getLogger(__name__)

POLL_INTERVAL_S = 30
REDIS_URL       = os.environ.get("REDIS_URL", "redis://redis:6379/0")
EVENTS_CHANNEL  = "sage:events"

# entity → last fired band (prevents re-firing on every poll while entity stays hot)
_fired_bands: dict[str, str] = {}
# entity → scenario_ref for scenarios we know about (used for expiry detection)
_registered_scenarios: dict[str, str] = {}


async def run_monitor() -> None:
    """Continuous async loop. Entry point called from sage_core."""
    log.info("Threshold monitor started. Poll interval: %ds", POLL_INTERVAL_S)
    from knowledge.demo_control import is_demo_active, DEMO_POLL_INTERVAL_S
    demo_prev = False
    client = aioredis.from_url(REDIS_URL, decode_responses=True)
    while True:
        # Demo sandbox: clear the fire-dedup so the replay can re-fire the full
        # cascade from a clean baseline, and poll faster so a ~3-min replay
        # produces a visibly live crossing. No-op when no demo runs.
        demo_active = await is_demo_active(client)
        if demo_active and not demo_prev:
            _fired_bands.clear()
            log.info("Demo sandbox ENTERED — cleared trigger dedup")
        demo_prev = demo_active

        try:
            await _poll()
        except Exception as exc:
            log.error("Monitor poll error: %s", exc)
        await asyncio.sleep(DEMO_POLL_INTERVAL_S if demo_active else POLL_INTERVAL_S)


async def _poll() -> None:
    scores = await get_risk_scores()
    client = aioredis.from_url(REDIS_URL, decode_responses=True)

    try:
        for view in scores:
            entity = view.entity
            score  = view.score
            prev   = _fired_bands.get(entity, "calm")

            if score >= CRITICAL_THRESHOLD and prev != "critical":
                _fired_bands[entity] = "critical"
                scenario_ref = await _get_pending(client, entity)
                await _publish(client, "critical", entity, score, scenario_ref)
                from orchestration.triggers import on_critical
                await on_critical(entity, score)

            elif score >= ACTION_THRESHOLD and prev not in ("action", "critical"):
                _fired_bands[entity] = "action"
                scenario_ref = await _get_pending(client, entity)
                await _publish(client, "action", entity, score, scenario_ref)
                from orchestration.triggers import on_action
                await on_action(entity, score, scenario_ref)
                # Consume the key so we don't double-promote on the next poll
                if scenario_ref:
                    await client.delete(f"sage:pending:{entity}")
                    _registered_scenarios.pop(entity, None)

            elif score >= SANDBOX_FORK_THRESHOLD and prev not in ("elevated", "action", "critical"):
                _fired_bands[entity] = "elevated"
                scenario_ref = await _get_pending(client, entity)
                await _publish(client, "elevated", entity, score, scenario_ref)
                from orchestration.triggers import on_elevated
                await on_elevated(entity, score)

            elif score < SANDBOX_FORK_THRESHOLD:
                # Entity cooled — reset so it can re-fire on the next escalation
                _fired_bands.pop(entity, None)

        await _check_expirations(client)
        await _drain_job_queue(client)

    finally:
        await client.aclose()


async def _drain_job_queue(client: object) -> None:
    """
    Drain `sage:jobs` (enqueued by knowledge/feedback.py::_maybe_trigger_retrain
    once RETRAIN_THRESHOLD outcome records accumulate) and actually run the
    retrain — closing the loop that used to just print a message an operator
    had to notice and act on manually.
    """
    while True:
        raw = await client.rpop("sage:jobs")
        if not raw:
            break
        try:
            job = json.loads(raw)
        except Exception:
            continue
        if job.get("job") == "calibrate_fusion":
            await _run_fusion_calibration(job.get("count"))


async def _run_fusion_calibration(count: Optional[int]) -> None:
    """Run sensory_agent.fusion's blocking GBM calibration off the event loop."""
    try:
        from knowledge.agent_trace import publish_trace
        await publish_trace(system="1", agent="fusion",
                             action=f"Retraining fusion model from {count or '?'} feedback records",
                             status="started")
    except Exception:
        pass

    try:
        from sensory_agent.fusion import _calibrate
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _calibrate)
        log.info("Fusion model retrain complete (%s feedback records)", count)
        try:
            from knowledge.agent_trace import publish_trace
            await publish_trace(system="1", agent="fusion",
                                 action="Fusion model retrain complete", status="done")
        except Exception:
            pass
    except Exception as exc:
        log.error("Fusion model retrain failed: %s", exc)
        try:
            from knowledge.agent_trace import publish_trace
            await publish_trace(system="1", agent="fusion",
                                 action=f"Fusion model retrain failed: {exc}", status="error")
        except Exception:
            pass


async def _get_pending(client: object, entity: str) -> Optional[str]:
    """Return pending scenario_ref from Redis; track it for expiry detection."""
    try:
        val = await client.get(f"sage:pending:{entity}")
        if val:
            _registered_scenarios[entity] = val
        return val
    except Exception:
        return None


async def _check_expirations(client: object) -> None:
    """
    Detect pending scenarios whose 72h Redis TTL has expired (no crossing happened).
    Records a false-positive outcome and publishes an expiry event to clear the UI.
    """
    expired = []
    for entity, ref in list(_registered_scenarios.items()):
        try:
            still_alive = await client.exists(f"sage:pending:{entity}")
        except Exception:
            still_alive = True
        if not still_alive:
            expired.append((entity, ref))

    for entity, scenario_ref in expired:
        _registered_scenarios.pop(entity, None)
        log.info("PendingScenario expired without crossing: %s ref=%s", entity, scenario_ref)
        try:
            from knowledge.feedback import record_expired_outcome
            await record_expired_outcome(
                scenario_id=scenario_ref,
                entity=entity,
                predicted_confidence=0.0,
                predicted_crossing_hours=0.0,
                feature_vector_at_prediction={},
            )
        except Exception as exc:
            log.warning("record_expired_outcome failed for %s (non-fatal): %s", scenario_ref, exc)
        await _publish(client, "expired", entity, 0.0, scenario_ref)


async def _publish(
    client: object,
    band: str,
    entity: str,
    score: float,
    scenario_ref: Optional[str],
) -> None:
    """Publish a pipeline event to sage:events (consumed by the WebSocket gateway)."""
    event = json.dumps({
        "type": "threshold",
        "band": band,
        "entity": entity,
        "score": round(score, 4),
        "scenario_ref": scenario_ref,
    })
    try:
        await client.publish(EVENTS_CHANNEL, event)
    except Exception as exc:
        log.warning("Failed to publish monitor event: %s", exc)
    log.info("[monitor] %s — %s score=%.2f scenario=%s",
             band.upper(), entity, score, scenario_ref or "none")
