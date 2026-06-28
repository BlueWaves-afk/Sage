"""
LangGraph state schema. Typed TypedDict so the state machine is fully type-checked.
"""
from __future__ import annotations

from typing import Optional
from typing_extensions import TypedDict


class SAGEState(TypedDict):
    """State carried through the LangGraph pipeline on every signal cycle."""
    signal_id: str
    entity: str
    risk_score: float
    risk_band: str
    sandbox_active: bool
    sandbox_confidence: float
    scenario_id: Optional[str]
    pipeline_stage: str     # "sense"|"triage"|"sage"|"sandbox"|"scenario"|"procure"|"reserve"
    error: Optional[str]
