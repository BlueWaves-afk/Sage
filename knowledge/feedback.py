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
    Count feedback records. If >= RETRAIN_THRESHOLD, queue a retrain job.
    In production this would post to a job queue. For the hackathon, it prints
    a visible log line that the operator can act on.
    """
    if not FEEDBACK_LOG.exists():
        return
    count = sum(1 for _ in open(FEEDBACK_LOG))
    if count >= RETRAIN_THRESHOLD and count % RETRAIN_THRESHOLD == 0:
        print(
            f"[FEEDBACK] {count} outcome records accumulated. "
            f"Run `python -m sensory_agent.fusion --calibrate` to re-fit the model."
        )
        # TODO: post to job queue in production: queue.push("retrain-fusion-model")


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
