"""
Seed risk state from LIVE, REAL System-1 signals — zero authored/fake content.

Unlike seed_golden_path.py (which authors signal text to guarantee a crisis demo),
this runs the ACTUAL System-1 agent fetch functions against live feeds:
  - news:      _poll_newsdata_latest / _poll_newsdata_market / _poll_gdelt
  - prices:    _poll_prices  (yfinance Brent/WTI + BOCD)
  - sanctions: _diff_all_lists  (OFAC/EU/UN diffs)

Every signal it ingests is real and carries its own source_url. The knowledge base
fusion model then COMPUTES the current risk per entity from those real signals — so
the score reflects the ACTUAL current geopolitical situation, not a scripted one.

This is the honest "nothing fake" path. The computed risk is whatever reality is
right now; if the Gulf is calm today, the score will be low — and that's correct.

Run (KB stack up):
  FALKORDB_HOST=localhost REDIS_URL=redis://localhost:6380/0 \
    SAGE_BUNDLE_PATH=$(pwd)/data/india-energy-2026.context \
    python3.11 -m scripts.seed_from_live
"""
from __future__ import annotations

import asyncio
import logging
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from config_env import load_local_env
    load_local_env()
except Exception:
    pass

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("seed_from_live")


async def _collect_live_signals():
    """Run the real agent fetch functions and return every real signal they produce."""
    signals = []

    async def _safe(label, coro):
        try:
            out = await coro
            n = len(out or [])
            log.info("  %-22s → %d real signals", label, n)
            return out or []
        except Exception as exc:
            log.warning("  %-22s failed: %s", label, exc)
            return []

    from sensory_agent import news, prices, sanctions
    signals += await _safe("news: newsdata latest", news._poll_newsdata_latest())
    signals += await _safe("news: newsdata market", news._poll_newsdata_market())
    signals += await _safe("news: GDELT", news._poll_gdelt())
    signals += await _safe("prices: yfinance/BOCD", prices._poll_prices())
    signals += await _safe("sanctions: OFAC/EU/UN", sanctions._diff_all_lists())
    return signals


async def main() -> None:
    from knowledge.connection import init as kb_init
    from knowledge.api.write import ingest_signal
    from knowledge.ingest_queue import _run_fusion_for_entity
    from knowledge.api.read import get_risk_scores, get_supply_chain_index

    await kb_init()
    log.info("Knowledge base connected. Collecting LIVE signals from real feeds…")

    signals = await _collect_live_signals()
    if not signals:
        log.warning("No live signals returned right now (feeds quiet or filtered). "
                    "Nothing to fuse — the KB reflects that honestly.")
        return

    # Ingest every real signal (episode + synthesis) and group by referenced entity.
    by_entity: dict[str, list] = defaultdict(list)
    for s in signals:
        try:
            await ingest_signal(s)
        except Exception as exc:
            log.debug("ingest failed for %s: %s", s.signal_id, exc)
        for ent in (s.entity_refs or []):
            by_entity[ent].append(s)

    log.info("Ingested %d real signals referencing %d tracked entities.",
             len(signals), len(by_entity))

    # Fuse per entity → the KB COMPUTES each risk score from the real signals.
    for entity, sigs in by_entity.items():
        await _run_fusion_for_entity(entity, sigs)

    # Report the computed state (read back from the KB).
    scores = {r.entity: r for r in await get_risk_scores()}
    for entity in by_entity:
        r = scores.get(entity)
        if r:
            log.info("  KB-COMPUTED %-26s score=%.4f band=%s (as_of %s)",
                     entity, r.score, r.band, r.recorded_at)

    sci = await get_supply_chain_index()
    log.info("India Supply-Chain Stability Index (from live signals): %.4f (%s) "
             "over %d scored entities.", sci.index, sci.band, sci.entities_scored)
    log.info("Done — every score above was computed from real, cited live signals.")


if __name__ == "__main__":
    asyncio.run(main())
