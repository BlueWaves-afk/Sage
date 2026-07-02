"""
LangGraph state machine for the SAGE autonomous pipeline.

Pipeline stages (maps to the UI pipeline bar):
  SENSE → TRIAGE → SAGE → {SANDBOX ∥ monitor} → SCENARIO → PROCURE → RESERVE

The node implementations (sandbox.py, monitor.py, triage, ingest, the three agent
runners) are the tested units; this module only wires them into a graph.

`build_graph()` returns a real compiled LangGraph `StateGraph` when `langgraph` is
installed, and otherwise a `_FallbackPipeline` exposing the same `async ainvoke(state)`
interface — so callers work identically either way. Both paths call the SAME node
coroutines below, so behaviour is consistent regardless of which backend runs.
"""
from __future__ import annotations

import logging
from typing import Any

from contracts.bands import ACTION_THRESHOLD
from contracts.signal import NormalizedSignal

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline state
# ---------------------------------------------------------------------------
# A plain dict is the state container (LangGraph merges node return dicts into it).
# Keys:
#   signal            NormalizedSignal        (input)
#   entity            str                     primary entity_ref
#   triage_decision   str                     synthesize|extract|store|drop
#   triage_similarity float
#   ingest            IngestResult
#   risk_score        float                   current fused score for entity
#   risk_band         str
#   sandbox           SandboxResult | None
#   scenario_id       str | None
#   scenario_params   dict
#   procurement_done  bool
#   reserve_done      bool
#   stages            list[str]               ordered log of stages that ran
PipelineState = dict


def _log_stage(state: PipelineState, name: str) -> None:
    state.setdefault("stages", []).append(name)


# ---------------------------------------------------------------------------
# Node coroutines (shared by both the LangGraph and fallback backends)
# ---------------------------------------------------------------------------

async def sense_node(state: PipelineState) -> PipelineState:
    """Resolve the primary entity for the signal. (Signal already in state.)"""
    signal: NormalizedSignal = state["signal"]
    state["entity"] = (signal.entity_refs or [signal.summary[:60]])[0]
    _log_stage(state, "SENSE")
    return state


async def triage_node(state: PipelineState) -> PipelineState:
    from knowledge.triage import triage
    decision, sim = await triage(state["signal"])
    state["triage_decision"] = decision
    state["triage_similarity"] = sim
    _log_stage(state, "TRIAGE")
    return state


async def sage_node(state: PipelineState) -> PipelineState:
    """Write the signal into the KB, then read back the entity's current fused risk."""
    from knowledge.api.write import ingest_signal
    from knowledge.api.read import get_risk_scores

    if state.get("triage_decision") != "drop":
        state["ingest"] = await ingest_signal(state["signal"])

    cur = next((s for s in await get_risk_scores() if s.entity == state.get("entity")), None)
    state["risk_score"] = float(cur.score) if cur else 0.0
    state["risk_band"] = cur.band if cur else "calm"
    _log_stage(state, "SAGE")
    return state


async def sandbox_node(state: PipelineState) -> PipelineState:
    """Anticipatory fork (parallel branch). Only meaningful for HIGH-priority signals."""
    from orchestration.sandbox import maybe_fork
    try:
        state["sandbox"] = await maybe_fork(state["signal"], state["entity"])
    except Exception as exc:
        log.warning("[graph] sandbox_node failed: %s", exc)
        state["sandbox"] = None
    _log_stage(state, "SANDBOX")
    return state


async def scenario_node(state: PipelineState) -> PipelineState:
    """Run System 2 with LLM-decided scenario params (confirmed threshold crossing)."""
    from orchestration.scenario_params import decide_scenario_params
    from scenario_agent.runner import run as run_scenario

    entity = state["entity"]
    scenario_params = await decide_scenario_params(entity)
    state["scenario_params"] = scenario_params
    state["scenario_id"] = await run_scenario(
        trigger_entity=entity, status="confirmed", scenario=scenario_params
    )
    _log_stage(state, "SCENARIO")
    return state


async def procure_node(state: PipelineState) -> PipelineState:
    from alt_procurement_agent.runner import run as run_procurement
    scenario = state.get("scenario_params", {}) or {}
    gap_mbpd = float(scenario.get("disruption_fraction", 1.0)) * _hormuz_mbpd()
    await run_procurement(
        scenario_id=state["scenario_id"], trigger_refinery=state["entity"],
        status="confirmed", gap_mbpd=gap_mbpd,
    )
    state["procurement_done"] = True
    _log_stage(state, "PROCURE")
    return state


