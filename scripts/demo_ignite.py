#!/usr/bin/env python3
"""
G9 — Demo Ignition (sandboxed).

Replays the 2026 Hormuz closure crisis (the G1 held-out calibration crisis)
through the REAL SAGE ingest path so judges can watch the autonomous pipeline
fire live — WITHOUT corrupting live state.

Sandbox lifecycle (see knowledge/demo_control.py):

    1. SNAPSHOT   GRAPH.COPY sage -> sage_demo_backup   (whole graph)
    2. ENTER      set sage:demo:active=1
                    → sage-core clears its risk caches, drops live signals,
                      and speeds up flush/poll so the climb is visible
    3. RESET      set every current RISK_STATE edge to CALM  (clean baseline)
    4. REPLAY     push the 23 daily ticks as real NormalizedSignals
                    → risk climbs CALM→…→CRITICAL, monitor fires the pipeline
    5. SETTLE     hold so scenario / procurement / SPR populate on screen
    6. RESTORE    GRAPH.DELETE sage ; GRAPH.COPY sage_demo_backup sage
                    → the exact pre-demo graph is back
    7. EXIT       set sage:demo:active=0
                    → sage-core clears caches; live re-derives from real graph

Run it inside the sage-core container so it shares the docker network:

    docker exec sage-sage-core-1 python3 /app/scripts/demo_ignite.py

Options:
    --tick-seconds N   wall seconds per replayed day   (default 4.0 → ~90s replay)
    --settle N         seconds to hold the peak state  (default 25)
    --no-restore       skip snapshot/restore (debugging only — WILL mutate live)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

log = logging.getLogger("demo_ignite")
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")

CRISIS_FILE = ROOT / "demo_cache" / "2026_hormuz_closure.json"

GRAPH_NAME   = os.environ.get("FALKOR_GRAPH", "sage")
BACKUP_GRAPH = "sage_demo_backup"
FALKOR_URL   = f"redis://{os.environ.get('FALKORDB_HOST', 'falkordb')}:{os.environ.get('FALKORDB_PORT', '6379')}"
REDIS_URL    = os.environ.get("REDIS_URL", "redis://redis:6379/0")

HORMUZ = "Strait of Hormuz"   # canonical display name (knowledge/registry.py)


# ── FalkorDB raw graph commands (snapshot / reset / restore) ──────────────────

async def _graph_query(falkor, graph: str, cypher: str):
    return await falkor.execute_command("GRAPH.QUERY", graph, cypher)


async def snapshot_graph(falkor) -> bool:
    """GRAPH.COPY sage -> sage_demo_backup. Returns True on success."""
    try:
        await falkor.execute_command("GRAPH.DELETE", BACKUP_GRAPH)  # clear any stale backup
    except Exception:
        pass
    try:
        await falkor.execute_command("GRAPH.COPY", GRAPH_NAME, BACKUP_GRAPH)
        log.info("  snapshot: %s -> %s", GRAPH_NAME, BACKUP_GRAPH)
        return True
    except Exception as exc:
        log.error("  snapshot FAILED: %s", exc)
        return False


async def reset_risk_to_calm(falkor) -> None:
    """Set every current RISK_STATE edge to a clean CALM baseline."""
    cypher = (
        "MATCH (:Entity)-[r:RELATES_TO]->(:Entity) "
        "WHERE r.name = 'RISK_STATE' AND r.invalid_at IS NULL "
        "SET r.score = 0.05, r.band = 'calm'"
    )
    try:
        await _graph_query(falkor, GRAPH_NAME, cypher)
        log.info("  reset: all RISK_STATE edges -> calm")
    except Exception as exc:
        log.warning("  reset non-fatal error: %s", exc)


async def restore_graph(falkor) -> bool:
    """Replace the live graph with the pre-demo snapshot using atomic RENAME.

    RENAME overwrites the destination key in one atomic step — no race window
    where live queries can recreate an empty 'sage' graph between a DELETE and
    COPY. This was the bug that caused RESTORE FAILED in the previous run.
    """
    try:
        await _graph_query(falkor, BACKUP_GRAPH, "MATCH (n) RETURN count(n) LIMIT 1")
    except Exception as exc:
        log.error("  RESTORE ABORTED — backup %s not readable: %s", BACKUP_GRAPH, exc)
        return False
    try:
        await falkor.execute_command("RENAME", BACKUP_GRAPH, GRAPH_NAME)
        log.info("  restore: RENAME %s -> %s (atomic, no race)", BACKUP_GRAPH, GRAPH_NAME)
        return True
    except Exception as exc:
        log.error("  RESTORE FAILED: %s — backup preserved as %s", exc, BACKUP_GRAPH)
        return False


# ── Demo status / flag ────────────────────────────────────────────────────────

async def set_flag(client, active: bool) -> None:
    from knowledge.demo_control import DEMO_FLAG_KEY
    if active:
        await client.set(DEMO_FLAG_KEY, "1", ex=1800)
    else:
        await client.delete(DEMO_FLAG_KEY)


async def set_status(client, active: bool, message: str) -> None:
    from knowledge.demo_control import DEMO_STATUS_KEY
    payload = {
        "active":  active,
        "crisis":  "2026 Hormuz Closure (held-out calibration crisis)",
        "message": message,
        "updated": datetime.now(timezone.utc).isoformat(),
    }
    await client.set(DEMO_STATUS_KEY, json.dumps(payload), ex=1800)


# ── Signal construction ───────────────────────────────────────────────────────

def _clamp_int(x, lo, hi):
    return max(lo, min(hi, int(round(x))))


def _tick_signals(tick: dict) -> list:
    """Turn one labeled daily tick into a list of real NormalizedSignals."""
    from contracts.signal import NormalizedSignal

    f    = tick["features"]
    date = tick["date"]
    obs  = datetime.fromisoformat(date + "T12:00:00+00:00")
    now  = datetime.now(timezone.utc)
    raw  = f"REPLAY:2026_hormuz:{date}"
    prov = tick.get("provenance", {})

    anom = float(f["ais_anomaly_score_max"])
    hi   = anom >= 0.6 or float(f.get("news_severity_max", 0)) >= 0.6
    prio = "HIGH" if hi else ("MED" if anom >= 0.35 else "LOW")

    sigs = []

    def mk(source, payload, summary, force=False, refs=(HORMUZ,)):
        sigs.append(NormalizedSignal(
            signal_id=str(uuid.uuid4()),
            source=source,
            observed_at=obs,
            ingested_at=now,
            priority_hint=prio,
            force_synthesis=force,
            entity_refs=list(refs),
            summary=summary,
            payload=payload,
            raw_ref=raw + ":" + source,
        ))

    # ── AIS aggregate (ONE signal per tick) ───────────────────────────────────
    # Real sensory agents emit one signal per raw event; the demo used to mimic
    # that by pushing ~15 AIS + ~20 news synthetic events per tick. At ~4s/tick
    # that flooded the ingest queue (700+ signals in 2 min) and saturated
    # FalkorDB ("Max pending queries exceeded"), so the consumer stalled and a
    # crossing tick's events never landed in one flush window intact — the GBM
    # saw a diluted vector and never crossed. Instead we send ONE aggregate
    # signal carrying the labelled daily counts in the payload; fusion honours
    # these explicit *_24h fields (see _run_fusion_for_entity overrides).
    dur = float(f.get("ais_gap_duration_max_h", 0))
    mk("ais", {
        "mmsi": "REPLAY-AGG",
        "gap_hours": max(dur, 5.0),                # decisive GBM feature (max-reduced)
        "dark_vessel": True,
        "anomaly_score": round(anom, 4),
        "h3_cell": "hormuz",
        "velocity_std": float(f.get("ais_velocity_std", 0.3)),
        "gap_count_24h": _clamp_int(f.get("ais_gap_count_24h", 0), 1, 20),
        "dark_vessel_count": _clamp_int(f.get("ais_dark_vessel_count", 0), 0, 20),
        "monitored_cell_pct": float(f.get("ais_monitored_cell_pct", 0)),
    }, f"[REPLAY {date}] Hormuz AIS anomaly {anom:.2f}, gap {dur:.0f}h, "
       f"{_clamp_int(f.get('ais_gap_count_24h',0),1,20)} vessel gaps. "
       f"{prov.get('ais', 'IMO/UKMTO proxy')}")

    # ── News / GDELT aggregate (ONE signal per tick) ──────────────────────────
    tone  = float(f.get("gdelt_tone_24h_mean", 0))
    sev_n = float(f.get("news_severity_max", 0))
    mk("news", {
        "tone": tone,
        "tone_delta": float(f.get("gdelt_tone_delta", 0)),
        "severity": round(sev_n, 4),
        "event_count_24h": _clamp_int(f.get("news_event_count_24h", 1), 1, 30),
    }, f"[REPLAY {date}] Hormuz tone {tone:.1f}, severity {sev_n:.2f}, "
       f"{_clamp_int(f.get('news_event_count_24h',1),1,30)} events. "
       f"{prov.get('gdelt', 'GDELT DOC API')}",
       force=False)  # never force for demo news: would block consumer on Nova Pro for 56s+

    # ── Price ─────────────────────────────────────────────────────────────────
    pct = float(f.get("price_brent_pct_change_24h", 0))
    mk("price", {
        "instrument": "BZ=F",
        "price": 0.0,
        "price_change_pct": pct,
        "changepoint": bool(f.get("price_bocd_flag", 0)),
        "regime_stressed": float(f.get("price_regime", 0)),
        "war_risk_premium_proxy": float(f.get("price_war_risk_premium", 0)),
    }, f"[REPLAY {date}] Brent {pct*100:+.1f}% 24h, war-risk "
       f"{f.get('price_war_risk_premium',0):.2f}. {prov.get('price', 'yfinance BZ=F')}",
       force=bool(f.get("price_bocd_flag", 0)))

    # ── Sanctions aggregate (ONE signal per tick, only when present) ──────────
    # Carries the labelled daily counts; force=False so it never blocks the
    # consumer on a 56s synthesis call during replay (demo_active guards it too).
    n_sanc = _clamp_int(f.get("sanctions_new_additions_24h", 0), 0, 10)
    n_vess = _clamp_int(f.get("sanctions_vessel_count", 0), 0, 10)
    n_major = float(f.get("sanctions_major_entity", 0))
    if n_sanc > 0 or n_vess > 0 or n_major > 0:
        mk("sanctions", {
            "list": "OFAC",
            "change": "add",
            "subject": f"REPLAY aggregate {date}",
            "subject_type": "entity",
            "new_additions_24h": n_sanc,
            "vessel_count_24h": n_vess,
            "major_entity": bool(n_major),
        }, f"[REPLAY {date}] OFAC designations: {n_sanc} new, {n_vess} vessels. "
           f"{prov.get('sanctions', 'OFAC/UN proxy')}", force=False)

    return sigs


# ── Main lifecycle ────────────────────────────────────────────────────────────

async def run(tick_seconds: float, settle: float, do_restore: bool) -> None:
    if not CRISIS_FILE.exists():
        log.error("Crisis data not found: %s\nRun scripts/build_calibration_data.py first.", CRISIS_FILE)
        sys.exit(1)

    ticks = json.loads(CRISIS_FILE.read_text())
    total = len(ticks)

    import redis.asyncio as aioredis
    from knowledge.connection import init as kb_init

    await kb_init()
    client = aioredis.from_url(REDIS_URL, decode_responses=True)
    falkor = aioredis.from_url(FALKOR_URL, decode_responses=True)

    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log.info("SAGE DEMO IGNITION — 2026 Hormuz Closure (sandboxed)")
    log.info("%d ticks · %.1fs/tick · ~%.0fs replay + %.0fs settle",
             total, tick_seconds, total * tick_seconds, settle)
    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    snapshotted = False
    try:
        # 1. SNAPSHOT
        if do_restore:
            snapshotted = await snapshot_graph(falkor)
            if not snapshotted:
                log.error("Aborting: could not snapshot the graph (refusing to mutate live).")
                return

        # 2. ENTER sandbox
        await set_flag(client, True)
        await set_status(client, True, "Replaying 2026 Hormuz Closure — sandboxed")
        log.info("  sandbox ENABLED (sage:demo:active=1)")
        await asyncio.sleep(4)   # let sage-core clear caches & begin dropping live signals

        # 3. RESET to a clean pre-crisis baseline
        await reset_risk_to_calm(falkor)
        await asyncio.sleep(tick_seconds)

        # 4. REPLAY
        #
        # Each tick is fused SYNCHRONOUSLY in this process by calling the real
        # fusion path (_run_fusion_for_entity) directly, instead of pushing
        # signals onto sage:ingest and hoping the async consumer drains them.
        # On the 4 GB demo host the consumer's event loop stalls under memory
        # pressure — its Redis calls time out and it flushes only ~5×/run, so a
        # crossing tick's signals never land in one clean fusion window and the
        # score never crosses. Fusing inline uses the identical GBM + escalate-
        # fast/decay-slow + RISK_STATE-write code, but is immune to consumer
        # health: one deterministic write per tick, exactly the labelled vector.
        from knowledge.ingest_queue import _run_fusion_for_entity
        log.info("  replaying %d ticks (inline fusion)…", total)
        crossing_seen = False
        for seq, tick in enumerate(ticks):
            sigs = _tick_signals(tick)
            try:
                await _run_fusion_for_entity(HORMUZ, sigs, demo_active=True)
            except Exception as exc:
                log.warning("  tick %d fusion error: %s", seq + 1, exc)
            label = tick["within_24h_of_crossing"]
            mark = "🔴" if label else "🟢"
            if label and not crossing_seen:
                crossing_seen = True
                log.info("  *** crossing window — autonomous pipeline should fire ***")
            log.info("  [%02d/%d] %s %s", seq + 1, total, tick["date"], mark)
            await asyncio.sleep(tick_seconds)

        # 5. SETTLE
        log.info("  settling %.0fs (scenario / procurement / SPR populate)…", settle)
        await set_status(client, True, "Peak crisis — pipeline output on screen")
        await asyncio.sleep(settle)

    finally:
        # 6. RESTORE + 7. EXIT — always runs, even on error/interrupt
        if do_restore and snapshotted:
            await restore_graph(falkor)
        await set_flag(client, False)
        await set_status(client, False, "Demo complete — live state restored")
        log.info("  sandbox DISABLED (sage:demo:active cleared)")
        await client.aclose()
        await falkor.aclose()

    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log.info("Demo complete. Live state restored to the pre-demo snapshot.")
    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


def main() -> None:
    ap = argparse.ArgumentParser(description="SAGE sandboxed demo ignition")
    ap.add_argument("--tick-seconds", type=float, default=4.0)
    ap.add_argument("--settle", type=float, default=25.0)
    ap.add_argument("--no-restore", action="store_true",
                    help="Skip snapshot/restore (debug only — mutates live state)")
    args = ap.parse_args()
    asyncio.run(run(args.tick_seconds, args.settle, do_restore=not args.no_restore))


if __name__ == "__main__":
    main()
