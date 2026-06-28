"""
Redis-backed ingest queue between sensory_agent and knowledge/api/write.py.

Architecture:
  sensory_agent sub-agents push NormalizedSignal JSON onto a Redis list.
  SAGE core (this module) pops from the same list in a consumer loop.
  The queue is the only coupling between sensing and the KB — no direct imports.

  Queue key: SAGE_INGEST_QUEUE (configurable via env var)

  sensory_agent pushes:    redis.rpush(QUEUE_KEY, signal.model_dump_json())
  SAGE core pops:          redis.blpop(QUEUE_KEY, timeout=1)

Risk state write:
  After every BATCH_SIZE signals (default 10) or every FLUSH_INTERVAL_S (30s),
  the fusion model is run across all signals in the current window and
  write_risk_state() is called for each entity that had signals.

Usage (called from the SAGE core container startup):
  from knowledge.ingest_queue import run_consumer_loop
  await run_consumer_loop()
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as aioredis

from contracts.signal import NormalizedSignal
from knowledge.api.write import ingest_signal, write_risk_state

log = logging.getLogger(__name__)

QUEUE_KEY        = os.environ.get("SAGE_INGEST_QUEUE", "sage:ingest")
REDIS_URL        = os.environ.get("REDIS_URL", "redis://redis:6379/0")
BATCH_SIZE       = int(os.environ.get("SAGE_BATCH_SIZE", "10"))
FLUSH_INTERVAL_S = int(os.environ.get("SAGE_FLUSH_INTERVAL_S", "30"))

# Per-entity signal buffer for fusion aggregation
_signal_buffer: dict[str, list[NormalizedSignal]] = defaultdict(list)
_last_flush     = time.monotonic()


async def run_consumer_loop() -> None:
    """
    Blocking consumer loop. Runs as a long-lived coroutine in the SAGE core container.
    Pops signals from Redis, processes them, and periodically triggers fusion writes.
    """
    client = aioredis.from_url(REDIS_URL, decode_responses=True)
    log.info("SAGE ingest consumer started. Queue: %s", QUEUE_KEY)

    try:
        while True:
            try:
                result = await client.blpop(QUEUE_KEY, timeout=1)
            except Exception as exc:
                log.error("Redis blpop error: %s — retrying in 5s", exc)
                await asyncio.sleep(5)
                continue

            if result:
                _, raw = result
                await _handle_raw(raw)

            # Flush fusion results if interval elapsed
            now = time.monotonic()
            global _last_flush
            if now - _last_flush >= FLUSH_INTERVAL_S:
                await _flush_risk_states()
                _last_flush = now

    finally:
        await client.aclose()


async def _handle_raw(raw: str) -> None:
    """Deserialise one signal JSON and hand it to ingest_signal()."""
    try:
        data   = json.loads(raw)
        signal = NormalizedSignal.model_validate(data)
    except Exception as exc:
        log.error("Malformed signal JSON: %s | raw=%.200s", exc, raw)
        return

    try:
        result = await ingest_signal(signal)
        log.debug("Ingested %s → %s", signal.signal_id, result.decision)

        # Buffer signal for fusion aggregation
        for entity in signal.entity_refs:
            _signal_buffer[entity].append(signal)

        # Flush if buffer for any entity is large enough
        for entity, buf in list(_signal_buffer.items()):
            if len(buf) >= BATCH_SIZE:
                await _run_fusion_for_entity(entity, buf)
                _signal_buffer[entity] = []

    except Exception as exc:
        log.error("ingest_signal failed for %s: %s", signal.signal_id, exc)


async def _flush_risk_states() -> None:
    """Flush all buffered signals through fusion and write risk states."""
    for entity, buf in list(_signal_buffer.items()):
        if buf:
            await _run_fusion_for_entity(entity, buf)
            _signal_buffer[entity] = []


async def _run_fusion_for_entity(
    entity: str,
    signals: list[NormalizedSignal],
) -> None:
    """
    Aggregate buffered signals for one entity through the fusion model,
    then write a RISK_STATE edge to the graph.
    """
    from sensory_agent.fusion import FeatureVector, get_model

    model = get_model()

    # Build a FeatureVector by scanning the buffered signals
    fv = FeatureVector()
    ais_gap_count   = 0
    dark_count      = 0
    anomaly_max     = 0.0
    gdelt_tones     = []
    severity_max    = 0.0
    event_count     = 0
    price_change    = 0.0
    bocd_flag       = 0.0
    sanction_adds   = 0
    sanction_vessels = 0
    major_entity    = 0.0

    for sig in signals:
        payload = sig.payload or {}
        if sig.source == "ais":
            ais_gap_count  += 1 if payload.get("gap_hours", 0) > 4 else 0
            dark_count     += 1 if payload.get("dark_vessel") else 0
            anomaly_max     = max(anomaly_max, float(payload.get("anomaly_score", 0)))
        elif sig.source in ("gdelt", "news"):
            tone = payload.get("tone")
            if tone is not None:
                gdelt_tones.append(float(tone))
            severity_max = max(severity_max, float(payload.get("severity", 0)))
            if float(payload.get("severity", 0)) > 0.7:
                event_count += 1
        elif sig.source == "price":
            price_change = float(payload.get("price_change_pct", price_change))
            bocd_flag    = 1.0 if payload.get("changepoint") else bocd_flag
        elif sig.source == "sanctions":
            if payload.get("change") == "add":
                sanction_adds += 1
                if payload.get("subject_type") in ("entity", "person"):
                    major_entity = 1.0

    fv.ais_gap_count_24h        = float(ais_gap_count)
    fv.ais_dark_vessel_count    = float(dark_count)
    fv.ais_anomaly_score_max    = anomaly_max
    fv.gdelt_tone_24h_mean      = (sum(gdelt_tones) / len(gdelt_tones)) if gdelt_tones else 0.0
    fv.news_severity_max        = severity_max
    fv.news_event_count_24h     = float(event_count)
    fv.price_brent_pct_change_24h = price_change
    fv.price_bocd_flag          = bocd_flag
    fv.sanctions_new_additions_24h = float(sanction_adds)
    fv.sanctions_vessel_count   = float(sanction_vessels)
    fv.sanctions_major_entity   = major_entity

    result = model.predict(fv)

    observed_at = max(s.observed_at for s in signals)

    log.info(
        "Risk state for '%s': score=%.3f band=%s [%s]",
        entity, result.score, _band_from_score(result.score), result.rationale,
    )

    try:
        await write_risk_state(
            entity=entity,
            score=result.score,
            factor_ais=result.factor_ais,
            factor_gdelt=result.factor_gdelt,
            factor_price=result.factor_price,
            factor_sanctions=result.factor_sanctions,
            rationale=result.rationale,
            model_version=result.model_version,
            observed_at=observed_at,
        )
    except Exception as exc:
        log.error("write_risk_state failed for '%s': %s", entity, exc)


def _band_from_score(score: float) -> str:
    from contracts.bands import score_to_band
    return score_to_band(score)


async def push_signal(signal: NormalizedSignal, redis_url: str = REDIS_URL) -> None:
    """
    Push a NormalizedSignal onto the ingest queue.
    Called by sensory_agent sub-agents.
    """
    client = aioredis.from_url(redis_url, decode_responses=True)
    try:
        await client.rpush(QUEUE_KEY, signal.model_dump_json())
    finally:
        await client.aclose()
