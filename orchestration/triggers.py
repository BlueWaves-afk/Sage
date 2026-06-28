"""
Event handlers fired by the LangGraph monitor on band crossings.
Each trigger activates the appropriate downstream agent(s).
"""
from __future__ import annotations


async def on_elevated(entity: str, score: float) -> None:
    """elevated band — evaluate sandbox fork (see sandbox.py)."""
    # TODO: emit sandbox fork event if not already forked for this entity
    pass


async def on_action(entity: str, score: float, scenario_ref: str | None) -> None:
    """action band — promote sandbox if exists, else run cold pipeline."""
    if scenario_ref:
        # fast path: pre-staged recommendations already exist
        # TODO: call promote_pending(scenario_ref)
        pass
    else:
        # cold path: trigger full systems 2→3→4 pipeline
        # TODO: emit scenario_agent trigger event
        pass


async def on_critical(entity: str, score: float) -> None:
    """critical band — immediate human escalation + full pipeline."""
    # TODO: push notification to human operator (email / SMS / dashboard alert)
    # TODO: also run on_action path
    pass


async def on_sandbox_promoted(entity: str, scenario_ref: str) -> None:
    """Called by promote_pending() after a PendingScenario is confirmed."""
    # TODO: push 'scenario.promoted' WebSocket event to visualizer_agent frontend
    pass
