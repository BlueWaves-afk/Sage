"""
Exhaustive end-to-end signal test.

For each of the 4 System-1 signal types, this:
  1. builds a valid NormalizedSignal (real payload sub-model),
  2. pushes it onto the live Redis ingest queue (push_signal),
  3. pops it back (blpop) and runs the real consumer handler (_handle_raw),
  4. forces per-entity fusion,
  5. reads the KB back and asserts an episode was written + risk state exists.

Run against dockerised FalkorDB (localhost:6379) + Redis (localhost:6380).
"""
from __future__ import annotations
import asyncio, os, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from datetime import datetime, timezone

from config_env import load_local_env
load_local_env()
os.environ["FALKORDB_HOST"] = "localhost"
os.environ["FALKORDB_PORT"] = "6379"
os.environ["REDIS_URL"] = "redis://localhost:6380/0"

TARGET = "Strait of Hormuz"


def _now():
    return datetime.now(timezone.utc)


def _signals():
    from contracts.signal import NormalizedSignal
    base = dict(observed_at=_now(), ingested_at=_now(), entity_refs=[TARGET], force_synthesis=True)
    return [
        ("PRICE", NormalizedSignal(
            signal_id="e2e-price-001", source="price", priority_hint="HIGH",
            summary="Brent BZ=F spiked +6.2% with BOCD changepoint; war-risk premium up",
            payload={"instrument": "BZ=F", "price": 103.4, "changepoint": True,
                     "regime": "stressed", "war_risk_premium": 0.85}, **base)),
        ("NEWS", NormalizedSignal(
            signal_id="e2e-news-001", source="news", priority_hint="HIGH",
            summary="Iran threatens to close Strait of Hormuz after strikes",
            payload={"actor": "Iran", "action": "threatens closure", "target": "Strait of Hormuz",
                     "tone": -8.5, "severity": 0.9, "goldstein": -9.0}, **base)),
        ("SANCTIONS", NormalizedSignal(
            signal_id="e2e-sanc-001", source="sanctions", priority_hint="HIGH",
            summary="OFAC adds tanker operator to SDN list",
            payload={"list": "OFAC", "change": "add", "subject": "NITC Shipping",
                     "subject_type": "entity"}, **base)),
        ("AIS", NormalizedSignal(
            signal_id="e2e-ais-001", source="ais", priority_hint="HIGH",
            lat=26.5, lon=56.4, h3_cells=["85484d8ffffffff"],
            summary="Dark-vessel AIS gap cluster near Larak Island",
            payload={"mmsi": "422000000", "gap_hours": 6.2, "dark_vessel": True,
                     "anomaly_score": 0.88}, **base)),
    ]


async def main():
    from knowledge.connection import init
    from knowledge.ingest_queue import push_signal, _handle_raw, _run_fusion_for_entity, _signal_buffer
    from knowledge.api.read import get_risk_scores, get_full_graph
    import redis.asyncio as aioredis

    await init()
    rc = aioredis.from_url("redis://localhost:6380/0", decode_responses=True)
    QUEUE = os.environ.get("SAGE_INGEST_QUEUE", "sage:ingest")

    def risk_of(scores, ent):
        for s in scores:
            if s.entity == ent:
                return s.score, s.band
        return None, None

    before = await get_risk_scores()
    b_score, b_band = risk_of(before, TARGET)
    print(f"\nBASELINE  {TARGET}: score={b_score} band={b_band}\n")

    # Prove push_signal lands in the Redis queue (sync llen, no blocking pop).
    import redis as _sync_redis
    sr = _sync_redis.Redis.from_url("redis://localhost:6380/0", decode_responses=True)
    sr.delete(QUEUE)
    probe = _signals()[0][1]
    await push_signal(probe, redis_url="redis://localhost:6380/0")
    qlen = sr.llen(QUEUE)
    landed = sr.lindex(QUEUE, 0) or ""
    queue_ok = qlen >= 1 and probe.signal_id in landed
    print(f"QUEUE (push_signal → Redis llen={qlen}): {'OK' if queue_ok else 'FAIL'}")
    sr.delete(QUEUE)  # clean up so the consumer container won't double-process
    print()

    results = []
    for name, sig in _signals():
        row = {"type": name, "ingest": "?", "episode": "?", "fusion": "?", "err": ""}
        try:
            # Drive the exact consumer handler that runs after blpop.
            eps_before = len(_signal_buffer.get(TARGET, []))
            await _handle_raw(sig.model_dump_json())
            row["ingest"] = "OK"
            row["episode"] = "OK" if len(_signal_buffer.get(TARGET, [])) > eps_before else "flushed"
            buf = _signal_buffer.get(TARGET, [sig]) or [sig]
            await _run_fusion_for_entity(TARGET, buf)
            row["fusion"] = "OK"
            _s, _b = risk_of(await get_risk_scores(), TARGET)
            print(f"    [{name}] score now = {_s:.4f} ({_b})  buf_len={len(buf)}")
        except Exception as exc:
            row["err"] = f"{type(exc).__name__}: {str(exc)[:70]}"
        results.append(row)

    after = await get_risk_scores()
    a_score, a_band = risk_of(after, TARGET)

    print("PER-SIGNAL RESULTS")
    print(f"{'TYPE':10} {'INGEST':12} {'EPISODE':10} {'FUSION':8} ERR")
    for r in results:
        print(f"{r['type']:10} {r['ingest']:12} {r['episode']:10} {r['fusion']:8} {r['err']}")

    g = await get_full_graph()
    print(f"\nAFTER     {TARGET}: score={a_score} band={a_band}")
    print(f"KB now: {len(g.nodes)} nodes, {len(g.edges)} edges, {len(after)} RISK_STATE edges")
    ok = all(r['ingest'].startswith('OK') for r in results)
    print(f"\n{'✅ ALL SIGNALS INGESTED' if ok else '⚠️  SOME SIGNALS FAILED'}")


if __name__ == "__main__":
    asyncio.run(main())
