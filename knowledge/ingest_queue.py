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

Fusion model:
  The weighted sum below is the fallback when sensory_agent/fusion_model.pkl is
  absent. It is intentionally inside knowledge/ (never imports sensory_agent) so
  the KB container can run without the sensory containers. Once sensory_agent
  trains a GBM model, it writes the .pkl to a shared volume; the next flush
  loads it automatically. The interface contract is:
    predict(fv: _FeatureVector) -> _FusionResult
  Any drop-in replacement satisfying this protocol is accepted.

Import boundary:
  This module imports contracts/ and knowledge/api/ only. sensory_agent is never
  imported here — that would couple the KB container to the sensing container.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import pickle
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import redis.asyncio as aioredis

from contracts.signal import NormalizedSignal
from knowledge.api.write import ingest_signal, write_risk_state

log = logging.getLogger(__name__)

QUEUE_KEY         = os.environ.get("SAGE_INGEST_QUEUE", "sage:ingest")
REDIS_URL         = os.environ.get("REDIS_URL", "redis://redis:6379/0")
BATCH_SIZE        = int(os.environ.get("SAGE_BATCH_SIZE", "10"))
FLUSH_INTERVAL_S  = int(os.environ.get("SAGE_FLUSH_INTERVAL_S", "30"))
FUSION_MODEL_PATH = Path(os.environ.get("FUSION_MODEL_PATH", "sensory_agent/fusion_model.pkl"))
# Risk decay half-life (hours): a prior score halves after this long without
# reinforcing signals. Escalation is instant (max); recession is gradual.
RISK_HALF_LIFE_H  = float(os.environ.get("RISK_HALF_LIFE_H", "48"))

# In-process last-known RISK_STATE per entity: (score, recorded_wall_epoch_s).
# The consumer is the single writer, so this is authoritative and race-free —
# avoids a FalkorDB read-after-write consistency race when computing decay.
_last_risk: dict[str, tuple[float, float]] = {}

_signal_buffer: dict[str, list[NormalizedSignal]] = defaultdict(list)
_last_flush     = time.monotonic()
_fitted_model   = None   # loaded lazily from FUSION_MODEL_PATH when it exists


# ---------------------------------------------------------------------------
# Inline feature vector + weighted-sum fusion (no sensory_agent import)
# ---------------------------------------------------------------------------

@dataclass
class _FeatureVector:
    """17-dimensional feature vector. Mirrors sensory_agent.fusion.FeatureVector."""
    # AIS stream (6 features)
    ais_gap_count_24h:        float = 0.0
    ais_dark_vessel_count:    float = 0.0
    ais_anomaly_score_max:    float = 0.0
    ais_gap_duration_max_h:   float = 0.0
    ais_monitored_cell_pct:   float = 0.0
    ais_velocity_std:         float = 0.0
    # GDELT / news (4 features)
    gdelt_tone_24h_mean:      float = 0.0
    gdelt_tone_delta:         float = 0.0
    news_severity_max:        float = 0.0
    news_event_count_24h:     float = 0.0
    # Prices (4 features)
    price_brent_pct_change_24h: float = 0.0
    price_bocd_flag:            float = 0.0
    price_regime:               float = 0.0
    price_war_risk_premium:     float = 0.0
    # Sanctions (3 features)
    sanctions_new_additions_24h: float = 0.0
    sanctions_vessel_count:      float = 0.0
    sanctions_major_entity:      float = 0.0


@dataclass
class _FusionResult:
    score:            float
    factor_ais:       float
    factor_gdelt:     float
    factor_price:     float
    factor_sanctions: float
    rationale:        str
    model_version:    str


