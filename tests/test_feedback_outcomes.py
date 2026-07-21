from __future__ import annotations

import json

from knowledge import feedback


def test_scenario_accuracy_and_realized_savings(tmp_path, monkeypatch) -> None:
    outcome_log = tmp_path / "scenario_outcomes.jsonl"
    monkeypatch.setattr(feedback, "SCENARIO_OUTCOMES_LOG", outcome_log)

    feedback.record_scenario_prediction(
        scenario_id="scenario-1",
        entity="Strait of Hormuz",
        params={"closure_fraction": 0.5},
        predicted={
            "gap_mbpd": 1.0,
            "price_impact_high": 20.0,
            "spr_depletion_days": 10.0,
            "gdp_proxy_impact_pct": -1.0,
        },
    )

    updated = feedback.record_scenario_realized(
        scenario_id="scenario-1",
        realized={
            "gap_mbpd": 0.8,
            "price_impact_high": 24.0,
            "spr_depletion_days": 8.0,
            "gdp_proxy_impact_pct": -0.5,
        },
        source="operator",
        evidence={
            "observed_from": "2026-01-01",
            "observed_to": "2026-01-15",
            "evidence_url": "https://example.com/outcome",
        },
        costs={
            "baseline_procurement_cost_usd": 10_000_000,
            "actual_procurement_cost_usd": 8_500_000,
            "baseline_basis": "approved procurement budget",
            "evidence_url": "https://example.com/award",
        },
    )

    assert updated is not None
    assert updated["costs"]["realized_savings_usd"] == 1_500_000

    summary = feedback.get_scenario_accuracy()
    assert summary is not None
    assert summary["realized"] == 1
    assert summary["coverage"] == 1.0
    assert summary["mape"]["gap_mbpd"]["mae"] == 0.2
    assert summary["mape"]["price_impact_high"]["bias"] == 4.0
    assert summary["savings"]["realized_savings_usd"] == 1_500_000
    assert summary["savings"]["verified_scenarios"] == 1


def test_realized_outcome_can_be_corrected_without_duplicate(tmp_path, monkeypatch) -> None:
    outcome_log = tmp_path / "scenario_outcomes.jsonl"
    monkeypatch.setattr(feedback, "SCENARIO_OUTCOMES_LOG", outcome_log)
    feedback.record_scenario_prediction(
        scenario_id="scenario-2",
        entity="Bab-el-Mandeb",
        params={},
        predicted={"gap_mbpd": 1.0},
    )

    for actual in (0.9, 0.7):
        feedback.record_scenario_realized(
            scenario_id="scenario-2",
            realized={"gap_mbpd": actual},
            source="analyst",
            evidence={"evidence_url": "https://example.com/revision"},
        )

    records = [json.loads(line) for line in outcome_log.read_text().splitlines()]
    assert len(records) == 1
    assert records[0]["realized"]["gap_mbpd"] == 0.7
    assert records[0]["error"]["gap_mbpd"] == -0.3


def test_costs_are_not_realized_when_pair_is_incomplete(tmp_path, monkeypatch) -> None:
    outcome_log = tmp_path / "scenario_outcomes.jsonl"
    monkeypatch.setattr(feedback, "SCENARIO_OUTCOMES_LOG", outcome_log)
    feedback.record_scenario_prediction(
        scenario_id="scenario-3",
        entity="Suez Canal",
        params={},
        predicted={"gap_mbpd": 0.5},
    )

    updated = feedback.record_scenario_realized(
        scenario_id="scenario-3",
        realized={"gap_mbpd": 0.4},
        source="analyst",
        costs={"baseline_procurement_cost_usd": 2_000_000},
    )

    assert updated is not None
    assert updated["costs"] is None
    assert feedback.get_realized_savings_summary()["verified_scenarios"] == 0
