"""
System 3 (alt_procurement_agent) unit tests — no live services required.

Covers grade compatibility (Gaussian model), maritime routing (bypass selection
under corridor closure), and TOPSIS ranking.
"""
from __future__ import annotations

from types import SimpleNamespace

from alt_procurement_agent.grade import compatibility_score, best_compatibility
from alt_procurement_agent.routing import solve as solve_routes
from alt_procurement_agent.rank import rank as topsis_rank
from contracts.outputs import ProcurementOption


def _spec(api, sulfur, compat=None):
    return SimpleNamespace(api_gravity=api, sulfur_pct=sulfur, compatibility=compat)


def test_compatibility_perfect_match_is_high():
    """A crude matching the refinery spec exactly scores near 1.0."""
    score = compatibility_score(32.8, 1.96, _spec(32.8, 1.96))
    assert 0.9 <= score <= 1.0


def test_compatibility_mismatch_is_low_but_floored():
    """A badly mismatched crude scores low but above the blending floor."""
    score = compatibility_score(16.0, 3.5, _spec(40.0, 0.2))
    assert 0.0 <= score < 0.5
    assert score > 0.0   # floors keep blending feasible


def test_compatibility_in_unit_range():
    for api in (16, 28, 34, 45):
        for sulfur in (0.1, 1.0, 2.5, 3.5):
            s = compatibility_score(api, sulfur, _spec(32.0, 1.8))
            assert 0.0 <= s <= 1.0


def test_precomputed_compatibility_passthrough():
    """When the bundle edge carries a precomputed compatibility, it is used directly."""
    assert compatibility_score(10.0, 5.0, _spec(32.0, 1.8, compat=0.77)) == 0.77


def test_best_compatibility_takes_max():
    specs = [_spec(40.0, 0.2), _spec(32.8, 1.96)]
    best = best_compatibility(32.8, 1.96, specs)
    assert best == max(compatibility_score(32.8, 1.96, s) for s in specs)


def test_routing_prefers_bypass_when_corridor_closed():
    """When Hormuz risk exceeds the ceiling, an available bypass route is selected."""
    suppliers = [SimpleNamespace(display_name="Saudi Aramco", country="Saudi Arabia")]
    corridors = [
        SimpleNamespace(display_name="Strait of Hormuz", risk_score=0.9),
        SimpleNamespace(display_name="Suez Canal", risk_score=0.1),
    ]
    bypass = [{"src": "Saudi Aramco", "via_corridor": "Suez Canal",
               "cost_premium": 2.5, "added_days": 10.0}]
    routes = solve_routes(suppliers, corridors, bypass, risk_max=0.5)
    assert "Saudi Aramco" in routes
    r = routes["Saudi Aramco"]
    # Hormuz is closed (0.9 > 0.5) so the open bypass must be chosen.
    assert r.is_bypass is True
    assert r.corridor == "Suez Canal"


def test_topsis_single_option_scores_one():
    opt = ProcurementOption(
        supplier="ADNOC", grade="Murban", route_via="Fujairah",
        landed_cost_usd_bbl=2.0, lead_time_days=22, grade_compatibility=0.9,
        corridor_risk=0.1, topsis_score=0.0, rationale="",
    )
    ranked = topsis_rank([opt])
    assert len(ranked) == 1
    assert ranked[0].topsis_score == 1.0


def test_topsis_orders_dominant_option_first():
    """A strictly better option (cheaper, faster, more compatible, safer) ranks #1."""
    good = ProcurementOption(
        supplier="ADNOC", grade="Murban", route_via="Fujairah",
        landed_cost_usd_bbl=1.5, lead_time_days=20, grade_compatibility=0.95,
        corridor_risk=0.1, topsis_score=0.0, rationale="",
    )
    bad = ProcurementOption(
        supplier="PDVSA", grade="Merey", route_via="Cape of Good Hope",
        landed_cost_usd_bbl=5.5, lead_time_days=38, grade_compatibility=0.4,
        corridor_risk=0.5, topsis_score=0.0, rationale="",
    )
    ranked = topsis_rank([bad, good])
    assert ranked[0].supplier == "ADNOC"
    assert ranked[0].topsis_score >= ranked[1].topsis_score
    assert ranked[0].score_breakdown is not None   # XAI breakdown populated