def _weighted_fusion(fv: _FeatureVector) -> _FusionResult:
    """
    Calibrated weighted-sum fallback. Replaced by GBM-Platt once trained.
    Each sub-index is normalised 0..1 before top-level weighting.
    """
    ais_raw = min(1.0, (
        0.35 * min(fv.ais_dark_vessel_count / 3.0, 1.0) +
        0.25 * min(fv.ais_gap_count_24h / 5.0, 1.0) +
        0.20 * fv.ais_anomaly_score_max +
        0.10 * min(fv.ais_gap_duration_max_h / 24.0, 1.0) +
        0.05 * fv.ais_monitored_cell_pct +
        0.05 * min(fv.ais_velocity_std / 5.0, 1.0)
    ))
    gdelt_raw = min(1.0, (
        0.40 * max(0.0, -fv.gdelt_tone_24h_mean / 10.0) +
        0.20 * max(0.0, -fv.gdelt_tone_delta / 5.0) +
        0.25 * fv.news_severity_max +
        0.15 * min(fv.news_event_count_24h / 5.0, 1.0)
    ))
    price_raw = min(1.0, (
        0.30 * min(abs(fv.price_brent_pct_change_24h) / 10.0, 1.0) +
        0.35 * fv.price_bocd_flag +
        0.20 * fv.price_regime +
        0.15 * min(fv.price_war_risk_premium, 1.0)
    ))
    sanctions_raw = min(1.0, (
        0.40 * min(fv.sanctions_new_additions_24h / 2.0, 1.0) +
        0.35 * fv.sanctions_major_entity +
        0.25 * min(fv.sanctions_vessel_count / 3.0, 1.0)
    ))

    score = 0.30 * ais_raw + 0.30 * gdelt_raw + 0.25 * price_raw + 0.15 * sanctions_raw

    dominant = sorted(
        [("AIS", ais_raw), ("GDELT", gdelt_raw),
         ("price", price_raw), ("sanctions", sanctions_raw)],
        key=lambda x: -x[1],
    )
    drivers = [f"{n} {v:.2f}" for n, v in dominant if v > 0.15]
    rationale = (
        f"dominant signals: {', '.join(drivers)} — weighted-sum fallback"
        if drivers else
        "weighted-sum fallback — train GBM for SHAP attributions"
    )

    return _FusionResult(
        score=round(min(1.0, score), 4),
        factor_ais=round(ais_raw, 4),
        factor_gdelt=round(gdelt_raw, 4),
        factor_price=round(price_raw, 4),
        factor_sanctions=round(sanctions_raw, 4),
        rationale=rationale,
        model_version="weighted-sum-v0",
    )


def _predict(fv: _FeatureVector) -> _FusionResult:
    """Load fitted GBM from shared volume if available; else use weighted sum."""
    global _fitted_model
    if _fitted_model is None and FUSION_MODEL_PATH.exists():
        try:
            with open(FUSION_MODEL_PATH, "rb") as f:
                _fitted_model = pickle.load(f)
            log.info("Loaded fitted fusion model from %s", FUSION_MODEL_PATH)
        except Exception as exc:
            log.warning("Failed to load fusion model: %s — using weighted sum", exc)

    if _fitted_model is not None:
        try:
            return _fitted_model.predict(fv)
        except Exception as exc:
            log.warning("Fitted model predict failed: %s — falling back to weighted sum", exc)

    return _weighted_fusion(fv)


# ---------------------------------------------------------------------------
# Consumer loop
# ---------------------------------------------------------------------------

