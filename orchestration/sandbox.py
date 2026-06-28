"""
Anticipatory Simulation Sandbox manager.

When a HIGH-priority signal arrives and P(crossing in 24h) > 0.5, this forks an
in-memory subgraph snapshot, projects signal trajectories, runs the GNN surrogate,
pre-stages Systems 3+4 outputs, and stores a PendingScenario in Graphiti.

Runs PARALLEL to the ground-truth synthesis branch — never blocks the main write path.
Total fork latency target: ~1,580ms.

Step timings:
  subgraph extraction   ~50ms
  trajectory projection ~80ms
  GNN surrogate        ~150ms
  Systems 3+4 pre-stage ~1,200ms
  PendingScenario write ~100ms

─────────────────────────────────────────────────────────────────────────────
TRAJECTORY PREDICTION — Mathematical Formulation (Weakness 3 addressed)
─────────────────────────────────────────────────────────────────────────────

We do NOT predict whether a geopolitical event will happen — that is exogenous
and unpredictable. We predict the OBSERVABLE SIGNAL METRICS that precede a
threshold crossing, given that an escalation has already begun.

Two-stage approach:

Stage 1 — Time-series forecasting (Chronos-2 / TimesFM-2.5)
  Input:  Last 72h of two observable series at 30-min resolution:
            x_ais(t)   = AIS gap frequency in monitored H3 cells
            x_price(t) = war-risk premium proxy (GDELT tone + insurance news)
  Model:  Chronos-2 (Amazon, arXiv 2410.09028) — pretrained zero-shot transformer
          for univariate time series. Produces:
            x̂_ais(t+Δ), x̂_price(t+Δ)  for Δ ∈ {6, 12, 18, 24, 36, 48, 72}h
          with quantile uncertainty bands (10th, 50th, 90th percentile).
  Output: 7-step forecast matrix [2 × 7] with quantile bands.

Stage 2 — Threshold crossing probability (Bayesian Filter)
  Given the forecast, compute P(risk_score(t+Δ) > θ_action) where θ_action=0.70.
  Using the fusion model (sensory_agent/fusion.py), the risk score is a function
  of the feature vector. We approximate:

    P(crossing within 24h) = P(max_{Δ≤24h} r(x̂(t+Δ)) > 0.70)

  where r(·) is the fusion model. We evaluate this by:
    1. Drawing N=500 sample paths from the forecast quantile distribution
       (quantile interpolation, no Gaussian assumption needed).
    2. Running the fusion model on each sample path.
    3. Fraction of paths where max risk > θ_action = P(crossing).

  This is fast: 500 × 7-step paths × cheap fusion model inference ≈ 30ms.

Stage 3 — Crossing time estimate
  Median of the crossing times across the N paths that do cross:
    t̂_cross = median({t : r(x̂_path_i(t)) > θ_action, path_i crosses})
  Confidence interval: [10th, 90th] percentile of crossing times.

Counterfactual scenarios (Weakness 5 extension)
  The sandbox also generates 3 counterfactual futures automatically:
    CF1: "Crisis resolves in 5 days" — x_ais decays exponentially, price reverts
    CF2: "Brent falls below $65"     — price series shocked downward
    CF3: "Russia increases exports"  — alternative supplier risk drops
  Each CF runs the same 3-stage pipeline and stores a separate PendingScenario
  with status='counterfactual'. Judges can explore these via the copilot.
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Optional

from contracts.bands import SANDBOX_CONFIDENCE_MIN, ACTION_THRESHOLD
from contracts.signal import NormalizedSignal
from knowledge.api.read import get_subgraph
from knowledge.api.write import write_pending

N_SAMPLE_PATHS = 500   # Monte Carlo paths for P(crossing) estimate
FORECAST_HORIZON_H = 72
FORECAST_STEPS = [6, 12, 18, 24, 36, 48, 72]   # hours ahead


@dataclass
class TrajectoryForecast:
    """Output of Stage 1 — Chronos-2 time series forecast."""
    entity: str
    horizon_hours: list[int] = field(default_factory=lambda: FORECAST_STEPS)
    # median forecasts
    ais_gap_freq_median: list[float] = field(default_factory=list)    # gaps/hour
    war_risk_premium_median: list[float] = field(default_factory=list)
    # uncertainty bands (10th and 90th percentile)
    ais_gap_freq_p10: list[float] = field(default_factory=list)
    ais_gap_freq_p90: list[float] = field(default_factory=list)
    war_risk_p10: list[float] = field(default_factory=list)
    war_risk_p90: list[float] = field(default_factory=list)


@dataclass
class SandboxResult:
    """Full output of the sandbox fork for one entity."""
    entity: str
    confidence: float           # P(risk_score > 0.70 within 24h)
    projected_crossing_hours: float
    crossing_ci_hours: tuple[float, float]   # 10th–90th percentile CI
    scenario_ref: str
    # Counterfactual summaries (Weakness 5)
    counterfactuals: list[dict] = field(default_factory=list)


async def maybe_fork(signal: NormalizedSignal, entity: str) -> Optional[SandboxResult]:
    """
    Called after triage returns HIGH. Runs parallel to synthesis — never awaited in main path.
    Returns SandboxResult if fork fires, None otherwise.
    """
    forecast = await _forecast_trajectories(signal, entity)
    confidence, crossing_h, crossing_ci = _compute_crossing_probability(forecast)

    if confidence < SANDBOX_CONFIDENCE_MIN:
        return None

    subgraph = await get_subgraph(entity, hops=2)
    sandbox_state = await _run_gnn_surrogate(subgraph, signal, forecast)
    scenario_ref = await _prestage_systems(entity, sandbox_state, confidence)

    # Generate counterfactual futures in parallel
    cf_tasks = [
        _counterfactual_fork(entity, signal, "crisis_resolves_5d"),
        _counterfactual_fork(entity, signal, "brent_below_65"),
        _counterfactual_fork(entity, signal, "russia_export_surge"),
    ]
    counterfactuals = await asyncio.gather(*cf_tasks, return_exceptions=True)
    cf_results = [r for r in counterfactuals if isinstance(r, dict)]

    await write_pending(
        confidence=confidence,
        projected_crossing_hours=crossing_h,
        scenario_ref=scenario_ref,
    )

    return SandboxResult(
        entity=entity,
        confidence=confidence,
        projected_crossing_hours=crossing_h,
        crossing_ci_hours=crossing_ci,
        scenario_ref=scenario_ref,
        counterfactuals=cf_results,
    )


async def _forecast_trajectories(signal: NormalizedSignal, entity: str) -> TrajectoryForecast:
    """
    Stage 1: Chronos-2 zero-shot forecast of AIS gap frequency and war-risk premium.

    Implementation notes:
    - Load last 72h of signal history for entity from Graphiti episodic store.
    - Resample to 30-min ticks (forward-fill for AIS, VWAP for price).
    - Run chronos_client.predict(context, prediction_length=len(FORECAST_STEPS))
    - Return quantile outputs.

    Stub — implement with `pip install chronos-forecasting` in Week 2.
    """
    # TODO: query Graphiti for last 72h of ais_gap_count and war_risk_premium signals
    # TODO: from chronos import ChronosPipeline
    # TODO: pipeline = ChronosPipeline.from_pretrained("amazon/chronos-t5-large")
    # TODO: quantiles, _ = pipeline.predict_quantiles(context, prediction_length=7,
    #           quantile_levels=[0.1, 0.5, 0.9])
    # Return stub with flat lines (zero escalation) as safe fallback
    n = len(FORECAST_STEPS)
    return TrajectoryForecast(
        entity=entity,
        ais_gap_freq_median=[0.0] * n,
        war_risk_premium_median=[0.0] * n,
        ais_gap_freq_p10=[0.0] * n,
        ais_gap_freq_p90=[0.0] * n,
        war_risk_p10=[0.0] * n,
        war_risk_p90=[0.0] * n,
    )


def _compute_crossing_probability(
    forecast: TrajectoryForecast,
) -> tuple[float, float, tuple[float, float]]:
    """
    Stage 2+3: Monte Carlo over forecast paths → P(crossing), median crossing time.

    Each sample path is drawn by quantile interpolation across the 10th–90th
    band (no Gaussian assumption — the distribution can be skewed for crisis signals).
    The fusion model maps each path's feature vector to a risk score.
    """
    import random

    crossing_times: list[float] = []

    for _ in range(N_SAMPLE_PATHS):
        for i, horizon_h in enumerate(FORECAST_STEPS):
            # Sample from quantile band via linear interpolation at uniform U[0,1]
            u = random.random()
            ais_sample = (
                forecast.ais_gap_freq_p10[i] +
                u * (forecast.ais_gap_freq_p90[i] - forecast.ais_gap_freq_p10[i])
            )
            price_sample = (
                forecast.war_risk_p10[i] +
                u * (forecast.war_risk_p90[i] - forecast.war_risk_p10[i])
            )

            # Approximate risk score from two dominant features (full fusion needs all 17)
            # This is intentionally lightweight — full fusion adds ~5ms per path
            approx_risk = min(1.0, 0.35 * min(ais_sample / 5, 1.0) + 0.25 * price_sample)

            if approx_risk > ACTION_THRESHOLD:
                crossing_times.append(float(horizon_h))
                break

    if not crossing_times:
        return 0.0, float("inf"), (float("inf"), float("inf"))

    confidence = len(crossing_times) / N_SAMPLE_PATHS
    crossing_times_sorted = sorted(crossing_times)
    median_h = crossing_times_sorted[len(crossing_times_sorted) // 2]
    p10_h = crossing_times_sorted[int(0.10 * len(crossing_times_sorted))]
    p90_h = crossing_times_sorted[int(0.90 * len(crossing_times_sorted))]

    return confidence, median_h, (p10_h, p90_h)


async def _run_gnn_surrogate(
    subgraph: object,
    signal: NormalizedSignal,
    forecast: TrajectoryForecast,
) -> dict:
    """
    Apply projected risk parameters to subgraph snapshot, run PyTorch GNN forward pass.
    Same cascade propagation as scenario_agent but on speculative state.
    Target: <150ms on T4 GPU.
    Stub.
    """
    # TODO: build node feature matrix from subgraph + forecast.ais_gap_freq_median[3] (24h)
    # TODO: load CascadeGNN from scenario_agent.gnn.model
    # TODO: model.forward(subgraph_features, projected_risk_params)
    return {"feedstock_gap_mbpd": 0.0, "price_impact_usd_bbl": 0.0}


async def _prestage_systems(
    entity: str,
    sandbox_state: dict,
    confidence: float,
) -> str:
    """
    Run alt_procurement_agent and reserve_optim_agent against sandbox state.
    All outputs tagged status='speculative'. Returns scenario_ref id.
    """
    scenario_ref = f"sandbox-{uuid.uuid4().hex[:8]}"
    # TODO: call alt_procurement_agent.runner.run(scenario_ref, entity, status="speculative")
    # TODO: call reserve_optim_agent.runner.run(scenario_ref, gap_mbpd, gap_days, status="speculative")
    return scenario_ref


async def _counterfactual_fork(
    entity: str,
    signal: NormalizedSignal,
    scenario_type: str,
) -> dict:
    """
    Generate a counterfactual future by applying a hypothetical shock to the
    baseline forecast and re-running the crossing probability estimate.

    scenario_type:
      'crisis_resolves_5d'  — AIS gap frequency decays to zero over 5 days
      'brent_below_65'      — war-risk premium shocked to 0, price drops 20%
      'russia_export_surge' — supplier risk for Russian corridors halved
    """
    # TODO: apply scenario-specific perturbation to forecast
    # TODO: re-run _compute_crossing_probability on perturbed forecast
    # TODO: return {scenario_type, confidence_cf, crossing_h_cf, delta_vs_baseline}
    return {
        "type": scenario_type,
        "confidence": 0.0,
        "crossing_hours": float("inf"),
        "note": "stub — implement counterfactual perturbation in Week 2",
    }
