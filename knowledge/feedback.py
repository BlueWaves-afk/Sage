"""
Outcome feedback loop for SAGE.

SAGE is an anticipatory system — it predicts disruptions before they happen.
Without a feedback loop, there is no way to know if it predicted correctly,
and the model never improves. This module closes that loop.

Design
------
Feedback is triggered by two events:
  1. A PendingScenario is promoted (crisis confirmed) — the prediction was TRUE.
  2. A PendingScenario expires without promotion — the prediction was FALSE.

In both cases we record:
  - The prediction: confidence, crossing_hours, risk band at prediction time
  - The outcome: did the crossing happen? When? What was the actual peak risk?
  - The feature vector at prediction time (from FusionResult stored in the episode)

These records accumulate in demo_cache/feedback_log.jsonl. When 50+ records
accumulate, `python -m sensory_agent.fusion --calibrate` re-trains the GBM model
and re-calibrates the thresholds.

This is a genuine feedback loop: the system's own predictions become training
data for the next model version.

Episodic feedback to Graphiti
------------------------------
We also write a feedback episode back into the knowledge graph so the copilot
can reason about prediction accuracy. Episode body:

  "SAGE predicted [action] crossing for [entity] on [date] with confidence 0.73.
   Outcome: [confirmed|expired]. Actual peak risk: 0.82. Prediction error: -0.09.
   Lead time accuracy: predicted in 18h, actual crossing in 22h (error: +4h)."

This lets a human analyst (or judge) ask: "How accurate has SAGE been?" and
get cited, episode-backed answers.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

FEEDBACK_LOG = Path(os.environ.get("FEEDBACK_LOG_PATH", "demo_cache/feedback_log.jsonl"))
RETRAIN_THRESHOLD = 50   # re-trigger calibration after this many feedback records

# ── Scenario-level outcome ledger (Feature B) ──────────────────────────────
# Separate from FEEDBACK_LOG above: that ledger scores the risk CROSSING
# (System 1 fusion). This ledger scores the scenario's predicted IMPACT
# (gap/price/spr/gdp — System 2) against what actually happened.
SCENARIO_OUTCOMES_LOG = Path(os.environ.get("SCENARIO_OUTCOMES_LOG_PATH", "demo_cache/scenario_outcomes.jsonl"))
CALIB_THRESHOLD = 20     # realized records per corridor before a correction factor is fit


async def record_confirmed_outcome(
    scenario_id: str,
    entity: str,
    predicted_confidence: float,
    predicted_crossing_hours: float,
    actual_crossing_hours: float,
    actual_peak_risk: float,
    feature_vector_at_prediction: dict,
) -> None:
    """
    Called by promote_pending() in knowledge/api/write.py when a scenario is confirmed.
    Records a TRUE POSITIVE feedback event.
    """
    record = {
        "event_type": "confirmed",
        "scenario_id": scenario_id,
        "entity": entity,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "predicted_confidence": predicted_confidence,
        "predicted_crossing_hours": predicted_crossing_hours,
        "actual_crossing_hours": actual_crossing_hours,
        "actual_peak_risk": actual_peak_risk,
        "lead_time_error_hours": actual_crossing_hours - predicted_crossing_hours,
        "confidence_calibration_error": actual_peak_risk - predicted_confidence,
        "features": feature_vector_at_prediction,
        # Label for re-training: this was a real crossing → positive
        "within_24h_of_crossing": True,
    }
    _append_record(record)
    await _write_feedback_episode(record)
    await _maybe_trigger_retrain()


async def record_expired_outcome(
    scenario_id: str,
    entity: str,
    predicted_confidence: float,
    predicted_crossing_hours: float,
    feature_vector_at_prediction: dict,
) -> None:
    """
    Called by a TTL check when a PendingScenario expires without promotion.
    Records a FALSE POSITIVE feedback event.
    """
    record = {
        "event_type": "expired",
        "scenario_id": scenario_id,
        "entity": entity,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "predicted_confidence": predicted_confidence,
        "predicted_crossing_hours": predicted_crossing_hours,
        "actual_crossing_hours": None,
        "actual_peak_risk": None,
        "lead_time_error_hours": None,
        "confidence_calibration_error": None,
        "features": feature_vector_at_prediction,
        # Label for re-training: no crossing happened → negative
        "within_24h_of_crossing": False,
    }
    _append_record(record)
    await _write_feedback_episode(record)
    await _maybe_trigger_retrain()


def _append_record(record: dict) -> None:
    """Append one JSON-lines record to the feedback log."""
    FEEDBACK_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(FEEDBACK_LOG, "a") as f:
        f.write(json.dumps(record) + "\n")


async def _write_feedback_episode(record: dict) -> None:
    """
    Write a feedback episode to Graphiti so copilot can cite accuracy history.
    Uses the same ingest path as live signals to maintain single write-path rule.
    """
    from contracts.signal import NormalizedSignal
    from knowledge.api.write import ingest_signal
    import uuid

    outcome_str = "CONFIRMED" if record["event_type"] == "confirmed" else "EXPIRED (false positive)"
    lead_info = ""
    if record.get("actual_crossing_hours") is not None:
        error = record["lead_time_error_hours"]
        lead_info = f" Predicted crossing in {record['predicted_crossing_hours']:.0f}h, actual: {record['actual_crossing_hours']:.0f}h (error: {error:+.0f}h)."
    calibration_info = ""
    if record.get("confidence_calibration_error") is not None:
        err = record["confidence_calibration_error"]
        calibration_info = f" Confidence calibration error: {err:+.2f}."

    body = (
        f"SAGE predicted action crossing for {record['entity']} "
        f"with confidence {record['predicted_confidence']:.2f}. "
        f"Outcome: {outcome_str}.{lead_info}{calibration_info}"
    )

    signal = NormalizedSignal(
        signal_id=f"feedback-{uuid.uuid4().hex[:8]}",
        source="news",          # SignalSource is a Literal alias, not an enum
        observed_at=datetime.now(timezone.utc),
        ingested_at=datetime.now(timezone.utc),
        priority_hint="LOW",    # Priority is a Literal alias, not an enum
        force_synthesis=True,
        entity_refs=[record["entity"], record["scenario_id"]],
        h3_cells=[],
        summary=body,
        payload={"feedback_record": record},
    )
    # Re-use the single write-path; triage will forward to synthesis
    await ingest_signal(signal)


async def _maybe_trigger_retrain() -> None:
    """
    Count feedback records. If >= RETRAIN_THRESHOLD, enqueue a real retrain job
    on the `sage:jobs` Redis list — drained by orchestration/monitor.py's poll
    loop, which actually runs `sensory_agent.fusion --calibrate` in-process.
    """
    if not FEEDBACK_LOG.exists():
        return
    count = sum(1 for _ in open(FEEDBACK_LOG))
    if count >= RETRAIN_THRESHOLD and count % RETRAIN_THRESHOLD == 0:
        log.info("%d outcome records accumulated — enqueueing fusion retrain job", count)
        try:
            import json as _json
            import os as _os
            import redis.asyncio as _aioredis
            client = _aioredis.from_url(_os.environ.get("REDIS_URL", "redis://redis:6379/0"),
                                        decode_responses=True)
            try:
                await client.lpush("sage:jobs", _json.dumps({"job": "calibrate_fusion", "count": count}))
            finally:
                await client.aclose()
        except Exception as exc:
            log.warning("Failed to enqueue retrain job (non-fatal): %s", exc)


def get_accuracy_summary() -> Optional[dict]:
    """
    Read feedback log and return a summary of prediction accuracy.
    Called by the copilot API to answer "How accurate has SAGE been?"
    """
    if not FEEDBACK_LOG.exists():
        return None

    records = []
    with open(FEEDBACK_LOG) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    if not records:
        return None

    confirmed = [r for r in records if r["event_type"] == "confirmed"]
    expired = [r for r in records if r["event_type"] == "expired"]
    total = len(records)

    precision = len(confirmed) / total if total > 0 else 0.0
    lead_errors = [r["lead_time_error_hours"] for r in confirmed if r.get("lead_time_error_hours") is not None]
    mean_lead_error = sum(lead_errors) / len(lead_errors) if lead_errors else None

    return {
        "total_predictions": total,
        "confirmed": len(confirmed),
        "expired_false_positives": len(expired),
        "precision": round(precision, 3),
        "mean_lead_time_error_hours": round(mean_lead_error, 1) if mean_lead_error is not None else None,
        "records_until_retrain": RETRAIN_THRESHOLD - (total % RETRAIN_THRESHOLD),
    }


# ---------------------------------------------------------------------------
# Scenario-level outcome ledger (Feature B) — was the predicted IMPACT right?
# ---------------------------------------------------------------------------

def record_scenario_prediction(
    scenario_id: str,
    entity: str,
    params: dict,
    predicted: dict,
) -> None:
    """
    Called automatically right after a scenario's output is stored (both
    auto-triggered and user-run). Writes the prediction half of an outcome
    record; the realized half is filled in later by `record_scenario_realized`.

    predicted = {gap_mbpd, price_impact_high, spr_depletion_days, gdp_proxy_impact_pct}
    """
    record = {
        "scenario_id": scenario_id,
        "entity": entity,
        "params": params,
        "predicted": predicted,
        "realized": None,
        "source": None,
        "predicted_at": datetime.now(timezone.utc).isoformat(),
        "realized_at": None,
        "error": None,
    }
    _append_scenario_record(record)


def record_scenario_realized(scenario_id: str, realized: dict, source: str) -> Optional[dict]:
    """
    Fill in the realized half of a prediction record and compute per-axis error.
    `source` in {"eia", "ais", "analyst"} — always shown in the UI so provenance
    of "what actually happened" is never ambiguous. Returns the updated record,
    or None if the scenario_id has no matching prediction.
    """
    if not SCENARIO_OUTCOMES_LOG.exists():
        return None

    lines = SCENARIO_OUTCOMES_LOG.read_text().splitlines()
    updated = None
    out_lines = []
    for line in lines:
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec["scenario_id"] == scenario_id and rec.get("realized") is None:
            pred = rec["predicted"]
            error = {}
            for k, v in realized.items():
                if v is not None and pred.get(k) is not None and pred[k] != 0:
                    error[k] = round((v - pred[k]) / abs(pred[k]), 4)
            rec["realized"] = realized
            rec["source"] = source
            rec["realized_at"] = datetime.now(timezone.utc).isoformat()
            rec["error"] = error
            updated = rec
        out_lines.append(json.dumps(rec))
    if updated is not None:
        SCENARIO_OUTCOMES_LOG.write_text("\n".join(out_lines) + "\n")
    return updated


def _append_scenario_record(record: dict) -> None:
    SCENARIO_OUTCOMES_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(SCENARIO_OUTCOMES_LOG, "a") as f:
        f.write(json.dumps(record) + "\n")


def get_scenario_accuracy() -> Optional[dict]:
    """
    Aggregate scenario-level prediction accuracy: per-axis MAPE across all
    realized outcomes, plus a per-corridor breakdown (feeds calibration).
    """
    if not SCENARIO_OUTCOMES_LOG.exists():
        return None

    records = [json.loads(l) for l in SCENARIO_OUTCOMES_LOG.read_text().splitlines() if l.strip()]
    realized = [r for r in records if r.get("realized") is not None]
    if not realized:
        return {"total_predictions": len(records), "realized": 0, "mape": {}, "per_corridor": {}}

    axes = ["gap_mbpd", "price_impact_high", "spr_depletion_days", "gdp_proxy_impact_pct"]
    mape: dict[str, dict] = {}
    for axis in axes:
        errs = [abs(r["error"][axis]) for r in realized if r.get("error", {}).get(axis) is not None]
        if errs:
            mape[axis] = {"mape": round(sum(errs) / len(errs), 4), "n": len(errs)}

    per_corridor: dict[str, dict] = {}
    by_entity: dict[str, list] = {}
    for r in realized:
        by_entity.setdefault(r["entity"], []).append(r)
    for entity, recs in by_entity.items():
        gap_errs = [r["error"]["gap_mbpd"] for r in recs if r.get("error", {}).get("gap_mbpd") is not None]
        price_errs = [r["error"]["price_impact_high"] for r in recs if r.get("error", {}).get("price_impact_high") is not None]
        per_corridor[entity] = {
            "n": len(recs),
            "mape_gap": round(sum(abs(e) for e in gap_errs) / len(gap_errs), 4) if gap_errs else None,
            "mape_price": round(sum(abs(e) for e in price_errs) / len(price_errs), 4) if price_errs else None,
        }

    return {
        "total_predictions": len(records),
        "realized": len(realized),
        "mape": mape,
        "per_corridor": per_corridor,
    }


async def maybe_calibrate_corridor(entity: str) -> Optional[dict]:
    """
    If a corridor has >= CALIB_THRESHOLD realized outcomes, fit a bounded scalar
    correction (gap_x, price_x) that centers the mean signed error toward zero,
    and persist it via knowledge.api.write.write_calibration_factor.

    Deliberately simple and auditable — not a black-box model. Bounded to
    [0.5, 1.5] at the write layer. Returns the fitted factor dict, or None if
    not enough data yet.
    """
    if not SCENARIO_OUTCOMES_LOG.exists():
        return None
    records = [json.loads(l) for l in SCENARIO_OUTCOMES_LOG.read_text().splitlines() if l.strip()]
    recs = [r for r in records if r["entity"] == entity and r.get("realized") is not None]
    if len(recs) < CALIB_THRESHOLD:
        return None

    def _mean_ratio(axis: str) -> float:
        ratios = []
        for r in recs:
            pred = r["predicted"].get(axis)
            real = r["realized"].get(axis)
            if pred and real and pred != 0:
                ratios.append(real / pred)
        return sum(ratios) / len(ratios) if ratios else 1.0

    gap_x = _mean_ratio("gap_mbpd")
    price_x = _mean_ratio("price_impact_high")

    from knowledge.api.write import write_calibration_factor
    await write_calibration_factor(entity, gap_x, price_x, len(recs))
    return {"entity": entity, "gap_x": round(gap_x, 3), "price_x": round(price_x, 3), "n": len(recs)}
