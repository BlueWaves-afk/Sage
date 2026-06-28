"""
Anticipatory Simulation Sandbox manager.

When a HIGH-priority signal arrives and P(crossing in 24h) > 0.5, this forks an
in-memory subgraph snapshot, projects signal trajectories, runs the GNN surrogate,
pre-stages Systems 3+4 outputs, and stores a PendingScenario in Graphiti.

This runs PARALLEL to the ground-truth synthesis branch — it does not block or delay
the main SAGE write pipeline. Total fork latency target: ~1,580ms.

Step timings:
  subgraph extraction  ~50ms
  trajectory projection ~80ms   (Chronos-2 / TimesFM-2.5)
  GNN surrogate        ~150ms   (PyTorch, T4 GPU)
  Systems 3+4 pre-stage ~1,200ms
  PendingScenario write ~100ms
"""
from __future__ import annotations

from contracts.bands import SANDBOX_CONFIDENCE_MIN
from contracts.signal import NormalizedSignal
from knowledge.api.read import get_subgraph
from knowledge.api.write import write_pending


async def maybe_fork(signal: NormalizedSignal, entity: str) -> None:
    """
    Called after triage returns HIGH. Runs in parallel with synthesis.
    If trajectory projection says P(crossing) > SANDBOX_CONFIDENCE_MIN, forks.
    """
    confidence = await _project_trajectory(signal, entity)
    if confidence < SANDBOX_CONFIDENCE_MIN:
        return

    projected_hours = await _estimate_crossing_hours(signal, entity)
    subgraph = await get_subgraph(entity, hops=2)

    sandbox_state = await _run_gnn_surrogate(subgraph, signal, confidence)
    scenario_ref  = await _prestage_systems(sandbox_state, confidence)

    await write_pending(
        confidence=confidence,
        projected_crossing_hours=projected_hours,
        scenario_ref=scenario_ref,
    )


async def _project_trajectory(signal: NormalizedSignal, entity: str) -> float:
    """
    Run Chronos-2 / TimesFM-2.5 on recent AIS gap frequency + war-risk premium series.
    Returns P(risk_score > 0.7 within 24h).
    Stub.
    """
    # TODO: load last 72h of price and AIS signals for entity from Graphiti
    # TODO: run Chronos-2 forecasting model
    # TODO: return probability
    return 0.0


async def _estimate_crossing_hours(signal: NormalizedSignal, entity: str) -> float:
    """Estimate hours until projected crossing. Stub."""
    return 18.0


async def _run_gnn_surrogate(subgraph: object, signal: NormalizedSignal, confidence: float) -> dict:
    """
    Apply projected risk parameters to subgraph snapshot, run PyTorch GNN forward pass.
    Same cascade propagation as scenario_agent but on speculative state, not live state.
    Target: <150ms on T4 GPU.
    Stub.
    """
    # TODO: import from scenario_agent.gnn.model and run inference
    return {}


async def _prestage_systems(sandbox_state: dict, confidence: float) -> str:
    """
    Run alt_procurement_agent and reserve_optim_agent against sandbox state.
    All outputs tagged status='speculative'. Returns scenario_ref id.
    Stub.
    """
    # TODO: call alt_procurement_agent.runner.run(sandbox_state, status="speculative")
    # TODO: call reserve_optim_agent.runner.run(sandbox_state, status="speculative")
    return "sandbox-stub-ref"