async def run_consumer_loop() -> None:
    """
    Blocking consumer loop. Runs as a long-lived coroutine in the SAGE core container.
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
                await _handle_raw(raw, client)

            now = time.monotonic()
            global _last_flush
            if now - _last_flush >= FLUSH_INTERVAL_S:
                await _flush_risk_states()
                _last_flush = now

    finally:
        await client.aclose()


async def _handle_raw(raw: str, redis_client: Optional[object] = None) -> None:
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

        for entity in signal.entity_refs:
            _signal_buffer[entity].append(signal)

        for entity, buf in list(_signal_buffer.items()):
            if len(buf) >= BATCH_SIZE:
                await _run_fusion_for_entity(entity, buf)
                _signal_buffer[entity] = []

        # Fire sandbox fork in background for HIGH signals
        if signal.priority_hint == "HIGH":
            for entity in signal.entity_refs:
                asyncio.create_task(_maybe_sandbox_fork(signal, entity))
            # Second-brain learning: let the LLM refine dependency-edge exposure
            # weights bitemporally if this signal implies a supply-chain shift.
            # Background + best-effort so it never delays ingest.
            asyncio.create_task(_maybe_learn_edges(signal))
            # Refresh India supply chain brief (cooldown-gated, best-effort).
            asyncio.create_task(_refresh_india_brief())

    except Exception as exc:
        log.error("ingest_signal failed for %s: %s", signal.signal_id, exc)


async def _maybe_learn_edges(signal: NormalizedSignal) -> None:
    """Background: refine edge exposure weights from a dependency-changing signal."""
    try:
        from knowledge.edge_learning import learn_dependency_updates
        n = await learn_dependency_updates(signal)
        if n:
            log.info("[learn] refined %d edge weight(s) from signal %s", n, signal.signal_id)
    except Exception as exc:
        log.debug("[learn] edge learning non-fatal error: %s", exc)


async def _refresh_india_brief() -> None:
    """Background: re-synthesize the India supply chain situation brief (cooldown-gated)."""
    try:
        from knowledge.context.india_brief import refresh_india_brief
        await refresh_india_brief(force=False)
    except Exception as exc:
        log.debug("[india_brief] refresh non-fatal error: %s", exc)


async def _flush_risk_states() -> None:
    """Flush all buffered signals through fusion and write risk states."""
    for entity, buf in list(_signal_buffer.items()):
        if buf:
            await _run_fusion_for_entity(entity, buf)
            _signal_buffer[entity] = []


async def _run_fusion_for_entity(entity: str, signals: list[NormalizedSignal]) -> None:
    """Aggregate buffered signals, run fusion model, write RISK_STATE edge."""
    fv = _FeatureVector()

    ais_gap_count       = 0
    dark_count          = 0
    anomaly_max         = 0.0
    gap_duration_max    = 0.0
    monitored_cell_hits = 0
    velocity_stds: list[float] = []

    gdelt_tones: list[float]       = []
    gdelt_tone_deltas: list[float] = []
    severity_max  = 0.0
    event_count   = 0

    price_change      = 0.0
    bocd_flag         = 0.0
    price_regime      = 0.0
    war_risk_premium  = 0.0

    sanction_adds    = 0
    sanction_vessels = 0
    major_entity     = 0.0

    for sig in signals:
        p = sig.payload or {}

        if sig.source == "ais":
            gap_h = float(p.get("gap_hours", 0))
            if gap_h > 4:
                ais_gap_count += 1
            gap_duration_max = max(gap_duration_max, gap_h)
            if p.get("dark_vessel"):
                dark_count += 1
            anomaly_max = max(anomaly_max, float(p.get("anomaly_score", 0)))
            if p.get("h3_cell"):
                monitored_cell_hits += 1
            vstd = p.get("velocity_std")
            if vstd is not None:
                velocity_stds.append(float(vstd))

        elif sig.source in ("gdelt", "news"):
            tone = p.get("tone") or p.get("gdelt_tone")
            if tone is not None:
                gdelt_tones.append(float(tone))
            td = p.get("tone_delta")
            if td is not None:
                gdelt_tone_deltas.append(float(td))
            sev = float(p.get("severity", 0))
            severity_max = max(severity_max, sev)
            if sev > 0.7:
                event_count += 1

        elif sig.source == "price":
            price_change     = float(p.get("price_change_pct", price_change))
            bocd_flag        = 1.0 if (p.get("changepoint") or
                                        float(p.get("bocd_probability", 0)) > 0.8) else bocd_flag
            price_regime     = float(p.get("regime_stressed", price_regime))
            war_risk_premium = max(war_risk_premium, float(p.get("war_risk_premium_proxy", 0)))

        elif sig.source == "sanctions":
            if p.get("change") == "add":
                sanction_adds += 1
                if p.get("subject_type") in ("entity", "person", "state"):
                    major_entity = 1.0
            if p.get("vessel_mmsi"):
                sanction_vessels += 1

    n_ais = max(sum(1 for s in signals if s.source == "ais"), 1)

    fv.ais_gap_count_24h          = float(ais_gap_count)
    fv.ais_dark_vessel_count      = float(dark_count)
    fv.ais_anomaly_score_max      = anomaly_max
    fv.ais_gap_duration_max_h     = gap_duration_max
    fv.ais_monitored_cell_pct     = monitored_cell_hits / n_ais
    fv.ais_velocity_std           = sum(velocity_stds) / len(velocity_stds) if velocity_stds else 0.0
    fv.gdelt_tone_24h_mean        = sum(gdelt_tones) / len(gdelt_tones) if gdelt_tones else 0.0
    fv.gdelt_tone_delta           = sum(gdelt_tone_deltas) / len(gdelt_tone_deltas) if gdelt_tone_deltas else 0.0
    fv.news_severity_max          = severity_max
    fv.news_event_count_24h       = float(event_count)
    fv.price_brent_pct_change_24h = price_change
    fv.price_bocd_flag            = bocd_flag
    fv.price_regime               = price_regime
    fv.price_war_risk_premium     = war_risk_premium
    fv.sanctions_new_additions_24h = float(sanction_adds)
    fv.sanctions_vessel_count     = float(sanction_vessels)
    fv.sanctions_major_entity     = major_entity

    result      = _predict(fv)
    # Coerce to tz-aware UTC — live agents may emit naive datetimes, and mixing
    # naive/aware in max() raises. Normalise before comparing. (No local
    # `from datetime import timezone` anywhere else in this function — that
    # would make `timezone` local to the whole function body and break this
    # module-level reference with an UnboundLocalError.)
    def _aware(dt):
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    observed_at = max(_aware(s.observed_at) for s in signals)

    # ── Escalate-fast / decay-slow ────────────────────────────────────────────
    # A fresh fusion window must never ERASE a genuine crisis: a couple of benign
    # signals would otherwise overwrite a CRITICAL score outright. Blend the new
    # fusion score with the TIME-DECAYED prior and keep the higher of the two —
    # risk climbs instantly on strong signals, but only recedes gradually
    # (RISK_HALF_LIFE_H) as signals subside. Standard for alerting/risk systems.
    effective_score = result.score
    sustained = False
    try:
        # Prefer the in-process cache (race-free); fall back to a DB read on
        # cold start. Decay by WALL-CLOCK time since the prior was recorded.
        prior_score = None
        prior_epoch = None
        if entity in _last_risk:
            prior_score, prior_epoch = _last_risk[entity]
            elapsed_h = max(0.0, (time.time() - prior_epoch) / 3600.0)
        else:
            prior_score, prior_recorded = await _prior_risk_state(entity)
            elapsed_h = (
                max(0.0, (datetime.now(timezone.utc) - prior_recorded).total_seconds() / 3600.0)
                if prior_recorded is not None else RISK_HALF_LIFE_H
            )
        if prior_score is not None:
            decayed_prior = prior_score * (0.5 ** (elapsed_h / RISK_HALF_LIFE_H))
            if decayed_prior > effective_score:
                effective_score = decayed_prior
                sustained = True
    except Exception as exc:
        log.debug("prior risk-state read failed for '%s': %s", entity, exc)

    # Update the in-process cache with what we're about to persist.
    _last_risk[entity] = (effective_score, time.time())

    rationale = result.rationale
    if sustained:
        rationale = f"{result.rationale}; sustained from prior crisis (time-decayed)"

    log.info(
        "Risk state for '%s': score=%.3f band=%s [%s]",
        entity, effective_score, _band_from_score(effective_score), rationale,
    )

    try:
        from knowledge.agent_trace import publish_trace
        await publish_trace(
            system="1", agent="fusion",
            action=f"Computing risk fusion for {entity} ({len(signals)} signals)",
            status="started", entity=entity,
        )
    except Exception:
        pass

    try:
        await write_risk_state(
            entity=entity,
            score=effective_score,
            factor_ais=result.factor_ais,
            factor_gdelt=result.factor_gdelt,
            factor_price=result.factor_price,
            factor_sanctions=result.factor_sanctions,
            rationale=rationale,
            model_version=result.model_version,
            observed_at=observed_at,
        )
        try:
            from knowledge.agent_trace import publish_trace
            await publish_trace(
                system="1", agent="fusion",
                action=f"Risk score computed: {entity} → {effective_score:.2f} ({_band_from_score(effective_score)})",
                status="done", entity=entity,
            )
        except Exception:
            pass
        # Cascade this primary score to dependents across the supply-chain graph
        # (a risky corridor raises its refineries/ports; a sanctioned supplier
        # raises the refineries it feeds). Only ever raises risk, never lowers.
        try:
            from knowledge.cascade import cascade_risk_from
            await cascade_risk_from(entity, effective_score)
        except Exception as exc:
            log.debug("risk cascade from '%s' failed: %s", entity, exc)
    except Exception as exc:
        log.error("write_risk_state failed for '%s': %s", entity, exc)


async def _prior_risk_state(entity: str):
    """Return (score, recorded_at_datetime) for the entity's current RISK_STATE, else (None, None)."""
    from knowledge.api.read import get_risk_scores
    for r in await get_risk_scores():
        if r.entity == entity:
            ts = None
            try:
                ts = datetime.fromisoformat(str(r.recorded_at).replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            except Exception:
                ts = None
            return float(r.score), ts
    return None, None


async def _maybe_sandbox_fork(signal: NormalizedSignal, entity: str) -> None:
    """
    Background task: fire anticipatory sandbox fork for HIGH signals.
    Registers the resulting scenario_ref in Redis (72h TTL) so the monitor
    can promote it when the live threshold crosses.
    Non-fatal — failure is logged and swallowed.
    """
    try:
        from orchestration.sandbox import maybe_fork
        result = await maybe_fork(signal, entity)
        if result and result.confidence > 0:
            log.info(
                "Sandbox fork '%s': confidence=%.2f crossing≈%.0fh ref=%s",
                entity, result.confidence, result.projected_crossing_hours, result.scenario_ref,
            )
            client = aioredis.from_url(REDIS_URL, decode_responses=True)
            try:
                await client.setex(
                    f"sage:pending:{entity}",
                    72 * 3600,          # 72h TTL — matches C6 expiry contract
                    result.scenario_ref,
                )
            finally:
                await client.aclose()
    except Exception as exc:
        log.debug("Sandbox fork non-fatal error for '%s': %s", entity, exc)


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
