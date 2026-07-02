"""
Bundle parameterisation + upgrade tests.

Verifies (1) the bundle loads and validates all param tables, (2) every agent
reads its constants from the bundle rather than hardcoding them, and (3) the
upgrade diff logic detects structural changes.
"""
from __future__ import annotations

import os

import pytest

from knowledge.context.loader import load_bundle

BUNDLE = "data/india-energy-2026.context"


@pytest.fixture(scope="module")
def bundle():
    if not os.path.isdir(BUNDLE):
        pytest.skip("context bundle not available")
    return load_bundle(BUNDLE)


def test_bundle_validates_all_param_tables(bundle):
    assert bundle.routing_params, "routing_params empty"
    assert bundle.ranking_params, "ranking_params empty"
    assert bundle.spr_params, "spr_params empty"
    assert bundle.grade_params, "grade_params empty"
    assert bundle.heuristic_params, "heuristic_params empty"
    assert bundle.economics_params, "economics_params empty"


def test_bundle_version_present(bundle):
    assert bundle.manifest.get("bundle_version"), "bundle_version missing from manifest"


def test_volatile_registry_is_complete(bundle):
    """The refresh contract enumerates the known sub-annual values with valid cadences."""
    assert bundle.volatile_registry, "volatile_defaults.csv not loaded"
    params = {r["param"] for r in bundle.volatile_registry}
    # The fastest-drifting values must be flagged.
    for must in ("baseline_brent_usd_per_bbl", "hormuz_share_pct", "vlcc_cost_usd_bbl", "current_fill_mmt"):
        assert must in params, f"{must} missing from volatile registry"
    valid_freq = {"live", "weekly", "monthly", "quarterly", "annual"}
    for r in bundle.volatile_registry:
        assert r["update_freq"] in valid_freq, f"bad update_freq: {r}"
        assert r["lives_in"], "registry row must name the file the value lives in"


def _with_bundle_env():
    os.environ["SAGE_BUNDLE_PATH"] = BUNDLE


def test_routing_reads_bundle():
    if not os.path.isdir(BUNDLE):
        pytest.skip("no bundle")
    _with_bundle_env()
    from alt_procurement_agent.routing import _load_routing_bundle
    cost, days, war = _load_routing_bundle()
    assert cost["Saudi Arabia"] > 0
    assert days["Russia"] > 0
    assert war > 0


def test_ranking_reads_bundle():
    if not os.path.isdir(BUNDLE):
        pytest.skip("no bundle")
    _with_bundle_env()
    from alt_procurement_agent.rank import _load_weights
    w = _load_weights()
    assert abs(sum(w.values()) - 1.0) < 1e-6, "TOPSIS weights should sum to 1.0"


def test_grade_reads_bundle():
    if not os.path.isdir(BUNDLE):
        pytest.skip("no bundle")
    _with_bundle_env()
    from alt_procurement_agent.grade import _load_grade_params
    p = _load_grade_params()
    assert p["grade_api_sigma"] > 0
    assert abs(p["grade_api_weight"] + p["grade_sulfur_weight"] - 1.0) < 1e-6


def test_spr_and_economics_read_bundle():
    if not os.path.isdir(BUNDLE):
        pytest.skip("no bundle")
    _with_bundle_env()
    from reserve_optim_agent.sdp import _load_sdp_bundle
    from reserve_optim_agent.runner import _load_spr_bundle_params
    sdp = _load_sdp_bundle()
    assert sdp["buffer_threshold_days"] > 0
    assert 0 < sdp["sdp_discount_rate"] <= 1.0
    resolve, refill = _load_spr_bundle_params()
    assert resolve["resolving"] >= resolve["constant"] >= resolve["escalating"]
    assert 0 < refill < 1.0


def test_heuristic_reads_bundle():
    if not os.path.isdir(BUNDLE):
        pytest.skip("no bundle")
    _with_bundle_env()
    from orchestration.scenario_params import _load_heuristic_params
    p = _load_heuristic_params()
    assert p["heuristic_max_disruption_days"] >= p["heuristic_disruption_days_if_sanctions"]


def test_upgrade_diff_detects_change(bundle):
    """_diff_nodes flags an entity whose structural facts changed."""
    from knowledge.context.upgrade import _diff_nodes
    import copy

    other = copy.deepcopy(bundle)
    # Mutate one numeric attribute on the first node of the first node-type present.
    changed_id = None
    for ntype, rows in other.node_rows.items():
        if rows:
            row = rows[0]
            changed_id = row.get("entity_id") or row.get("canonical_name")
            for k, v in row.items():
                if k not in ("tier", "source", "as_of", "notes", "entity_id", "canonical_name"):
                    try:
                        row[k] = str(float(v) + 1.0)
                        break
                    except (ValueError, TypeError):
                        continue
            break

    changed = _diff_nodes(bundle, other)
    if changed_id is not None:
        assert changed_id in changed
