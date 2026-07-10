"""
Seed the SAGE knowledge base with realistic India oil supply-chain data.

Populates all 3 stores:
  1. /wiki markdown store      — narrative intelligence pages per entity
  2. Episodic subgraph         — episodes written via add_episode() with entity types
  3. Semantic entity subgraph  — RISK_STATE, scenario, procurement, SPR edges
     (written via write_* functions, which call add_episode() internally)

Run inside a container that has FalkorDB access:
  docker exec -it sage-api-gateway-1 python scripts/seed_kb.py

Or from your host (requires FALKORDB_HOST=localhost in env):
  FALKORDB_HOST=localhost LLM_PROVIDER=stub python scripts/seed_kb.py
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env / .env.local so LLM_PROVIDER=bedrock + AWS creds are set (else the
# stub LLM runs and no entities are extracted from episodes).
try:
    from config_env import load_local_env
    load_local_env()
except Exception:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger("seed_kb")

# ─── 1. Wiki pages ────────────────────────────────────────────────────────────

# Foundational wiki pages are NOT defined here anymore. They live in the context
# bundle's narratives/ layer (data/<bundle>.context/narratives/*.md) and are written
# to the wiki store through the synthesis path during bundle.instantiate().

# ─── 2. Episodic signals (written via add_episode with entity types) ──────────

EPISODES: list[dict] = [
    {
        "name": "ais-signal-2026-06-28-001",
        "body": (
            "AIS monitoring alert: MT Pacific Star (MMSI 477123456) went AIS-dark at "
            "25.3°N 56.8°E in the Strait of Hormuz at 14:22 UTC on 2026-06-28. "
            "Gap duration: 4.2 hours before signal resumed near Qeshm Island. "
            "Vessel type: VLCC (300,000 DWT). Last known cargo: Arab Light crude from Ras Tanura. "
            "Destination declared: Vadinar Port. "
            "IRGCN patrol vessel P-224 observed in vicinity 2h prior. "
            "Saudi Aramco vessel fleet AIS compliance rate dropped to 78% in the strait this week."
        ),
        "source_desc": "AIS stream monitor — Strait of Hormuz",
    },
    {
        "name": "gdelt-signal-2026-06-28-002",
        "body": (
            "GDELT event extraction: Iranian state media (IRNA) published statement from IRGC Navy "
            "Commander Rear Admiral Tangsiri warning of 'consequences' if US carrier strike group "
            "USS Abraham Lincoln enters the Persian Gulf. Statement coincides with annual IRGC naval "
            "exercise 'Great Prophet 18' scheduled 2026-07-01. "
            "Saudi Aramco confirmed continued operations at Ras Tanura; no disruption reported. "
            "Brent crude front-month contract rose $3.40/bbl (4.1%) on the news. "
            "Goldtone sentiment: -0.61 (hostile). "
            "India MoPNG monitoring situation; no emergency protocol activated."
        ),
        "source_desc": "GDELT news extraction — Persian Gulf",
    },
    {
        "name": "price-signal-2026-06-28-003",
        "body": (
            "Brent crude BOCD (Bayesian Online Change Point Detection) alert: "
            "Structural breakpoint detected in Brent spot price series at 2026-06-28 09:30 UTC. "
            "Pre-breakpoint mean: $74.20/bbl (30-day). "
            "Post-breakpoint level: $78.80/bbl. "
            "Breakpoint confidence: 0.94. "
            "WTI spread: Brent-WTI = $6.40 (widening, consistent with supply-risk premium). "
            "EIA crude inventory draw last week: -4.2 MB (larger than -2.1 MB expected). "
            "OPEC+ next meeting: 2026-07-15."
        ),
        "source_desc": "EIA / yfinance price monitor",
    },
    {
        "name": "sanctions-signal-2026-06-28-004",
        "body": (
            "OFAC SDN list delta: No new additions affecting Indian oil supply this week. "
            "NIOC remains on SDN list — no waivers active. "
            "Sovcomflot (Russia) fleet: 3 additional VLCCs added to SDN list on 2026-06-25. "
            "Nayara Energy (Vadinar) confirmed no exposure to sanctioned vessels. "
            "EU Council Regulation 833/2014 amendment under review — potential tightening of "
            "Russian crude price cap enforcement. "
            "Indian refiners: compliance posture unchanged; using non-sanctioned vessels for "
            "all Gulf crude liftings."
        ),
        "source_desc": "OFAC SDN delta monitor",
    },
]

# ─── 2b. Structural reference data — loaded from a context bundle ──────────────
#
# The foundational static knowledge (corridors, suppliers, refineries, crude grades,
# ports, SPR, and their structural edges) now lives in a versioned, provenance-tracked
# CONTEXT BUNDLE at data/india-energy-2026.context — NOT hardcoded here.
#
# This is SAGE's "load pretrained knowledge" step: knowledge.context.load_bundle()
# parses the bundle, validates that every row is sourced (real | derived | estimated),
# and renders structural episodes that the standard add_episode() path extracts.
#
# Swap CONTEXT_BUNDLE for a newer/region-specific bundle to re-base the worldview.
# See data/CONTEXT_BUNDLE_SCHEMA.md for the format.

CONTEXT_BUNDLE = os.environ.get("SAGE_CONTEXT_BUNDLE", "data/india-energy-2026.context")


# ─── 3. Risk state writes ─────────────────────────────────────────────────────

RISK_STATES: list[dict] = [
    {
        "entity": "Strait of Hormuz",
        "score": 0.68,
        "factor_ais": 0.82,
        "factor_gdelt": 0.71,
        "factor_price": 0.55,
        "factor_sanctions": 0.05,
        "rationale": (
            "VLCC AIS dark event (4.2h gap, IRGC patrol in vicinity) + IRGC naval exercise "
            "announcement + Brent BOCD breakpoint. Composite GBM score: 0.68."
        ),
        "model_version": "weighted-sum-fallback-v1",
    },
    {
        "entity": "Saudi Aramco",
        "score": 0.18,
        "factor_ais": 0.12,
        "factor_gdelt": 0.15,
        "factor_price": 0.22,
        "factor_sanctions": 0.00,
        "rationale": "No direct threats to Aramco operations. Minor contagion from Hormuz risk.",
        "model_version": "weighted-sum-fallback-v1",
    },
    {
        "entity": "Vadinar Port",
        "score": 0.42,
        "factor_ais": 0.55,
        "factor_gdelt": 0.35,
        "factor_price": 0.30,
        "factor_sanctions": 0.00,
        "rationale": (
            "Indirect exposure: Vadinar dependent on Hormuz-transiting VLCCs. "
            "No vessel-specific incidents at Vadinar."
        ),
        "model_version": "weighted-sum-fallback-v1",
    },
    {
        "entity": "NIOC",
        "score": 0.92,
        "factor_ais": 0.10,
        "factor_gdelt": 0.88,
        "factor_price": 0.40,
        "factor_sanctions": 1.00,
        "rationale": "OFAC SDN-listed. Iranian geopolitical escalation indicators elevated.",
        "model_version": "weighted-sum-fallback-v1",
    },
]

# ─── 4. Scenario output ───────────────────────────────────────────────────────

from contracts.outputs import (
    ScenarioOutputData, ProcurementRecData, ProcurementOption, ScoreBreakdown,
    SPRScheduleData, SPRDay,
)

SCENARIO = ScenarioOutputData(
    scenario_id="sc-20260628-001",
    trigger_entity="Strait of Hormuz",
    status="confirmed",
    confidence=0.73,
    gap_mbpd=1.8,
    gap_duration_days=14.0,
    feedstock_gap_timeline=[1.6, 1.8, 1.9, 1.8, 1.7, 1.5, 1.2, 1.0, 0.8, 0.6, 0.4, 0.3, 0.2, 0.1],
    price_impact_low=9.0,
    price_impact_high=24.0,
    spr_depletion_days=7.2,
    assumptions={
        "import_dependence_pct": {"value": 88.2, "unit": "%", "source": "PPAC 2025"},
        "hormuz_share_of_gulf": {"value": 95.0, "unit": "%", "source": "EIA 2024"},
        "bypass_ramp_days":     {"value": 5.0,  "unit": "days", "source": "Aramco ops est."},
    },
)

PROCUREMENT = ProcurementRecData(
    scenario_id="sc-20260628-001",
    status="confirmed",
    ranked=[
        ProcurementOption(
            supplier="Saudi Aramco (Yanbu)",
            grade="Arab Light",
            route_via="Yanbu → Suez → Arabian Sea → Vadinar",
            landed_cost_usd_bbl=82.40,
            lead_time_days=14.0,
            grade_compatibility=0.94,
            corridor_risk=0.08,
            topsis_score=0.88,
            score_breakdown=ScoreBreakdown(
                cost_score=0.74,
                lead_time_score=0.62,
                grade_compatibility_score=0.94,
                corridor_risk_score=0.92,
            ),
            rationale=(
                "Petroline bypass fully avoids Hormuz. Arab Light compatible with Jamnagar and "
                "Vadinar refineries. Lead time 14d (Suez routing) vs 8d Hormuz — acceptable. "
                "Saudi Aramco confirmed 2 mbpd Petroline availability on 2026-06-27."
            ),
            episode_citations=[],
        ),
        ProcurementOption(
            supplier="ADNOC (Fujairah)",
            grade="Murban",
            route_via="Abu Dhabi Crude Pipeline → Fujairah → Arabian Sea → Vadinar",
            landed_cost_usd_bbl=83.10,
            lead_time_days=10.0,
            grade_compatibility=0.88,
            corridor_risk=0.10,
            topsis_score=0.82,
            score_breakdown=ScoreBreakdown(
                cost_score=0.71,
                lead_time_score=0.74,
                grade_compatibility_score=0.88,
                corridor_risk_score=0.90,
            ),
            rationale=(
                "ADCO pipeline bypasses Hormuz to Fujairah. Murban is a sweet light crude "
                "(40° API, 0.59% S) — slightly above Jamnagar's preferred API range but "
                "processable. ADNOC confirmed 0.6 mbpd additional lift available."
            ),
            episode_citations=[],
        ),
        ProcurementOption(
            supplier="Iraq SOMO (Ceyhan)",
            grade="Basra Heavy",
            route_via="Turkey ITP pipeline → Ceyhan → Suez → Vadinar",
            landed_cost_usd_bbl=79.80,
            lead_time_days=18.0,
            grade_compatibility=0.85,
            corridor_risk=0.22,
            topsis_score=0.61,
            score_breakdown=ScoreBreakdown(
                cost_score=0.83,
                lead_time_score=0.48,
                grade_compatibility_score=0.85,
                corridor_risk_score=0.78,
            ),
            rationale=(
                "ITP pipeline currently at reduced throughput (0.4 mbpd vs 1.6 mbpd capacity) "
                "due to Turkey-Iraq transit fee dispute. Cheapest option but longest lead time "
                "and supply uncertainty. Ranked 3rd."
            ),
            episode_citations=[],
        ),
    ],
)

SPR_SCHEDULE = SPRScheduleData(
    scenario_id="sc-20260628-001",
    status="confirmed",
    daily_plan=[
        SPRDay(day=1,  action="hold",  volume_mmt=0.00, reserve_after_mmt=5.33, days_cover_after=11.9, decision_driver="await confirmation of gap scope"),
        SPRDay(day=2,  action="hold",  volume_mmt=0.00, reserve_after_mmt=5.33, days_cover_after=11.9, decision_driver="bypass cargo ETA T+14d — hold"),
        SPRDay(day=3,  action="draw",  volume_mmt=0.12, reserve_after_mmt=5.21, days_cover_after=11.6, decision_driver="gap confirmed > 72h — initiate draw"),
        SPRDay(day=4,  action="draw",  volume_mmt=0.15, reserve_after_mmt=5.06, days_cover_after=11.3, decision_driver="ramp draw rate"),
        SPRDay(day=5,  action="draw",  volume_mmt=0.18, reserve_after_mmt=4.88, days_cover_after=10.9, decision_driver="max operational draw rate"),
        SPRDay(day=6,  action="draw",  volume_mmt=0.18, reserve_after_mmt=4.70, days_cover_after=10.5, decision_driver="sustain"),
        SPRDay(day=7,  action="draw",  volume_mmt=0.18, reserve_after_mmt=4.52, days_cover_after=10.1, decision_driver="sustain"),
        SPRDay(day=8,  action="draw",  volume_mmt=0.18, reserve_after_mmt=4.34, days_cover_after=9.7,  decision_driver="sustain"),
        SPRDay(day=9,  action="draw",  volume_mmt=0.18, reserve_after_mmt=4.16, days_cover_after=9.3,  decision_driver="sustain"),
        SPRDay(day=10, action="draw",  volume_mmt=0.18, reserve_after_mmt=3.98, days_cover_after=8.9,  decision_driver="sustain"),
        SPRDay(day=11, action="draw",  volume_mmt=0.15, reserve_after_mmt=3.83, days_cover_after=8.5,  decision_driver="taper — bypass cargo arrives T+14"),
        SPRDay(day=12, action="draw",  volume_mmt=0.12, reserve_after_mmt=3.71, days_cover_after=8.3,  decision_driver="taper"),
        SPRDay(day=13, action="draw",  volume_mmt=0.08, reserve_after_mmt=3.63, days_cover_after=8.1,  decision_driver="taper"),
        SPRDay(day=14, action="hold",  volume_mmt=0.00, reserve_after_mmt=3.63, days_cover_after=8.1,  decision_driver="bypass cargo received — end draw"),
    ],
    prob_above_buffer=0.91,
    constraint_satisfied=True,
    lagrange_multiplier=0.038,
    option_value_of_waiting=1.42,
    policy_memo=(
        "Hold for 48h to confirm gap scope. Initiate draw on day 3 if gap sustained. "
        "Max rate 0.18 MT/day maintains 8.1 days cover at draw end. "
        "Yanbu bypass cargo (Arab Light, 14d lead time) bridges the gap without "
        "breaching the 8-day cover floor. Taper draw from day 11. "
        "Total draw: 1.40 MT over 14 days. Reserve post-event: 3.63 MT (68% fill)."
    ),
)


async def main() -> None:
    log.info("Seeding SAGE knowledge base…")
    os.makedirs("demo_cache", exist_ok=True)

    # ── Init KB ────────────────────────────────────────────────────────────────
    from knowledge.connection import init as kb_init
    await kb_init()
    log.info("KB initialised.")

    # ── 1. Foundational wiki pages now come from the context bundle's narratives
    #       layer (instantiated in step 2b below), NOT hardcoded here. ───────────

    # ── 2. Write episodic signals ──────────────────────────────────────────────
    from graphiti_core.nodes import EpisodeType
    from knowledge.connection import _get_graphiti
    from knowledge.schema.entities import ENTITY_TYPES
    from knowledge.schema.edges import EDGE_TYPES, EDGE_TYPE_MAP

    g = _get_graphiti()
    log.info("Writing %d episodic signals…", len(EPISODES))
    now = datetime.now(timezone.utc)
    for ep in EPISODES:
        try:
            await g.add_episode(
                name=ep["name"],
                episode_body=ep["body"],
                source=EpisodeType.text,
                source_description=ep["source_desc"],
                reference_time=now,
                entity_types=ENTITY_TYPES,
                edge_types=EDGE_TYPES,
                edge_type_map=EDGE_TYPE_MAP,
            )
            log.info("  episode: %s", ep["name"])
        except Exception as exc:
            log.warning("  episode FAILED (%s): %s", ep["name"], exc)

    # ── 2b. Instantiate the context bundle (foundational static knowledge) ──────
    # Loads + validates the provenance-tracked bundle, then writes its structural
    # episodes BEFORE risk states so the typed entity nodes and structural edges
    # exist first. This is the SAGE.instantiate(bundle) step.
    from knowledge.context import load_bundle
    bundle = load_bundle(CONTEXT_BUNDLE)
    bsum = bundle.summary()
    log.info("Context bundle '%s' (schema %s): nodes=%s edges=%s by_tier=%s",
             bsum["bundle_id"], bsum["schema"], bsum["nodes"], bsum["edges"], bsum["by_tier"])
    counts = await bundle.instantiate(g, reference_time=now)
    log.info("Instantiated bundle: %d fact episodes + %d narrative pages "
             "(wiki store + reconciled episodes).", counts["facts"], counts["narratives"])

    # ── 3. Write risk states ───────────────────────────────────────────────────
    from knowledge.api.write import write_risk_state
    log.info("Writing %d risk states…", len(RISK_STATES))
    for rs in RISK_STATES:
        try:
            ref = await write_risk_state(**rs)
            log.info("  risk_state: %s → score=%.2f  episode=%s", rs["entity"], rs["score"], ref.episode_uuid)
        except Exception as exc:
            log.warning("  risk_state FAILED (%s): %s", rs["entity"], exc)

    # ── 4. Write scenario ──────────────────────────────────────────────────────
    from knowledge.api.write import write_scenario, write_procurement, write_spr_schedule
    log.info("Writing scenario sc-20260628-001…")
    try:
        ref = await write_scenario(SCENARIO)
        log.info("  scenario: %s", ref.episode_uuid)
    except Exception as exc:
        log.warning("  scenario FAILED: %s", exc)

    log.info("Writing procurement recommendation…")
    try:
        ref = await write_procurement(PROCUREMENT)
        log.info("  procurement: %s", ref.episode_uuid)
    except Exception as exc:
        log.warning("  procurement FAILED: %s", exc)

    log.info("Writing SPR schedule…")
    try:
        ref = await write_spr_schedule(SPR_SCHEDULE)
        log.info("  spr_schedule: %s", ref.episode_uuid)
    except Exception as exc:
        log.warning("  spr_schedule FAILED: %s", exc)

    # ── 5. Read back and verify ────────────────────────────────────────────────
    log.info("─── Verification ────────────────────────────────────────────────")
    from knowledge.api.read import get_risk_scores, get_wiki_page, get_available_suppliers
    from knowledge.synthesis import list_wiki_entities as list_wiki_pages

    wiki_pages = list_wiki_pages()
    log.info("Wiki pages on disk: %s", wiki_pages)

    scores = await get_risk_scores()
    log.info("Risk scores in graph: %d entities", len(scores))
    for s in scores:
        log.info("  %-30s score=%.2f  band=%s", s.entity, s.score, s.band)

    page = await get_wiki_page("Strait of Hormuz")
    log.info("Wiki page retrieved: %s (length=%d chars)", page.entity, len(page.content))

    # Verify structural data landed (the values Systems 2/3/4 read)
    from knowledge.api.read import get_subgraph, get_grade_specs, get_routes, get_spr_state
    suppliers = await get_available_suppliers(risk_max=1.0)
    log.info("Suppliers queryable: %d (with daily_export_mbpd populated)", len(suppliers))
    grades = await get_grade_specs("Jamnagar Refinery")
    log.info("Jamnagar CONFIGURED_FOR grades: %d (api_gravity/compatibility populated)", len(grades))
    routes = await get_routes(risk_max=1.0)
    log.info("Corridors queryable: %d (with throughput_mbpd)", len(routes))
    caverns = await get_spr_state()
    log.info("SPR caverns queryable: %d (with capacity_mmt/current_fill_mmt)", len(caverns))
    sub = await get_subgraph("Strait of Hormuz", hops=2)
    log.info("Hormuz 2-hop subgraph: %d nodes, %d edges (ARIO input)", len(sub.nodes), len(sub.edges))

    log.info("─── Seed complete ────────────────────────────────────────────────")
    log.info("  FalkorDB browser: http://localhost:3000")
    log.info("  API:              http://localhost:8000/api/risk-scores")
    log.info("  Wiki page:        http://localhost:8000/api/wiki/Strait%%20of%%20Hormuz")


if __name__ == "__main__":
    asyncio.run(main())
