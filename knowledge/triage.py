"""
SAGE triage gate.

Scores each incoming NormalizedSignal and decides which synthesis path to take.
Runs before narrative synthesis — keeps ~88% of signals out of the expensive Nova Pro path.

Decision logic:
  force_synthesis=True  → always HIGH (sanctions diffs, BOCD breakpoints, dark-vessel gaps)
  similarity > 0.72     → HIGH  → full narrative synthesis
  similarity > 0.40     → MED   → entity extraction only, no wiki update
  otherwise             → LOW   → store raw, no graphiti write
"""
from __future__ import annotations

from typing import Literal

from contracts.signal import NormalizedSignal

TriageDecision = Literal["synthesize", "extract", "store", "drop"]


async def triage(signal: NormalizedSignal) -> tuple[TriageDecision, float]:
    """
    Returns (decision, similarity_score).
    Stub — real implementation embeds the signal summary and compares
    cosine similarity against tracked entity embeddings from Graphiti.
    """
    if signal.force_synthesis:
        return "synthesize", 1.0

    # TODO: embed signal.summary via Bedrock Titan
    # TODO: query Graphiti for entity embeddings matching signal.entity_refs
    # TODO: compute max cosine similarity
    similarity: float = 0.0

    if similarity > 0.72:
        return "synthesize", similarity
    elif similarity > 0.40:
        return "extract", similarity
    else:
        return "store", similarity
