"""
C7 — Write API. The only entry points for writing to the knowledge base.

All agents call these functions. None of them import graphiti_core directly.
Stubs — implement bodies in Week 2 after schema is locked.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

from contracts.outputs import ProcurementRecData, ScenarioOutputData, SPRScheduleData
from contracts.signal import NormalizedSignal


class EpisodeRef(BaseModel):
    episode_uuid: str
    scenario_id: Optional[str] = None


class IngestResult(BaseModel):
    signal_id: str
    decision: Literal["synthesized", "extracted", "stored", "dropped"]
    episode_uuid: Optional[str] = None
    risk_updated: bool = False


async def ingest_signal(signal: NormalizedSignal) -> IngestResult:
    """
    Main entry point for all raw signals from sensory_agent.
    Flow: triage → (synthesize | extract | store) → add_episode → risk propagation.
    """
    # TODO: call triage.triage(signal)
    # TODO: if synthesize → call synthesis.synthesize() for each entity_ref
    # TODO: build episode_text with risk score embedded in prose
    # TODO: call graphiti.add_episode(entity_types=..., edge_types=..., edge_type_map=...)
    # TODO: write RISK_STATE edge if score provided
    raise NotImplementedError


async def write_scenario(data: ScenarioOutputData) -> EpisodeRef:
    """scenario_agent calls this after ARIO + GNN cascade completes."""
    # TODO: build episode prose from data fields
    # TODO: call graphiti.add_episode() with ScenarioOutput entity type
    # TODO: write AFFECTS_SCENARIO edge back to trigger entity
    raise NotImplementedError


async def write_procurement(data: ProcurementRecData) -> EpisodeRef:
    """alt_procurement_agent calls this after TOPSIS ranking completes."""
    raise NotImplementedError


async def write_spr_schedule(data: SPRScheduleData) -> EpisodeRef:
    """reserve_optim_agent calls this after SDP/CMDP solve completes."""
    raise NotImplementedError


async def write_pending(confidence: float, projected_crossing_hours: float, scenario_ref: str) -> EpisodeRef:
    """
    Sandbox calls this to persist a PendingScenario node.
    Must NEVER write a RISK_STATE edge on a live node — speculative outputs are isolated.
    """
    raise NotImplementedError


async def promote_pending(scenario_ref: str) -> EpisodeRef:
    """
    LangGraph monitor calls this when live risk_score crosses ACTION_THRESHOLD.
    Flips PendingScenario.status to 'promoted' and all linked output episodes to 'confirmed'.
    """
    raise NotImplementedError
