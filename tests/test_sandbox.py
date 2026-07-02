"""
Anticipatory sandbox unit tests — pure forecast/crossing/counterfactual logic.

No live services: these exercise the statistical forecast, the fusion-faithful
crossing-probability estimate, and the counterfactual perturbations directly.
"""
from __future__ import annotations

from orchestration.sandbox import (
    TrajectoryForecast, FORECAST_STEPS,
    _project_series, _compute_crossing_probability, _perturb_forecast, _projected_severity,
)


def _forecast(ais_med, price_med, ais_band=1.0, price_band=0.15):
    n = len(FORECAST_STEPS)
    return TrajectoryForecast(
        entity="Strait of Hormuz",
        ais_gap_freq_median=[ais_med] * n,
        ais_gap_freq_p10=[max(0.0, ais_med - ais_band)] * n,
        ais_gap_freq_p90=[ais_med + ais_band] * n,
        war_risk_premium_median=[price_med] * n,
        war_risk_p10=[max(0.0, price_med - price_band)] * n,
        war_risk_p90=[min(1.0, price_med + price_band)] * n,
    )


def test_project_series_bands_ordered_and_trending():
    med, p10, p90 = _project_series([1.0, 1.8, 2.6, 3.4], cap=10.0)
    assert len(med) == len(FORECAST_STEPS)
    assert all(p10[i] <= med[i] <= p90[i] for i in range(len(med)))
    assert med[-1] >= med[0]   # rising history → rising projection


def test_project_series_handles_single_point():
    med, p10, p90 = _project_series([2.0], cap=10.0)
    assert len(med) == len(FORECAST_STEPS)
    assert all(p90[i] >= p10[i] for i in range(len(med)))   # non-degenerate bands


def test_crossing_requires_multifactor_escalation():
    """
    A strong AIS+price escalation WITH news/sanctions crosses the action band;
    the same escalation with zero news/sanctions correctly stays capped (fusion
    weights for ais+price sum to 0.60 < 0.70 action threshold).
    """
    fc = _forecast(ais_med=4.5, price_med=0.6)
    conf_multi, _, _ = _compute_crossing_probability(fc, base_gdelt_contrib=0.15, base_sanctions_contrib=0.05)
    conf_alone, _, _ = _compute_crossing_probability(fc, 0.0, 0.0)
    assert conf_multi > 0.5
    assert conf_alone == 0.0


def test_crossing_calm_forecast_does_not_cross():
    fc = _forecast(ais_med=0.2, price_med=0.05)
    conf, crossing_h, _ = _compute_crossing_probability(fc, 0.1, 0.05)
    assert conf == 0.0
    assert crossing_h == float("inf")


def test_counterfactual_resolution_reduces_crossing():
    fc = _forecast(ais_med=4.5, price_med=0.6)
    base_conf, _, _ = _compute_crossing_probability(fc, 0.15, 0.05)
    for scenario in ("crisis_resolves_5d", "brent_below_65", "russia_export_surge"):
        pert = _perturb_forecast(fc, scenario)
        cf_conf, _, _ = _compute_crossing_probability(pert, 0.15, 0.05)
        assert cf_conf <= base_conf, f"{scenario} should not increase crossing probability"


def test_projected_severity_in_unit_range():
    assert 0.0 <= _projected_severity(_forecast(0.0, 0.0)) <= 1.0
    assert _projected_severity(_forecast(5.0, 1.0)) == 1.0   # saturated → full severity


def test_perturb_does_not_mutate_baseline():
    fc = _forecast(ais_med=4.0, price_med=0.5)
    before = list(fc.ais_gap_freq_median)
    _perturb_forecast(fc, "crisis_resolves_5d")
    assert fc.ais_gap_freq_median == before   # perturbation returns a copy
