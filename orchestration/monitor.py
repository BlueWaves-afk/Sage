"""
LangGraph threshold monitor.

Polls get_risk_scores() every 30 seconds. On band crossing, fires the appropriate
trigger: sandbox fork (elevated), scenario promotion (action), escalation (critical).
This is what makes the system autonomous — no human query required to start the pipeline.
"""
from __future__ import annotations

import asyncio

from contracts.bands import ACTION_THRESHOLD, CRITICAL_THRESHOLD, SANDBOX_FORK_THRESHOLD
from knowledge.api.read import get_risk_scores
from knowledge.api.write import promote_pending

POLL_INTERVAL_S = 30
_already_fired: set[str] = set()   # entity names that have already triggered in this session


async def run_monitor() -> None:
    """
    Continuous async loop. Entry point for the LangGraph monitor node.
    Stub — real implementation emits LangGraph events on crossing detected.
    """
    while True:
        await _poll()
        await asyncio.sleep(POLL_INTERVAL_S)


async def _poll() -> None:
    scores = await get_risk_scores()
    for view in scores:
        entity = view.entity
        score  = view.score

        if score >= CRITICAL_THRESHOLD:
            _fire("critical", entity, score)
        elif score >= ACTION_THRESHOLD and entity not in _already_fired:
            _fire("action", entity, score)
            _already_fired.add(entity)
            # TODO: call promote_pending(scenario_ref) if PendingScenario exists
            # TODO: emit LangGraph "threshold_crossed" event → triggers systems 2/3/4
        elif score >= SANDBOX_FORK_THRESHOLD:
            pass  # sandbox fork decision lives in sandbox.py
        else:
            _already_fired.discard(entity)


def _fire(band: str, entity: str, score: float) -> None:
    # TODO: emit LangGraph state-change event consumed by graph.py
    print(f"[monitor] {band.upper()} crossing — {entity} score={score:.2f}")
