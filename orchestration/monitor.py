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
# entity → monotonic time of last pipeline fire. A hub whose score oscillates across
# the action threshold would otherwise re-fire the full Bedrock pipeline every poll;
# the cooldown caps one autonomous run per entity per window regardless of wobble.
_last_fire_ts: dict[str, float] = {}
FIRE_COOLDOWN_S = float(os.environ.get("SAGE_FIRE_COOLDOWN_S", "600"))


def _fire_allowed(entity: str) -> bool:
    import time
    last = _last_fire_ts.get(entity)
    return last is None or (time.monotonic() - last) >= FIRE_COOLDOWN_S


def _mark_fired(entity: str) -> None:
    import time
    _last_fire_ts[entity] = time.monotonic()

# ── Pipeline-trigger allowlist ────────────────────────────────────────────────
# The autonomous response pipeline (scenario → procurement → SPR) only makes sense
# for SUPPLY-CHAIN entities — a corridor, supplier, refinery or port whose risk
# implies a concrete procurement/reserve action. Geopolitical hub nodes (a country,
# an Authority, a GeoEvent) can legitimately score high from news tone without any
# procurement response being meaningful; firing an ARIO cascade + Bedrock synthesis
# for "United States" is both wrong and a wasted LLM call. We gate firing on entity
# type, resolved from graph labels and cached briefly.
_ELIGIBLE_TYPES = {
    "Corridor", "Supplier", "Refinery", "Port", "ProductionField", "DistributionHub",
}
_eligible_names: set[str] = set()
_eligible_ts: float = 0.0
_ELIGIBLE_TTL_S = 120.0
_warm_started = False


async def _refresh_eligible() -> None:
    """Cache the set of pipeline-eligible entity NAMES (by supply-chain label)."""
    global _eligible_names, _eligible_ts
    import time
    if time.monotonic() - _eligible_ts < _ELIGIBLE_TTL_S and _eligible_names:
        return
    try:
        from knowledge.api.read import _cypher
        labels_list = "[" + ",".join(f"'{t}'" for t in _ELIGIBLE_TYPES) + "]"
        rows = await _cypher(
            f"MATCH (n:Entity) WHERE any(l IN n.labels WHERE l IN {labels_list}) "
            f"RETURN n.name AS name"
        )
        names = {r.get("name") for r in rows if r.get("name")}
        if names:
            _eligible_names = names
            _eligible_ts = time.monotonic()
    except Exception as exc:
        log.debug("[monitor] eligible-set refresh failed (non-fatal): %s", exc)


def _pipeline_eligible(entity: str) -> bool:
    """True if the entity is a supply-chain type the response pipeline should fire for.
    Fail-open only when the eligible set is empty (cold start) so a resolution
    outage never silences the pipeline entirely."""
    if not _eligible_names:
        return True
    return entity in _eligible_names


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
            _last_fire_ts.clear()
            log.info("Demo sandbox ENTERED — cleared trigger dedup")
        demo_prev = demo_active

        try:
            await _poll()
        except Exception as exc:
            log.error("Monitor poll error: %s", exc)
        await asyncio.sleep(DEMO_POLL_INTERVAL_S if demo_active else POLL_INTERVAL_S)


async def _poll() -> None:
    global _warm_started
    scores = await get_risk_scores()
    client = aioredis.from_url(REDIS_URL, decode_responses=True)
    await _refresh_eligible()

    try:
        if not _warm_started:
            for view in scores:
                if view.score >= CRITICAL_THRESHOLD:
                    _fired_bands[view.entity] = "critical"
                elif view.score >= ACTION_THRESHOLD:
                    _fired_bands[view.entity] = "action"
                elif view.score >= SANDBOX_FORK_THRESHOLD:
                    _fired_bands[view.entity] = "elevated"
            _warm_started = True
            log.info("[monitor] warm-started from %d existing risk states", len(scores))
            return

        for view in scores:
            entity = view.entity
            score  = view.score
            prev   = _fired_bands.get(entity, "calm")

            # Only supply-chain entities trigger the response pipeline. A non-eligible
            # entity (country/authority/event) can still be scored and shown, but we
            # don't fire ARIO + procurement + SPR (or burn Bedrock) for it.
            if score >= SANDBOX_FORK_THRESHOLD and not _pipeline_eligible(entity):
                if prev != "calm":
                    _fired_bands.pop(entity, None)
                log.debug("[monitor] %s at %.2f — not pipeline-eligible, skipping fire", entity, score)
                continue

            if score >= CRITICAL_THRESHOLD and prev != "critical" and _fire_allowed(entity):
                _fired_bands[entity] = "critical"
                _mark_fired(entity)
                scenario_ref = await _get_pending(client, entity)
                await _publish(client, "critical", entity, score, scenario_ref)
                from orchestration.triggers import on_critical
                await on_critical(entity, score)

            elif score >= ACTION_THRESHOLD and prev not in ("action", "critical") and _fire_allowed(entity):
                _fired_bands[entity] = "action"
                _mark_fired(entity)
                scenario_ref = await _get_pending(client, entity)
                await _publish(client, "action", entity, score, scenario_ref)
                from orchestration.triggers import on_action
                await on_action(entity, score, scenario_ref)
                # Consume the key so we don't double-promote on the next poll
                if scenario_ref:
                    await client.delete(f"sage:pending:{entity}")
                    _registered_scenarios.pop(entity, None)

            elif score >= SANDBOX_FORK_THRESHOLD and prev not in ("elevated", "action", "critical") and _fire_allowed(entity):
                _fired_bands[entity] = "elevated"
                _mark_fired(entity)
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
