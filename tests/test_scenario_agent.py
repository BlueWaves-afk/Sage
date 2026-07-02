"""
System 2 (scenario_agent) unit tests — no live FalkorDB/Bedrock required.

Covers the ARIO cascade, Monte-Carlo bands, the Leontief IO model, and the ABM
emergent simulation. These are the deterministic model cores; the KB-dependent
runner wiring is covered by integration tests.
"""
from __future__ import annotations

import pytest

from scenario_agent.ario import ARIOParams, run as run_ario, run_monte_carlo


def test_ario_no_disruption_is_zero_gap():
    """Zero disruption fraction → no feedstock gap."""
    r = run_ario(ARIOParams(disruption_fraction=0.0, disruption_days=30, horizon_days=45))
    assert r.gap_mbpd == 0.0
    assert len(r.feedstock_gap_timeline) == 45


def test_ario_full_closure_produces_gap_and_price():
    """A large disruption produces a non-negative gap and a positive price band."""
    r = run_ario(ARIOParams(disruption_fraction=1.0, disruption_days=30, horizon_days=45))
    assert r.gap_mbpd >= 0.0
    assert r.price_impact_high >= r.price_impact_low >= 0.0
    # A full closure should move the price band above zero.
    assert r.price_impact_high > 0.0


def test_ario_escalation_profiles_differ():
    """Escalating, constant, and resolving profiles yield distinct timelines.

    The bypass is compromised so a real feedstock gap forms — otherwise India's bypass
    capacity fully absorbs the disruption and every profile collapses to a zero gap
    (a documented, correct property of the cascade for partial disruptions).
    """
    base = dict(disruption_fraction=1.0, disruption_days=30, horizon_days=45,
                bypass_compromised_frac=0.9)
    esc = run_ario(ARIOParams(escalation_profile="escalating", **base))
    con = run_ario(ARIOParams(escalation_profile="constant", **base))
    res = run_ario(ARIOParams(escalation_profile="resolving", **base))
    # Distinct cumulative gaps across the three shapes.
    sums = {sum(esc.feedstock_gap_timeline), sum(con.feedstock_gap_timeline),
            sum(res.feedstock_gap_timeline)}
    assert len(sums) >= 2, "escalation profiles should not all collapse to the same timeline"


def test_ario_bypass_compromise_worsens_gap():
    """Blocking the bypass cannot reduce the feedstock gap."""
    base = dict(disruption_fraction=1.0, disruption_days=30, horizon_days=45)
    healthy = run_ario(ARIOParams(bypass_compromised_frac=0.0, **base))
    blocked = run_ario(ARIOParams(bypass_compromised_frac=1.0, **base))
    assert sum(blocked.feedstock_gap_timeline) >= sum(healthy.feedstock_gap_timeline)


def test_monte_carlo_bands_ordered():
    """p10 ≤ p50 ≤ p90 for every reported metric."""
    bands = run_monte_carlo(ARIOParams(disruption_fraction=0.7, disruption_days=25), n=100)
    for metric, band in bands.items():
        if isinstance(band, dict) and {"p10", "p50", "p90"} <= set(band):
            assert band["p10"] <= band["p50"] <= band["p90"], f"{metric} bands out of order"


def test_io_model_optional_load():
    """Leontief IO loads from the bundle and produces non-negative GDP/inflation impacts."""
    from scenario_agent.io_model import load_io
    io = load_io("data/india-energy-2026.context")
    if io is None:
        pytest.skip("IO bundle not available in this environment")
    res = io.run(0.3, 0.2)
    assert res.gdp_loss_pct >= 0.0
    assert res.inflation_pct >= 0.0


def test_abm_simulation_runs():
    """ABM produces a system gap timeline of the requested horizon."""
    from scenario_agent.abm import simulate
    refineries = [
        {"name": "Jamnagar Refinery", "capacity_mbpd": 1.4, "exposure": 0.6, "inventory_days": 22},
        {"name": "Paradip", "capacity_mbpd": 0.3, "exposure": 0.2, "inventory_days": 20},
    ]
    res = simulate(refineries, disruption_fraction=1.0, disruption_days=30, horizon_days=45)
    assert len(res.system_gap_timeline) == 45
    assert all(g >= 0.0 for g in res.system_gap_timeline)
    assert res.peak_system_gap >= 0.0
