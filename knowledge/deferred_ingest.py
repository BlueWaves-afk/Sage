"""
Deferred LLM ingest — batch-at-EOD cost gate.

Signals whose fused risk score is below IMMEDIATE_INGEST_THRESHOLD (0.80) are
parked here instead of immediately firing Nova Pro synthesis + Graphiti
add_episode. A daily flush at EOD_FLUSH_UTC (default 23:50 UTC) processes
everything that accumulated during the day: one synthesis call per entity
(not one per signal) and one add_episode batch call, cutting Bedrock spend
~10× vs. per-signal processing.

High-risk signals (score ≥ 0.80), force_synthesis=True signals (sanctions,
BOCD price breakpoints), and demo-replay signals bypass the gate entirely and
are ingested immediately.

Flush can also be triggered manually (admin endpoint, or when score crosses the
threshold later in the day) via flush_entity() or flush_all_deferred().

Savings model (documented, not enforced):
  Current:  ~80 Nova Pro + ~240 Nova Micro + ~500 Titan calls/day  ≈ $0.80/day
  With gate: ~14 Nova Pro + ~24 Nova Micro + ~60 Titan calls/day   ≈ $0.09/day
  Savings:  ~89% reduction in Bedrock spend
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as aioredis

from contracts.signal import NormalizedSignal

log = logging.getLogger(__name__)

# Risk score at or above which ingest fires immediately (no deferral).
IMMEDIATE_INGEST_THRESHOLD = float(
    os.environ.get("SAGE_IMMEDIATE_INGEST_THRESHOLD", "0.80")
)

# UTC hour:minute at which the daily EOD flush runs (default 23:50).
EOD_FLUSH_UTC = os.environ.get("SAGE_EOD_FLUSH_UTC", "23:50")

# Redis key holding deferred signal JSON blobs per entity.
# Format: sage:deferred:{entity_slug} → Redis List of signal JSON strings.
_DEFERRED_KEY_PREFIX = "sage:deferred:"

# Per-entity deferred buffer (in-process, mirrors Redis for fast access).
# entity → list[NormalizedSignal]
_deferred: dict[str, list[NormalizedSignal]] = defaultdict(list)
_deferred_lock = asyncio.Lock()


def _entity_key(entity: str) -> str:
    slug = entity.lower().replace(" ", "_").replace("/", "-")
    return f"{_DEFERRED_KEY_PREFIX}{slug}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def defer_signal(signal: NormalizedSignal, entity: str, redis_url: str) -> None:
    """
    Park a signal for later batch processing. Called by ingest_queue when the
    fused risk score for the entity is below IMMEDIATE_INGEST_THRESHOLD.
    """
    async with _deferred_lock:
        _deferred[entity].append(signal)

    # Persist to Redis so the deferred list survives a container restart.
    try:
        client = aioredis.from_url(redis_url, decode_responses=True)
        try:
            await client.rpush(_entity_key(entity), signal.model_dump_json())
            # 36h TTL — signals older than that are stale and not worth ingesting.
            await client.expire(_entity_key(entity), 36 * 3600)
        finally:
            await client.aclose()
    except Exception as exc:
        log.debug("deferred Redis persist failed for '%s': %s", entity, exc)

    log.debug("Deferred signal %s for '%s' (%.0f pending)",
              signal.signal_id, entity, len(_deferred[entity]))


async def flush_entity(entity: str, redis_url: str) -> int:
    """
    Immediately process all deferred signals for one entity.
    Called when risk crosses IMMEDIATE_INGEST_THRESHOLD, or at EOD.
    Returns number of signals flushed.
    """
    async with _deferred_lock:
        signals = _deferred.pop(entity, [])

    if not signals:
        # Try recovering from Redis (e.g. after restart).
        signals = await _load_from_redis(entity, redis_url)

    if not signals:
        return 0

    log.info("[deferred] flushing %d signals for '%s'", len(signals), entity)
    await _batch_ingest(entity, signals)

    # Clear Redis deferred list.
    try:
        client = aioredis.from_url(redis_url, decode_responses=True)
        try:
            await client.delete(_entity_key(entity))
        finally:
            await client.aclose()
    except Exception as exc:
        log.debug("deferred Redis clear failed for '%s': %s", entity, exc)

    return len(signals)


async def flush_all_deferred(redis_url: str) -> int:
    """
    End-of-day flush: process all deferred signals across all entities.
    Returns total number of signals processed.
    """
    async with _deferred_lock:
        entities = list(_deferred.keys())

    # Also pick up any entities known only in Redis (post-restart).
    redis_entities = await _redis_deferred_entities(redis_url)
    all_entities = list(set(entities) | set(redis_entities))

    if not all_entities:
        log.info("[deferred] EOD flush: nothing to process")
        return 0

    log.info("[deferred] EOD flush: processing %d entities", len(all_entities))
    total = 0
    for entity in all_entities:
        try:
            n = await flush_entity(entity, redis_url)
            total += n
        except Exception as exc:
            log.error("[deferred] flush failed for '%s': %s", entity, exc)

    log.info("[deferred] EOD flush complete: %d signals processed across %d entities",
             total, len(all_entities))
    return total


def deferred_count(entity: Optional[str] = None) -> int:
    """Return count of in-process deferred signals (for metrics/logging)."""
    if entity:
        return len(_deferred.get(entity, []))
    return sum(len(v) for v in _deferred.values())


# ---------------------------------------------------------------------------
# Daily EOD flush scheduler
# ---------------------------------------------------------------------------

async def run_eod_flush_loop(redis_url: str) -> None:
    """
    Long-lived coroutine: fires flush_all_deferred() once per day at EOD_FLUSH_UTC.
    Launch as a background task alongside run_consumer_loop().
    """
    log.info("[deferred] EOD flush scheduler started (fires at %s UTC)", EOD_FLUSH_UTC)
    while True:
        seconds_until = _seconds_until_eod()
        log.debug("[deferred] next EOD flush in %.0fs", seconds_until)
        await asyncio.sleep(seconds_until)
        try:
            await flush_all_deferred(redis_url)
        except Exception as exc:
            log.error("[deferred] EOD flush error: %s", exc)
        # Sleep 70s after firing so we don't re-fire in the same minute.
        await asyncio.sleep(70)


def _seconds_until_eod() -> float:
    """Seconds from now until the next EOD_FLUSH_UTC wall-clock moment (UTC)."""
    now = datetime.now(timezone.utc)
    try:
        h, m = (int(x) for x in EOD_FLUSH_UTC.split(":"))
    except Exception:
        h, m = 23, 50

    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    delta = (target - now).total_seconds()
    if delta <= 0:
        delta += 86400  # already past today's window — fire tomorrow
    return delta


# ---------------------------------------------------------------------------
# Batch ingest: one synthesis call per entity, one add_episode per entity
# ---------------------------------------------------------------------------

async def _batch_ingest(entity: str, signals: list[NormalizedSignal]) -> None:
    """
    Consolidate a day's worth of signals for one entity into a single LLM call.

    Strategy:
    - Pick the highest-priority signal as the "anchor" for synthesis
      (it has the richest summary; its entity_refs drive the wiki update).
    - Build a combined episode body from all signal summaries (no extra LLM calls).
    - Call synthesize() once with the anchor signal (one Nova Pro call).
    - Call add_episode() once with the combined body (one Nova Micro + Titan call).
    """
    from knowledge.api.write import ingest_signal
    from contracts.signal import NormalizedSignal as _NS

    # Sort: force_synthesis first, then by priority (HIGH > MED > LOW).
    _priority_order = {"HIGH": 0, "MED": 1, "LOW": 2}
    sorted_sigs = sorted(
        signals,
        key=lambda s: (
            0 if s.force_synthesis else 1,
            _priority_order.get(s.priority_hint or "LOW", 2),
        ),
    )
    anchor = sorted_sigs[0]

    # Build a combined summary embedding all signals' summaries.
    combined_summary = anchor.summary
    if len(signals) > 1:
        extras = [
            f"[{s.source.upper()} {s.observed_at.strftime('%Y-%m-%d')}] {s.summary}"
            for s in sorted_sigs[1:]
        ]
        combined_summary = (
            f"{anchor.summary}\n\n"
            f"Additional signals accumulated since last synthesis "
            f"({len(signals) - 1} more):\n"
            + "\n".join(f"• {e}" for e in extras[:20])  # cap at 20 to stay in token budget
        )

    # Build a synthetic anchor signal with the combined summary.
    batch_signal = _NS(
        signal_id=anchor.signal_id,
        source=anchor.source,
        observed_at=anchor.observed_at,
        ingested_at=anchor.ingested_at,
        priority_hint=anchor.priority_hint,
        force_synthesis=True,   # bypass triage gate in ingest_signal
        entity_refs=anchor.entity_refs,
        summary=combined_summary,
        payload=anchor.payload,
        raw_ref=anchor.raw_ref,
        source_url=anchor.source_url,
    )

    try:
        result = await ingest_signal(batch_signal)
        log.info(
            "[deferred] batch ingest for '%s': %d signals → 1 episode (%s)",
            entity, len(signals), result.decision,
        )
    except Exception as exc:
        log.error("[deferred] batch ingest failed for '%s': %s", entity, exc)


# ---------------------------------------------------------------------------
# Redis helpers
# ---------------------------------------------------------------------------

async def _load_from_redis(entity: str, redis_url: str) -> list[NormalizedSignal]:
    """Load deferred signals from Redis (used after restart)."""
    signals: list[NormalizedSignal] = []
    try:
        client = aioredis.from_url(redis_url, decode_responses=True)
        try:
            raw_list = await client.lrange(_entity_key(entity), 0, -1)
        finally:
            await client.aclose()
        for raw in raw_list:
            try:
                signals.append(NormalizedSignal.model_validate(json.loads(raw)))
            except Exception:
                pass
    except Exception as exc:
        log.debug("Redis load for '%s' failed: %s", entity, exc)
    return signals


async def _redis_deferred_entities(redis_url: str) -> list[str]:
    """Scan Redis for all sage:deferred:* keys and return entity slugs."""
    entities: list[str] = []
    try:
        client = aioredis.from_url(redis_url, decode_responses=True)
        try:
            cursor = 0
            while True:
                cursor, keys = await client.scan(
                    cursor, match=f"{_DEFERRED_KEY_PREFIX}*", count=100
                )
                for key in keys:
                    entities.append(key.removeprefix(_DEFERRED_KEY_PREFIX))
                if cursor == 0:
                    break
        finally:
            await client.aclose()
    except Exception as exc:
        log.debug("Redis scan for deferred keys failed: %s", exc)
    return entities
