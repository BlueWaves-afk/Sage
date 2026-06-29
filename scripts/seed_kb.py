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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger("seed_kb")

# ─── 1. Wiki pages ────────────────────────────────────────────────────────────

WIKI_PAGES: dict[str, str] = {
    "Strait of Hormuz": """\
# Strait of Hormuz — Intelligence Page

## Strategic Role
The Strait of Hormuz is the world's most critical oil chokepoint. Approximately 20–21 million
barrels per day (mbpd) transit the strait — roughly 20% of global petroleum liquids and 25–30%
of global LNG trade. For India, it is the single most important maritime corridor: ~88% of
India's crude oil imports flow through or originate in the Persian Gulf.

## Physical Characteristics
- Navigable channel: two 3.2 km lanes (inbound/outbound), separated by a 3.2 km median
- Minimum depth: 27 m (adequate for VLCCs)
- Iranian territorial waters span the northern edge; Omani waters the southern
- H3 resolution-4 cells: 8526800bfffffff (central channel)

## Historical Disruption Events
| Event | Date | Duration | Impact |
|---|---|---|---|
| Tanker War (Iran-Iraq) | 1984–1988 | ~4 years | 500+ vessels attacked |
| Op Praying Mantis | Apr 1988 | 1 day | 2 Iranian frigates sunk |
| Gulf War I blockade scare | Aug–Nov 1990 | 3 months | Price +150% |
| 2019 tanker attacks | May–Jun 2019 | 6 weeks | Price +4% |
| 2024 shadow fleet surge | Jan–Mar 2024 | Ongoing | 15% AIS dark rate |

## Bypass Alternatives
- **Saudi East-West Pipeline (Petroline):** 5 mbpd capacity; Yanbu Red Sea terminal
- **UAE Abu Dhabi Crude Oil Pipeline (ADCO):** 1.5 mbpd; Fujairah terminal
- **Iraq-Turkey Pipeline (ITP):** 1.6 mbpd; Ceyhan Mediterranean terminal (currently offline)
- Combined bypass capacity: ~8 mbpd vs. 21 mbpd flow — significant gap

## SAGE Risk Profile
- Primary risk drivers: AIS dark-vessel activity, IRGC naval exercises, US-Iran diplomatic temperature
- Triage threshold: force_synthesis=True on any AIS gap > 4h in the strait corridor
- Connected entities: Saudi Aramco, NIOC, ADNOC, Vadinar Port, Paradip Port
""",

    "Saudi Aramco": """\
# Saudi Aramco — Intelligence Page

## Profile
Saudi Aramco (officially Saudi Arabian Oil Company) is the world's largest oil producer and
India's single largest crude supplier. In FY2024–25, India imported approximately 39.1 MT of
crude from Saudi Arabia, accounting for ~17% of India's total crude imports.

## Export Grades
| Grade | API | Sulfur % | Typical Destination |
|---|---|---|---|
| Arab Light | 32.8 | 1.96 | Jamnagar, Mangaluru |
| Arab Medium | 30.4 | 2.59 | Vizag, Paradip |
| Arab Heavy | 27.4 | 2.89 | Chennai (capacity permitting) |
| Arab Extra Light | 40.9 | 1.15 | Bina, Panipat |

## Export Terminals
- **Ras Tanura:** World's largest offshore oil loading facility; capacity ~8.5 mbpd
- **Yanbu (Red Sea):** Petroline western terminal; 5 mbpd; bypasses Hormuz
- **Ju'aymah:** Offshore terminal; NGL and crude

## Bypass Capability
If Hormuz closes, Saudi can shift 5 mbpd through Petroline to Yanbu.
India could continue receiving Arab Light via Suez/Cape route from Yanbu,
adding ~7–12 days transit and ~$2–3/bbl freight premium.

## Current Status
- Active exporter, no sanctions
- Aramco Margin Compression Program: cost target $2.80/bbl opex
- OPEC+ quota: 9.0 mbpd production ceiling (as of Q1 2026)

## SAGE Risk Profile
- Low sanctions risk (score: 0.0)
- Corridor risk: moderate if Hormuz disrupted; LOW if Yanbu bypass activated
- Connected entities: Strait of Hormuz, Ras Tanura Port, Jamnagar Refinery
""",

    "Jamnagar Refinery": """\
# Jamnagar Refinery — Intelligence Page

## Overview
Reliance Industries' Jamnagar complex is the world's largest refining hub, comprising:
- **DTA Refinery:** 668,000 bpd nameplate capacity
- **SEZ Refinery:** 580,000 bpd nameplate capacity
- **Combined:** 1.24 mbpd — largest single refinery complex globally

Located in Jamnagar district, Gujarat. Dedicated SPM (Single Point Mooring) infrastructure
handles VLCCs directly offshore.

## Crude Diet
Jamnagar is a complex refinery (Nelson Complexity Index ~11.3) capable of processing a wide
range of crudes. Primary feedstock is medium-sour Gulf crudes:
- Arab Medium (primary)
- Iraqi Basra Medium/Heavy
- Iranian Heavy (historically; currently under sanctions restrictions)
- Russian Urals/ESPO (increased post-2022 for price advantage)

## API/Sulfur Range
- Preferred API: 28–35°
- Sulfur tolerance: up to 3.5% (secondary processing units)
- Incompatible: ultra-heavy (API < 20) without blending

## Strategic Reserve Link
- Feeds Vizag SPR Cavern via Vadinar-Vizag crude pipeline (proposed)
- Currently SPR fill is via Paradip for MRPL crude

## SAGE Risk Profile
- High exposure to Hormuz disruption (primary supply corridor)
- Bypass feasibility: HIGH (can absorb Yanbu-routed Arab Light with <5% cost premium)
- Inventory buffer: ~30 days crude tank capacity on-site
- Connected entities: Vadinar Port, Arab Medium grade, Vizag SPR Cavern
""",

    "Vadinar Port": """\
# Vadinar Port — Intelligence Page

## Overview
Vadinar (also Sikka) is a deep-water port on the Gulf of Kutch, Gujarat, operated primarily
by Nayara Energy (formerly Essar Oil). It is the primary crude import terminal for Jamnagar
and Vadinar refineries.

## Specifications
- Berth depth: 18.5 m (VLCC capable, fully laden)
- Throughput capacity: ~36 MT/year (crude)
- SPM buoys: 2 × 250,000 DWT
- Tank farm: 4.5 million BBL crude storage

## Traffic (CY2025)
- VLCCs handled: ~420/year (~35/month)
- Primary sources: Saudi Arabia (40%), UAE (25%), Iraq (20%), Others (15%)
- Average discharge time: 36 hours per VLCC

## SAGE Risk Profile
- Hormuz linkage: DIRECT — all Gulf crude arrives via Hormuz before Vadinar
- Bypass routing: Yanbu crude can route Suez → Arabian Sea → Vadinar (no port change needed)
- Congestion risk: LOW (adequate berth capacity)
- Connected entities: Jamnagar Refinery, Strait of Hormuz, Saudi Aramco
""",

    "Vizag SPR Cavern": """\
# Vizag SPR Cavern — Intelligence Page

## Overview
The Visakhapatnam (Vizag) Strategic Petroleum Reserve is India's first commissioned SPR
facility, managed by Indian Strategic Petroleum Reserves Limited (ISPRL). Located at
Visakhapatnam, Andhra Pradesh.

## Specifications
- Storage type: Underground rock cavern (excavated granite)
- Total capacity: 1.33 million metric tonnes (MT) ≈ 9.75 million BBL
- Operational since: 2016
- Crude grade stored: Iranian Heavy (historically); currently Arab Medium and Basra Heavy

## Current Fill Status (estimated, Q1 2026)
- Fill level: ~1.15 MT (86% full)
- Days of cover (at 4.5 mbpd import rate): ~8.9 days
- Cavern pressure: nominal operational range

## Draw Rates
- Maximum draw rate: ~0.20 MT/day (≈ 1.46 mbpd)
- Time to full depletion at max draw: ~5.75 days
- Typical emergency draw: 0.12–0.18 MT/day

## Policy Context
India's combined SPR capacity (Vizag + Mangaluru + Padur) = 5.33 MT (~39 MB).
At 4.5 mbpd import rate, this covers ~11.7 days. The IEA recommends 90 days minimum.
India's total (SPR + commercial) cover is approximately 60–65 days.

## SAGE Risk Profile
- Primary response asset for Hormuz disruption
- Trigger draw policy: activated when gap > 0.5 mbpd sustained > 72h
- Connected entities: Jamnagar Refinery, Mangaluru SPR Cavern, Padur SPR Cavern
""",

    "NIOC": """\
# NIOC — Intelligence Page

## Profile
National Iranian Oil Company. Prior to 2018 JCPOA withdrawal, Iran supplied ~15–20 MT/year
of crude to India (primarily to Mangaluru Refinery and Nayara). Currently under comprehensive
US and EU sanctions; Indian imports effectively zero since 2019.

## Sanctions Status
- **US OFAC:** SDN-listed entity; secondary sanctions risk for any purchaser
- **EU:** Comprehensive sanctions including oil sector
- **UN:** Arms embargo only (not oil)

## Historical Indian Supply (pre-sanctions)
- Primary grades: Iranian Heavy (31° API, 1.85% S), Iranian Light (34° API, 1.37% S)
- Destination: Mangaluru (MRPL) — configured for Iranian Heavy
- Average price: ~$5–7/bbl discount to Arab Light equivalent

## SAGE Risk Profile
- Sanctions risk: CRITICAL (score: 1.0)
- Supply status: UNAVAILABLE for Indian importers under US secondary sanction risk
- Note: Any resumption requires OFAC waiver — currently no waiver active
- Connected entities: Strait of Hormuz, Mangaluru Refinery, OFAC
""",
}

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

    # ── 1. Write wiki pages ────────────────────────────────────────────────────
    from knowledge.synthesis import write_wiki_page
    log.info("Writing %d wiki pages…", len(WIKI_PAGES))
    for entity, content in WIKI_PAGES.items():
        write_wiki_page(entity, content)
        log.info("  wiki: %s", entity)

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

    log.info("─── Seed complete ────────────────────────────────────────────────")
    log.info("  FalkorDB browser: http://localhost:3000")
    log.info("  API:              http://localhost:8000/api/risk-scores")
    log.info("  Wiki page:        http://localhost:8000/api/wiki/Strait%%20of%%20Hormuz")


if __name__ == "__main__":
    asyncio.run(main())
