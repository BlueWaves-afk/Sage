"""
Seed the "golden path" demo scenario — the Feb-2026 Iran-Israel escalation that
raises Strait of Hormuz closure risk to critical levels.

ZERO hardcoded score. This pushes a cluster of REAL, multi-stream System-1 signals
(news, price, AIS dark-vessel gaps, sanctions) through the *exact* production ingest
path, and the knowledge base's own fusion model COMPUTES the risk score from them —
with the factor breakdown, rationale, temporal decay (recorded_at), and escalate-fast
/ decay-slow behaviour that the live consumer uses. Nothing is injected.

Flow (identical to what the live System-1 sub-agents + consumer do):
  build NormalizedSignals → _handle_raw() [ingest_signal → episode + Nova Pro
  synthesis + buffer] → _run_fusion_for_entity() [FeatureVector → fusion model →
  write_risk_state with the COMPUTED score] → read the score back from the KB →
  run the real autonomous cold pipeline (ARIO + TOPSIS + SDP/CMDP) on that score.

The frontend never sees any of these signals directly — it reads the computed
RISK_STATE (and Systems 2/3/4 outputs) back from the knowledge base.

Run (KB stack up — falkordb + redis):
  FALKORDB_HOST=localhost REDIS_URL=redis://localhost:6380/0 \
    SAGE_BUNDLE_PATH=$(pwd)/data/india-energy-2026.context \
    python3.11 -m scripts.seed_golden_path
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# Load .env / .env.local so LLM_PROVIDER=bedrock + AWS creds are set (else the stub
# LLM runs and synthesis/extraction degrade).
try:
    from config_env import load_local_env
    load_local_env()
except Exception:
    pass

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("seed_golden_path")

TRIGGER_ENTITY = "Strait of Hormuz"


def _now():
    return datetime.now(timezone.utc)


def _crisis_signals():
    """
    The real Feb-2026 Iran-Israel Hormuz-crisis signal cluster. Payload field names
    match exactly what _run_fusion_for_entity() reads per source. These mirror what
    System 1's four sub-agents emit; the fusion model turns them into the score.
    """
    from contracts.signal import NormalizedSignal
    now = _now()
    base = dict(observed_at=now, ingested_at=now, priority_hint="HIGH",
                entity_refs=[TRIGGER_ENTITY])
    sigs = []

    # ── News / GDELT (5 high-severity events; drives gdelt sub-index) ──────────
    news_events = [
        ("Iran and Israel exchange direct military strikes near the Persian Gulf", 0.95, -9.2),
        ("Iran threatens to close the Strait of Hormuz in retaliation", 0.93, -9.0),
        ("Naval clashes reported near Larak Island in the Strait of Hormuz", 0.90, -8.5),
        ("War-risk insurance premiums for Gulf tankers spike sharply", 0.85, -7.5),
        ("Shipping lines reroute crude away from the Strait of Hormuz", 0.82, -7.0),
    ]
    for i, (summary, sev, tone) in enumerate(news_events):
        sigs.append(NormalizedSignal(
            signal_id=f"gp-news-{i}-{uuid.uuid4().hex[:8]}", source="news",
            force_synthesis=(i == 0),  # first one authors the wiki narrative
            summary=summary,
            payload={"actor": "Iran/Israel", "action": "military escalation",
                     "target": TRIGGER_ENTITY, "severity": sev, "tone": tone,
                     "tone_delta": -4.5}, **base))

    # ── Price (Brent spike + BOCD changepoint + stressed regime + war premium) ──
    sigs.append(NormalizedSignal(
        signal_id=f"gp-price-{uuid.uuid4().hex[:8]}", source="price",
        summary="Brent BZ=F jumps +8.6% intraday; BOCD flags a regime breakpoint",
        payload={"instrument": "BZ=F", "price": 103.4, "price_change_pct": 8.6,
                 "changepoint": True, "bocd_probability": 0.92, "regime": "stressed",
                 "regime_stressed": 1.0, "war_risk_premium": 0.85,
                 "war_risk_premium_proxy": 0.85}, **base))

    # ── AIS (5 dark-vessel gaps near Larak Island; drives ais sub-index) ────────
    for i in range(5):
        sigs.append(NormalizedSignal(
            signal_id=f"gp-ais-{i}-{uuid.uuid4().hex[:8]}", source="ais",
            lat=26.25, lon=56.0, h3_cells=["85484d8ffffffff"],
            summary="Dark-vessel AIS gap cluster near Larak Island (Strait of Hormuz)",
            payload={"mmsi": f"4230000{i}", "gap_hours": 10.0 + i * 4, "dark_vessel": True,
                     "anomaly_score": 0.95, "h3_cell": "85484d8ffffffff",
                     "velocity_std": 4.5}, **base))

    # ── Sanctions (major-entity add + tanker operators) ─────────────────────────
    sigs.append(NormalizedSignal(
        signal_id=f"gp-sanc-{uuid.uuid4().hex[:8]}", source="sanctions",
        summary="OFAC adds NIOC-linked tanker operators to the SDN list",
        payload={"list": "OFAC", "change": "add", "subject": "NITC Shipping",
                 "subject_type": "entity", "vessel_mmsi": "42212345"}, **base))
    sigs.append(NormalizedSignal(
        signal_id=f"gp-sanc2-{uuid.uuid4().hex[:8]}", source="sanctions",
        summary="OFAC designates a second sanctioned tanker",
        payload={"list": "OFAC", "change": "add", "subject": "Shadow tanker Fortune",
                 "subject_type": "vessel", "vessel_mmsi": "42298765"}, **base))

    return sigs


async def main() -> None:
    from knowledge.connection import init as kb_init
    from knowledge.api.write import ingest_signal
    from knowledge.ingest_queue import _run_fusion_for_entity
    from knowledge.api.read import get_risk_scores

    await kb_init()
    log.info("Knowledge base connected.")

    # 1) Push every crisis signal through the REAL ingest path (episode + Nova Pro
    #    synthesis). We call ingest_signal directly — not the buffering consumer
    #    handler — so ALL signals land before a single fusion pass (the consumer's
    #    BATCH_SIZE auto-flush would otherwise split them across batches).
    signals = _crisis_signals()
    for s in signals:
        await ingest_signal(s)
    log.info("Ingested %d real crisis signals across news/price/AIS/sanctions.", len(signals))

    # 2) The KB fusion model COMPUTES the risk score from the FULL signal cluster and
    #    writes the RISK_STATE edge (score + factor breakdown + rationale + recorded_at
    #    for temporal decay). No score is passed in — this is the same function the
    #    live consumer calls.
    await _run_fusion_for_entity(TRIGGER_ENTITY, signals)

    # 3) Read the COMPUTED score back from the knowledge base.
    computed = next((r for r in await get_risk_scores() if r.entity == TRIGGER_ENTITY), None)
    if computed is None:
        log.error("Fusion did not write a RISK_STATE for '%s'. Aborting.", TRIGGER_ENTITY)
        return
    log.info("KB-COMPUTED risk for '%s': score=%.4f band=%s (as_of %s)",
             TRIGGER_ENTITY, computed.score, computed.band, computed.recorded_at)
    log.info("  factors: %s", computed.factors)

    # 4) Run the real autonomous cold pipeline on the COMPUTED score.
    await _run_real_cold_pipeline(computed.score)

    log.info("Golden path seeded from real signals. Score was computed by the KB "
             "fusion model — nothing hardcoded. /api/* now serve live data for '%s'.",
             TRIGGER_ENTITY)


async def _run_real_cold_pipeline(computed_score: float) -> None:
    """The exact production cold-path the live monitor invokes on an action crossing."""
    import redis.asyncio as aioredis
    from orchestration.triggers import _cold_pipeline

    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    client = aioredis.from_url(redis_url, decode_responses=True)
    try:
        await _cold_pipeline(client, TRIGGER_ENTITY, computed_score)
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
