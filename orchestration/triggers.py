"""
Event handlers fired by the monitor on band crossings.

Fast path (pre-staged): sandbox already ran → promote_pending() → recommendations
  surface in ~300ms because Systems 3+4 outputs are already in the graph.

Cold path (no sandbox): threshold crossed without prior sandbox → run full pipeline.
  Systems 2→3→4 run; 2 first, then 3+4 in parallel. ~8,500ms total.

Each handler publishes stage events to sage:events so the WebSocket pipeline bar
updates autonomously without any human action.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from typing import Optional

import redis.asyncio as aioredis

log = logging.getLogger(__name__)

REDIS_URL      = os.environ.get("REDIS_URL", "redis://redis:6379/0")
EVENTS_CHANNEL = "sage:events"


# ---------------------------------------------------------------------------
# Public trigger API (called by monitor.py)
# ---------------------------------------------------------------------------

async def on_elevated(entity: str, score: float) -> None:
    """
    Elevated band (0.45–0.70): sandbox evaluation.
    Ingest path fires sandbox on every HIGH signal, so a fork usually already
    exists. This handles the drift case where risk climbed slowly via MED signals.
    """
    client = aioredis.from_url(REDIS_URL, decode_responses=True)
    try:
        existing = await client.get(f"sage:pending:{entity}")
        if existing:
            log.debug("[trigger] elevated '%s' — sandbox active ref=%s", entity, existing)
        else:
            await _publish_stage(client, "SANDBOX", entity, "evaluating")
            log.info("[trigger] elevated '%s' — no sandbox yet; will fork on next HIGH signal", entity)
    except Exception as exc:
        log.warning("[trigger] on_elevated error for '%s': %s", entity, exc)
    finally:
        await client.aclose()


async def on_action(entity: str, score: float, scenario_ref: Optional[str]) -> None:
    """Action band (0.70–0.90): promote pre-staged or run cold pipeline."""
    client = aioredis.from_url(REDIS_URL, decode_responses=True)
    try:
        if scenario_ref:
            await _fast_path(client, entity, score, scenario_ref)
        else:
            await _cold_pipeline(client, entity, score)
    except Exception as exc:
        log.error("[trigger] on_action error for '%s': %s", entity, exc)
    finally:
        await client.aclose()


async def on_critical(entity: str, score: float) -> None:
    """Critical band (≥0.90): human escalation alert + run action path."""
    client = aioredis.from_url(REDIS_URL, decode_responses=True)
    try:
        await _publish_stage(client, "ESCALATION", entity, "critical")
        log.warning("[trigger] CRITICAL — '%s' score=%.2f — human escalation required", entity, score)
        scenario_ref = await client.get(f"sage:pending:{entity}")
        if scenario_ref:
            await _fast_path(client, entity, score, scenario_ref)
        else:
            await _cold_pipeline(client, entity, score)
    except Exception as exc:
        log.error("[trigger] on_critical error for '%s': %s", entity, exc)
    finally:
        await client.aclose()


async def on_sandbox_promoted(entity: str, scenario_ref: str) -> None:
    """
    Called by promote_pending() after a PendingScenario is confirmed.
    Publishes scenario.promoted so the frontend surfaces pre-staged recommendations.
    """
    client = aioredis.from_url(REDIS_URL, decode_responses=True)
    try:
        await client.publish(EVENTS_CHANNEL, json.dumps({
            "type": "scenario.promoted",
            "entity": entity,
            "scenario_ref": scenario_ref,
            "stage": "SCENARIO",
            "status": "promoted",
        }))
        log.info("[trigger] sandbox promoted — '%s' ref=%s", entity, scenario_ref)
    except Exception as exc:
        log.warning("on_sandbox_promoted publish failed (non-fatal): %s", exc)
    finally:
        await client.aclose()


# ---------------------------------------------------------------------------
# Fast path: pre-staged recommendations already exist
# ---------------------------------------------------------------------------

async def _fast_path(client: object, entity: str, score: float, scenario_ref: str) -> None:
    await _publish_stage(client, "SCENARIO", entity, "promoting")
    try:
        from knowledge.api.write import promote_pending
        await promote_pending(scenario_ref, entity=entity)
        await _publish_stage(client, "SCENARIO", entity, "promoted")
        log.info("[trigger] fast path — promoted %s for '%s' (score=%.2f)", scenario_ref, entity, score)
    except Exception as exc:
        log.error("[trigger] promote_pending failed for %s: %s — cold fallback", scenario_ref, exc)
        await _cold_pipeline(client, entity, score)


# ---------------------------------------------------------------------------
# Cold path: no pre-staged scenario
# ---------------------------------------------------------------------------

async def _cold_pipeline(client: object, entity: str, score: float) -> None:
    """Run Systems 2→3→4. System 2 first, then 3+4 in parallel."""
    scenario_id = f"cold-{uuid.uuid4().hex[:8]}"
    log.info("[trigger] cold pipeline — '%s' ref=%s", entity, scenario_id)

    # System 2 — LLM decides scenario params from live signals, then runs cascade.
    await _publish_stage(client, "SCENARIO", entity, "running")
    scenario_params: dict = {}
    try:
        from orchestration.scenario_params import decide_scenario_params
        from scenario_agent.runner import run as run_scenario
        scenario_params = await decide_scenario_params(entity)
        log.info("[trigger] scenario params for '%s': %s", entity, scenario_params)
        scenario_id = await run_scenario(trigger_entity=entity, status="confirmed", scenario=scenario_params)
        await _publish_stage(client, "SCENARIO", entity, "done")
    except Exception as exc:
        log.error("[trigger] scenario_agent failed for '%s': %s", entity, exc)
        await _publish_stage(client, "SCENARIO", entity, "error")
        return

    # Systems 3 + 4 run in parallel, both informed by the scenario result.
    await _publish_stage(client, "PROCURE", entity, "running")
    await _publish_stage(client, "RESERVE", entity, "running")

    results = await asyncio.gather(
        _run_procurement(scenario_id, entity),
        _run_spr(scenario_id, scenario_params),
        return_exceptions=True,
    )
    for result, label in zip(results, ("PROCURE", "RESERVE")):
        stage_status = "error" if isinstance(result, Exception) else "done"
        await _publish_stage(client, label, entity, stage_status)
        if isinstance(result, Exception):
            log.error("[trigger] %s failed for '%s': %s", label, entity, result)

    log.info("[trigger] cold pipeline complete — '%s' ref=%s", entity, scenario_id)


async def _run_procurement(scenario_id: str, trigger_entity: str) -> None:
    from alt_procurement_agent.runner import run as run_procurement
    await run_procurement(scenario_id=scenario_id, trigger_refinery=trigger_entity)


async def _run_spr(scenario_id: str, scenario_params: dict) -> None:
    from reserve_optim_agent.runner import run as run_spr
    await run_spr(
        scenario_id=scenario_id,
        gap_mbpd=scenario_params.get("disruption_fraction", 1.0) * 2.19,  # Hormuz dep ~2.19mbpd
        gap_duration_days=int(scenario_params.get("disruption_days", 30)),
        escalation_profile=scenario_params.get("escalation_profile", "constant"),
    )


async def _publish_stage(client: object, stage: str, entity: str, status: str) -> None:
    try:
        await client.publish(EVENTS_CHANNEL, json.dumps({
            "type": "pipeline_stage",
            "stage": stage,
            "entity": entity,
            "status": status,
        }))
    except Exception as exc:
        log.warning("Failed to publish stage event %s/%s: %s", stage, status, exc)
