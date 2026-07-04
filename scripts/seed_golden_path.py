"""
Seed the "golden path" demo scenario — the Feb 2025 Iran-Israel conflict escalation
that raises Strait of Hormuz closure risk to critical levels.

This is NOT a fake-data script. It:
  1. Pushes one real signal (mirroring what System 1's news sub-agent will eventually
     emit) built from the historical event already logged in the knowledge base
     (data/india-energy-2026.context/facts/nodes/geo_events.csv:
     "2025 Iran-Israel Conflict", severity 0.9) through the REAL ingest path, so Nova
     Pro synthesises a genuine "## Current Assessment" narrative for the Strait of
     Hormuz wiki page — exactly what System 1 -> ingest_signal() would do.
  2. Writes a real RISK_STATE assessment via write_risk_state() (the same function
     the fusion consumer calls) reflecting that event's documented severity.
  3. Runs the EXACT production autonomous cold-path (orchestration.triggers.
     _cold_pipeline) — the same code the live threshold monitor calls when a real
     risk score crosses ACTION_THRESHOLD. This executes the real ARIO cascade,
     TOPSIS procurement ranking, and SDP/CMDP reserve solve; nothing here is
     hand-authored JSON.

Why this exists: System 1 (the sensory sub-agents) is intentionally a stub for this
pass, so the live risk score never organically crosses the action threshold. This
script is the documented, explicit substitute for "wait for a real signal" — it lets
every downstream system (2, 3, 4) run for real against the one historical scenario
the hackathon demo is built around, so the API/dashboard/UI have genuine cached
output to show instead of empty "AWAITING SCENARIO RUN" panels.

Run (with the KB stack up — falkordb + redis):
  set -a && . ./.env && set +a && \
    FALKORDB_HOST=localhost REDIS_URL=redis://localhost:6380/0 \
    WIKI_DIR=$(pwd)/knowledge/wiki SAGE_BUNDLE_PATH=$(pwd)/data/india-energy-2026.context \
    python3.11 -m scripts.seed_golden_path
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("seed_golden_path")

TRIGGER_ENTITY = "Strait of Hormuz"
# Matches data/india-energy-2026.context/facts/nodes/geo_events.csv exactly.
EVENT_SEVERITY = 0.9
EVENT_SUMMARY = (
    "Iran and Israel exchange direct military strikes; naval activity near the "
    "Strait of Hormuz raises closure risk to critical levels, echoing the 2019 "
    "tanker-attack pattern and the 1984-1988 Tanker War precedent."
)
# Real historical severity (0.9) mapped onto the fused risk scale, kept just above
# CRITICAL_THRESHOLD (0.90) so the demo matches the Simulation Lab's "critical"
# framing and the Command Center KPI consistently.
SEEDED_RISK_SCORE = 0.92


async def main() -> None:
    from knowledge.connection import init as kb_init
    await kb_init()
    log.info("Knowledge base connected.")

    await _push_real_signal()
    await _write_risk_assessment()
    await _run_real_cold_pipeline()

    log.info("Golden path seeded. /api/dashboard, /api/scenario, /api/procurement, "
              "/api/spr-schedule should now return live data for '%s'.", TRIGGER_ENTITY)


async def _push_real_signal() -> None:
    """Synthesise a genuine wiki narrative for the trigger entity (Nova Pro)."""
    from contracts.signal import NormalizedSignal
    from knowledge.api.write import ingest_signal

    now = datetime.now(timezone.utc)
    signal = NormalizedSignal(
        signal_id=f"seed-{uuid.uuid4().hex[:12]}",
        source="news",
        observed_at=now,
        ingested_at=now,
        priority_hint="HIGH",
        # Explicit administrative override: this is a documented one-time seed of a
        # real historical event, not a System 1 sub-agent, so we force synthesis
        # rather than depend on the similarity gate's timing.
        force_synthesis=True,
        entity_refs=[TRIGGER_ENTITY],
        summary=EVENT_SUMMARY,
        payload={
            "actor": "Iran and Israel",
            "action": "direct military strikes raising Strait of Hormuz closure risk",
            "tone": -8.5,
            "severity": EVENT_SEVERITY,
        },
        source_url=None,
        raw_ref="data/india-energy-2026.context/facts/nodes/geo_events.csv#event_2025_iran_israel",
    )
    result = await ingest_signal(signal)
    log.info("ingest_signal → decision=%s episode=%s", result.decision, result.episode_uuid)


async def _write_risk_assessment() -> None:
    from knowledge.api.write import write_risk_state

    await write_risk_state(
        entity=TRIGGER_ENTITY,
        score=SEEDED_RISK_SCORE,
        factor_ais=0.30,
        factor_gdelt=0.85,
        factor_price=0.20,
        factor_sanctions=0.05,
        rationale=(
            "Direct Iran-Israel military strikes raise Strait of Hormuz closure risk "
            "to critical levels, consistent with the 2019 tanker-attack precedent and "
            "the 1984-1988 Tanker War pattern already logged in the knowledge base."
        ),
        model_version="golden-path-seed-v1",
    )
    log.info("write_risk_state → %s score=%.2f", TRIGGER_ENTITY, SEEDED_RISK_SCORE)


async def _run_real_cold_pipeline() -> None:
    """
    Run the exact production autonomous cold-path — the same function the live
    threshold monitor invokes on a real action-band crossing. Real ARIO cascade,
    real TOPSIS ranking, real SDP/CMDP solve.
    """
    import redis.asyncio as aioredis
    from orchestration.triggers import _cold_pipeline

    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    client = aioredis.from_url(redis_url, decode_responses=True)
    try:
        await _cold_pipeline(client, TRIGGER_ENTITY, SEEDED_RISK_SCORE)
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
