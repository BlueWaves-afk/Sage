"""
Knowledge base smoke tests.

These tests verify the contracts, schema models, and business logic that
don't require a live FalkorDB or Bedrock connection.

Tests that DO require live services are marked @pytest.mark.integration
and skipped by default. Run them with:
  pytest -m integration tests/test_kb_smoke.py

Day-4 smoke test checklist (per schema spec §11):
  [x] C0: connection module imports cleanly
  [x] C1: NormalizedSignal validates all source types
  [x] C2: all 11 entity types importable and validate correctly
  [x] C3: all 9 edge types + EDGE_TYPE_MAP importable
  [x] C4: score_to_band() returns correct bands for boundary values
  [x] C5: output models validate
  [x] C6: PendingScenario lifecycle field valid
  [x] C7: all read/write function signatures importable
  [x] Fusion: weighted-sum fallback runs without Bedrock
  [x] Triage: force_synthesis always returns synthesize
  [x] Synthesis: wiki page write/read roundtrip
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone

import pytest

# ---------------------------------------------------------------------------
# C0 — connection
# ---------------------------------------------------------------------------

def test_connection_imports():
    from knowledge.connection import build_graphiti, bootstrap, SCHEMA_VERSION, GRAPH_NAME
    assert SCHEMA_VERSION == "1.0.0"
    assert GRAPH_NAME == "sage"


# ---------------------------------------------------------------------------
# C1 — NormalizedSignal
# ---------------------------------------------------------------------------

def test_ais_signal():
    from contracts.signal import NormalizedSignal
    now = datetime.now(timezone.utc)
    sig = NormalizedSignal(
        signal_id="test-001",
        source="ais",
        observed_at=now,
        ingested_at=now,
        summary="MT Destiny went AIS-dark near Larak Island",
        priority_hint="HIGH",
        force_synthesis=True,
        entity_refs=["Strait of Hormuz", "MT Destiny"],
        h3_cells=["8526800bfffffff"],
        payload={"mmsi": "123456789", "dark_vessel": True, "anomaly_score": 0.9},
    )
    assert sig.source == "ais"
    assert sig.force_synthesis is True
    assert "Strait of Hormuz" in sig.entity_refs


def test_sanctions_signal():
    from contracts.signal import NormalizedSignal
    now = datetime.now(timezone.utc)
    sig = NormalizedSignal(
        signal_id="test-002",
        source="sanctions",
        observed_at=now,
        ingested_at=now,
        summary="OFAC added NIOC to SDN list",
        force_synthesis=True,
        entity_refs=["NIOC"],
        payload={"list": "OFAC", "change": "add", "subject": "NIOC", "subject_type": "entity"},
    )
    assert sig.source == "sanctions"
    assert sig.force_synthesis is True


def test_price_signal():
    from contracts.signal import NormalizedSignal
    now = datetime.now(timezone.utc)
    sig = NormalizedSignal(
        signal_id="test-003",
        source="price",
        observed_at=now,
        ingested_at=now,
        summary="Brent crude +8.3% on Hormuz closure news",
        entity_refs=["Strait of Hormuz"],
        payload={"instrument": "BZ=F", "price": 102.5, "changepoint": True, "regime": "stressed"},
    )
    assert sig.source == "price"


# ---------------------------------------------------------------------------
# C2 — Entity ontology
# ---------------------------------------------------------------------------

def test_all_entity_types_import():
    from knowledge.schema.entities import (
        Corridor, Supplier, Refinery, CrudeGrade, Port,
        SPRCavern, Vessel, GeoEvent, Authority,
        PendingScenario, ScenarioOutput, ENTITY_TYPES,
    )
    assert len(ENTITY_TYPES) == 11
    for name, cls in ENTITY_TYPES.items():
        assert isinstance(name, str)
        # Must be the class itself, not an instance (Graphiti footgun #780)
        assert isinstance(cls, type), f"{name} must be a class, not an instance"


def test_corridor_entity():
    from knowledge.schema.entities import Corridor
    c = Corridor(
        throughput_mbpd=18.5,
        choke_severity=0.95,
        location_lat=26.5,
        location_lon=56.3,
        h3_cells=["8526800bfffffff"],
    )
    assert c.choke_severity == 0.95
    assert "8526800bfffffff" in c.h3_cells


def test_pending_scenario_defaults():
    from knowledge.schema.entities import PendingScenario
    p = PendingScenario()
    assert p.status == "speculative"
    assert p.confidence is None


# ---------------------------------------------------------------------------
# C3 — Edge ontology
# ---------------------------------------------------------------------------

def test_all_edge_types_import():
    from knowledge.schema.edges import EDGE_TYPES, EDGE_TYPE_MAP
    assert len(EDGE_TYPES) == 9
    # Wildcard key must exist
    assert ("Entity", "Entity") in EDGE_TYPE_MAP
    assert "RISK_STATE" in EDGE_TYPE_MAP[("Entity", "Entity")]


def test_risk_state_required_fields():
    from knowledge.schema.edges import RiskState
    rs = RiskState(score=0.75, band="action")
    assert rs.score == 0.75
    assert rs.band == "action"
    assert rs.factor_ais == 0.0   # default


def test_edge_type_classes_not_instances():
    from knowledge.schema.edges import EDGE_TYPES
    for name, cls in EDGE_TYPES.items():
        assert isinstance(cls, type), f"{name} must be a class"


# ---------------------------------------------------------------------------
# C4 — Band thresholds
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("score,expected_band", [
    (0.00, "calm"),
    (0.24, "calm"),
    (0.25, "watch"),
    (0.44, "watch"),
    (0.45, "elevated"),
    (0.69, "elevated"),
    (0.70, "action"),
    (0.89, "action"),
    (0.90, "critical"),
    (1.00, "critical"),
])
def test_score_to_band(score: float, expected_band: str):
    from contracts.bands import score_to_band
    assert score_to_band(score) == expected_band


# ---------------------------------------------------------------------------
# C5 — Output models
# ---------------------------------------------------------------------------

def test_scenario_output_data():
    from contracts.outputs import ScenarioOutputData
    data = ScenarioOutputData(
        scenario_id="sc-001",
        trigger_entity="Strait of Hormuz",
        status="confirmed",
        confidence=0.85,
        gap_mbpd=1.2,
        gap_duration_days=14.0,
        feedstock_gap_timeline=[1.1, 1.2, 1.3, 1.2, 1.1, 1.0, 0.9],
        price_impact_low=8.0,
        price_impact_high=22.0,
        spr_depletion_days=6.5,
        assumptions={
            "import_dependence_pct": {"value": 88.2, "unit": "%", "source": "PPAC 2025"},
        },
    )
    assert data.confidence == 0.85
    assert "import_dependence_pct" in data.assumptions


def test_score_breakdown():
    from contracts.outputs import ScoreBreakdown
    bd = ScoreBreakdown(
        cost_score=0.85,
        lead_time_score=0.70,
        grade_compatibility_score=0.92,
        corridor_risk_score=0.65,
    )
    assert bd.cost_score == 0.85
    assert "cost" in bd.weights_used


# ---------------------------------------------------------------------------
# C6 — PendingScenario lifecycle
# ---------------------------------------------------------------------------

def test_pending_scenario_lifecycle():
    from knowledge.schema.entities import PendingScenario
    p = PendingScenario(
        confidence=0.73,
        projected_crossing_hours=18.0,
        status="speculative",
        scenario_ref="sandbox-abc12345",
    )
    assert p.status == "speculative"
    # Promote
    p.status = "promoted"
    assert p.status == "promoted"


# ---------------------------------------------------------------------------
# Fusion — weighted-sum fallback (no Bedrock needed)
# ---------------------------------------------------------------------------

def test_fusion_weighted_sum_fallback():
    from sensory_agent.fusion import FeatureVector, FusionModel
    fv = FeatureVector(
        ais_dark_vessel_count=3.0,
        ais_gap_count_24h=5.0,
        gdelt_tone_24h_mean=-7.5,
        price_bocd_flag=1.0,
        sanctions_major_entity=1.0,
    )
    model = FusionModel()   # load() not called → falls back to weighted sum
    result = model.predict(fv)
    assert 0.0 <= result.score <= 1.0
    assert result.factor_ais > 0.0
    assert result.model_version == "weighted-sum-fallback"


def test_fusion_score_zero_on_calm():
    from sensory_agent.fusion import FeatureVector, FusionModel
    fv = FeatureVector()   # all zeros → calm
    model = FusionModel()
    result = model.predict(fv)
    assert result.score == 0.0


# ---------------------------------------------------------------------------
# Triage — force_synthesis bypass
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_triage_force_synthesis():
    from contracts.signal import NormalizedSignal
    from knowledge.triage import triage
    now = datetime.now(timezone.utc)
    sig = NormalizedSignal(
        signal_id="t-001",
        source="sanctions",
        observed_at=now,
        ingested_at=now,
        summary="Sanctions added",
        force_synthesis=True,
        entity_refs=["NIOC"],
        payload={},
    )
    decision, sim = await triage(sig)
    assert decision == "synthesize"
    assert sim == 1.0


@pytest.mark.asyncio
async def test_triage_no_entity_refs_stores():
    from contracts.signal import NormalizedSignal
    from knowledge.triage import triage
    now = datetime.now(timezone.utc)
    sig = NormalizedSignal(
        signal_id="t-002",
        source="news",
        observed_at=now,
        ingested_at=now,
        summary="Some background news",
        entity_refs=[],
        payload={},
    )
    decision, sim = await triage(sig)
    assert decision == "store"
    assert sim == 0.0


# ---------------------------------------------------------------------------
# Synthesis — wiki roundtrip (no Bedrock needed)
# ---------------------------------------------------------------------------

def test_wiki_roundtrip():
    from knowledge.synthesis import load_wiki_page, write_wiki_page
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["WIKI_DIR"] = tmpdir
        # Clear module-level WIKI_DIR cache
        import knowledge.synthesis as syn_mod
        from pathlib import Path
        syn_mod.WIKI_DIR = Path(tmpdir)

        entity  = "Test Corridor"
        content = "# Test Corridor\n\nRisk is elevated due to AIS gaps."
        write_wiki_page(entity, content)
        loaded = load_wiki_page(entity)
        assert content == loaded


def test_wiki_returns_stub_for_new_entity():
    from knowledge.synthesis import load_wiki_page
    page = load_wiki_page("NonExistent Entity XYZ 12345")
    assert "NonExistent Entity XYZ 12345" in page


# ---------------------------------------------------------------------------
# C7 — API signatures importable
# ---------------------------------------------------------------------------

def test_write_api_signatures():
    from knowledge.api.write import (
        ingest_signal, write_scenario, write_procurement,
        write_spr_schedule, write_pending, promote_pending,
        write_risk_state, IngestResult, EpisodeRef,
    )
    import inspect
    assert inspect.iscoroutinefunction(ingest_signal)
    assert inspect.iscoroutinefunction(write_risk_state)
    assert inspect.iscoroutinefunction(promote_pending)


def test_read_api_signatures():
    from knowledge.api.read import (
        get_risk_scores, get_subgraph, get_available_suppliers,
        get_grade_specs, get_routes, get_spr_state,
        copilot_query, get_wiki_page,
        RiskScoreView, SubgraphView, SupplierView,
        GradeSpecView, CorridorView, SPRCavernView,
        WikiPage, CopilotAnswer,
    )
    import inspect
    assert inspect.iscoroutinefunction(get_risk_scores)
    assert inspect.iscoroutinefunction(copilot_query)