async def reserve_node(state: PipelineState) -> PipelineState:
    from reserve_optim_agent.runner import run as run_spr
    scenario = state.get("scenario_params", {}) or {}
    await run_spr(
        scenario_id=state["scenario_id"],
        gap_mbpd=float(scenario.get("disruption_fraction", 1.0)) * _hormuz_mbpd(),
        gap_duration_days=int(scenario.get("disruption_days", 30)),
        status="confirmed",
        escalation_profile=scenario.get("escalation_profile", "constant"),
    )
    state["reserve_done"] = True
    _log_stage(state, "RESERVE")
    return state


def _hormuz_mbpd() -> float:
    """Reuse the bundle-derived Hormuz dependency from triggers (single source of truth)."""
    try:
        from orchestration.triggers import _hormuz_dependency_mbpd
        return _hormuz_dependency_mbpd()
    except Exception:
        return 2.19


# ---------------------------------------------------------------------------
# Routing predicates
# ---------------------------------------------------------------------------

def _is_high_priority(state: PipelineState) -> bool:
    """Sandbox forks only for HIGH-priority signals (the anticipatory branch)."""
    return getattr(state["signal"], "priority_hint", "LOW") == "HIGH"


def _crossed_action(state: PipelineState) -> bool:
    """Scenario pipeline fires when the entity's fused risk is in action/critical band."""
    return float(state.get("risk_score", 0.0)) >= ACTION_THRESHOLD


# ---------------------------------------------------------------------------
# LangGraph backend
# ---------------------------------------------------------------------------

def _build_langgraph():
    """Wire a real LangGraph StateGraph. Raises ImportError if langgraph is absent."""
    from langgraph.graph import StateGraph, END

    g = StateGraph(dict)
    g.add_node("sense", sense_node)
    g.add_node("triage", triage_node)
    g.add_node("sage", sage_node)
    g.add_node("sandbox", sandbox_node)
    g.add_node("scenario", scenario_node)
    g.add_node("procure", procure_node)
    g.add_node("reserve", reserve_node)

    g.set_entry_point("sense")
    g.add_edge("sense", "triage")

    # Parallel anticipatory branch: HIGH signals fork the sandbox off triage; every
    # signal continues to SAGE. (Both fan-out targets converge before the band check.)
    g.add_conditional_edges(
        "triage",
        lambda s: ["sandbox", "sage"] if _is_high_priority(s) else ["sage"],
        {"sandbox": "sandbox", "sage": "sage"},
    )
    g.add_edge("sandbox", "sage")

    # After SAGE, run the response pipeline only if the band crossed action.
    g.add_conditional_edges(
        "sage",
        lambda s: "scenario" if _crossed_action(s) else "end",
        {"scenario": "scenario", "end": END},
    )
    g.add_edge("scenario", "procure")
    g.add_edge("procure", "reserve")
    g.add_edge("reserve", END)

    return g.compile()


# ---------------------------------------------------------------------------
# Fallback backend (no langgraph dependency)
# ---------------------------------------------------------------------------

class _FallbackPipeline:
    """
    Minimal async orchestrator with the same `ainvoke(state)` contract as a compiled
    LangGraph. Runs the identical node coroutines and routing predicates, so the
    pipeline behaves the same whether or not langgraph is installed.
    """

    async def ainvoke(self, state: PipelineState) -> PipelineState:
        import asyncio

        state = await sense_node(state)
        state = await triage_node(state)

        # SAGE always runs; sandbox forks in parallel for HIGH-priority signals.
        if _is_high_priority(state):
            sandbox_task = asyncio.create_task(sandbox_node(dict(state)))
            state = await sage_node(state)
            sandbox_state = await sandbox_task
            state["sandbox"] = sandbox_state.get("sandbox")
            if "SANDBOX" not in state.get("stages", []):
                state.setdefault("stages", []).append("SANDBOX")
        else:
            state = await sage_node(state)

        # Response pipeline only on an action-band crossing.
        if _crossed_action(state):
            state = await scenario_node(state)
            state = await procure_node(state)
            state = await reserve_node(state)

        return state


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------

def build_graph(prefer_langgraph: bool = True) -> Any:
    """
    Return a compiled pipeline exposing `async ainvoke(state) -> state`.

    Uses LangGraph when installed (and prefer_langgraph=True); otherwise returns the
    behaviourally-equivalent fallback. Both call the same node coroutines.
    """
    if prefer_langgraph:
        try:
            compiled = _build_langgraph()
            log.info("[graph] using LangGraph backend")
            return compiled
        except Exception as exc:
            log.info("[graph] langgraph unavailable (%s) — using fallback pipeline", exc)
    return _FallbackPipeline()


async def run_pipeline(signal: NormalizedSignal) -> PipelineState:
    """Convenience entry point: build the graph and run one signal through it."""
    graph = build_graph()
    return await graph.ainvoke({"signal": signal})
