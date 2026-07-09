"""
System 1 — Shared scaffolding for all sensory sub-agents.

The ONLY way a sub-agent touches the KB is through ``emit()``.
Sub-agents NEVER call ``ingest_signal``, ``write_risk_state``,
``add_episode``, or triage directly — the consumer loop does all of that.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from contracts.signal import NormalizedSignal
from knowledge.ingest_queue import push_signal

log = logging.getLogger(__name__)


def new_signal_id(prefix: str) -> str:
    """Generate a unique signal ID: ``<prefix>-<12-char hex>``."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def utcnow() -> datetime:
    """Return timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


async def emit(signal: NormalizedSignal) -> None:
    """
    The ONLY way a sub-agent touches the KB.

    Pushes the signal onto the Redis ingest queue; the consumer loop
    (``knowledge/ingest_queue.py``) pops it, runs triage, synthesis,
    fusion, and write_risk_state.
    """
    try:
        await push_signal(signal)
        log.info(
            "Emitted %s signal %s → entities=%s",
            signal.source,
            signal.signal_id,
            signal.entity_refs,
        )
    except Exception as exc:
        log.error("Failed to emit signal %s: %s", signal.signal_id, exc)
        raise
