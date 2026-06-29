# SAGE — AI-Driven Energy Supply Chain Resilience

**SAGE** = **S**ynthesis-first **A**gentic **G**raph-**E**nhanced knowledge architecture.

Built for ET AI Hackathon 2.0, Problem Statement 2. India sources ~88% of its crude oil from imports, with 40–45% transiting the Strait of Hormuz. SAGE monitors geopolitical and logistics risk signals continuously, models disruption scenarios and their downstream economic impacts, and generates executable procurement rerouting recommendations — turning a reactive crisis response into a managed, anticipatory process.

---

## What Makes SAGE Different

Traditional supply chain tools are **retrospective** — they record what happened. SAGE is **anticipatory**: when a high-priority signal arrives, it simultaneously updates ground truth and forks an isolated speculative future, pre-staging responses before a threshold is even crossed.

| Capability | Graphiti alone | SAGE |
|---|---|---|
| Records past events | ✓ | ✓ via Graphiti |
| Maintains current ground truth | ✓ | ✓ via Graphiti |
| Detects risk threshold crossing | ✗ | ✓ LangGraph monitor |
| Projects signal trajectories forward | ✗ | ✓ Anticipatory Sandbox |
| Pre-stages recommendations before threshold | ✗ | ✓ Anticipatory Sandbox |
| Autonomous end-to-end pipeline | ✗ | ✓ no human initiation required |

**Demo metric:** 300ms (pre-staged) vs 8,500ms (cold) response time from threshold crossing to ranked recommendations. 28× speedup by moving reasoning earlier in time.

---

## Architecture

Five systems, one shared knowledge base, one autonomous orchestration loop.

```
                        ┌─────────────────────────────────────────┐
                        │           SAGE Knowledge Base           │
                        │   Graphiti + FalkorDB + /wiki store     │
                        │   Three stores: episodic · graph · vec  │
                        └────────────────┬────────────────────────┘
                                         │  read/write API only
          ┌──────────────┬───────────────┼───────────────┬──────────────┐
          ▼              ▼               ▼               ▼              ▼
   sensory_agent   scenario_agent  alt_procurement  reserve_optim  visualizer
   (sense)         (reason)        _agent (act)     _agent (act)   _agent (show)

                        ▲
               orchestration/
               LangGraph autonomous loop
               threshold monitor · sandbox
```

The knowledge base is the nervous system — it receives signals, synthesizes them, and its own state changes trigger the downstream agents automatically. No human types a query to start the pipeline.

---

## Folder Structure

```
sage/
│
├── CLAUDE.md                          # AI assistant rules — structural laws, import boundaries, conventions
├── README.md                          # this file
├── pyproject.toml                     # single Python project; all packages discoverable via setuptools
├── docker-compose.yml                 # 12-container deployment on EC2 g4dn.xlarge
│
├── contracts/                         # shared Pydantic contracts — imported by every package, imports nothing
│   ├── signal.py                      # NormalizedSignal: the common shape all sensory sub-agents emit
│   ├── outputs.py                     # ScenarioOutputData, ProcurementRecData, SPRScheduleData
│   └── bands.py                       # risk band thresholds (calm/watch/elevated/action/critical) — single source of truth
│
├── knowledge/                         # the knowledge base — only module that talks to Graphiti/FalkorDB
│   ├── connection.py                  # FalkorDriver bootstrap; build_indices_and_constraints()
│   ├── triage.py                      # embedding similarity gate → synthesize / extract / store / drop
│   ├── synthesis.py                   # Nova Pro wiki agent: reconciles signals into /wiki prose, then hands to Graphiti
│   ├── schema/
│   │   ├── entities.py                # 11 entity types (Corridor, Supplier, Refinery…) as Pydantic + ENTITY_TYPES registry
│   │   └── edges.py                   # 9 edge types (RISK_STATE, EXPORTS_VIA…) + EDGE_TYPES + EDGE_TYPE_MAP
│   ├── wiki/                          # Store 1: one Markdown file per entity, git-versioned narrative pages
│   └── api/
│       ├── read.py                    # typed *View read wrappers — get_risk_scores, get_subgraph, copilot_query…
│       └── write.py                   # ingest_signal, write_scenario, write_procurement, write_spr_schedule…
│
├── orchestration/                     # LangGraph autonomous loop — drives the 5-system pipeline without human input
│   ├── state.py                       # SAGEState TypedDict: signal_id, entity, risk_score, band, pipeline_stage…
│   ├── monitor.py                     # polls get_risk_scores() every 30s; fires triggers on band crossings
│   ├── sandbox.py                     # anticipatory fork: subgraph snapshot → trajectory → GNN → pre-stage systems 3+4
│   ├── triggers.py                    # on_elevated / on_action / on_critical / on_sandbox_promoted event handlers
│   └── graph.py                       # LangGraph StateGraph wiring: SENSE→TRIAGE→SAGE→SANDBOX→SCENARIO→PROCURE→RESERVE
│
├── sensory_agent/                     # System 1 — four always-on sub-agents; the only system that writes raw signals
│   ├── ais.py                         # AIS websocket (aisstream.io), H3 indexing, HABIT imputation, dark-vessel detection, SAR fusion
│   ├── news.py                        # GDELT + NewsAPI every 15 min; Nova Micro extracts {actor, action, target, severity}
│   ├── sanctions.py                   # OFAC/EU/UN diff every 6h; any new addition is force_synthesis=True immediately
│   └── prices.py                      # EIA + yfinance every 5 min; BOCD changepoint detection; regime-switching HMM
│
├── scenario_agent/                    # System 2 — disruption cascade modeller; triggered by sandbox or confirmed threshold
│   ├── ario.py                        # ARIO dynamic IO cascade (Hallegatte 2008): day-by-day supply shock propagation
│   ├── runner.py                      # reads subgraph from KB → runs ARIO (confirmed) or GNN (speculative) → write_scenario()
│   └── gnn/
│       ├── model.py                   # PyTorch GNN surrogate: learns ARIO param→output mapping; <150ms on T4 GPU
│       └── train.py                   # generates ARIO Monte Carlo sweep → trains and saves GNN weights
│
├── alt_procurement_agent/             # System 3 — finds and ranks alternative crude sources when primary routes are blocked
│   ├── routing.py                     # OR-Tools MILP + RRNCO heuristic: asymmetric cost matrix over corridors and ports
│   ├── grade.py                       # RF + Peng-Robinson EOS: crude API gravity/sulfur compatibility per refinery
│   ├── rank.py                        # TOPSIS multi-objective ranking: cost × lead time × compatibility × corridor risk
│   └── runner.py                      # reads suppliers/grades/routes from KB → ranks options → write_procurement()
│
├── reserve_optim_agent/               # System 4 — optimal SPR drawdown schedule under supply shock uncertainty
│   ├── sdp.py                         # Bellman iteration over (reserve, regime, price, day) state space; CMDP Lagrangian relaxation
│   ├── options.py                     # real-options valuation: quantifies the value of waiting before committing to drawdown
│   └── runner.py                      # reads SPR state + scenario gap from KB → solves SDP → write_spr_schedule()
│
├── visualizer_agent/                  # System 5 — digital twin UI; pure consumer, reads everything, writes nothing
│   ├── api_gateway/
│   │   └── main.py                    # FastAPI + WebSocket: REST endpoints, risk-score push, copilot, wiki page on node click
│   └── frontend/
│       └── src/                       # React + deck.gl: geospatial KG map, H3 heatmap, staged alert, pipeline bar, copilot
│
└── demo_cache/                        # pre-recorded Feb 23–28 2026 Hormuz signal replay for DEMO_MODE=true
```

---

## Key Structural Rules

These rules are enforced by `CLAUDE.md` and must not be violated:

**1. Import boundaries**
`contracts/` → no internal imports.
`knowledge/` → `contracts/` only.
Everyone else → `contracts/` and `knowledge/api/` only.
No agent imports another agent. No one imports `graphiti_core` outside `knowledge/`.

**2. Single write path**
Raw signals never go to Graphiti directly. The only path is:
`NormalizedSignal → ingest_signal() → triage → synthesis → add_episode()`

**3. Speculative isolation**
Sandbox outputs are never written as `RISK_STATE` on live nodes. Speculative risk lives only on `PendingScenario` nodes.

**4. Frozen contracts**
`RISK_STATE` edge field names are frozen after Week-1 sign-off. Any change bumps `schema_version` and requires team approval.

---

## Knowledge Base — Contracts & Schema

The knowledge base is the only module that writes to Graphiti/FalkorDB. Everything else talks to it through a typed API. The schema and contracts are the **Week-1 lock-in artifact** — four people build in parallel against these, so stability matters more than perfection.

Full normative spec: [`.claude/design/SAGE_Schema_and_Contracts_Spec.md`](.claude/design/SAGE_Schema_and_Contracts_Spec.md)

---

### The Three Stores

| Store | What | Where | Owner |
|---|---|---|---|
| **Episodic subgraph** | Every synthesized episode node, non-lossy, with `MENTIONS` edges back to extracted entities. Ground-truth provenance. | FalkorDB (Graphiti-managed) | Graphiti |
| **Semantic entity subgraph** | Typed entity nodes + typed edges + validity windows (bitemporal) + 1024-D embeddings for hybrid search. | FalkorDB (Graphiti-managed) | Graphiti |
| **/wiki store** | One Markdown file per entity — the reconciled, human-readable intelligence page. Git-versioned history. | `knowledge/wiki/` (Docker volume) | SAGE (`knowledge/synthesis.py`) |

All three are written in one sequence by `knowledge/api/write.py:ingest_signal()`. No other code path writes to any store.

---

### The 7 Contracts

Every contract is a Python Pydantic v2 `BaseModel`. All carry `schema_version`. Consumers assert on the major version at startup.

#### C0 — Connection
```python
from knowledge.connection import build_graphiti, bootstrap
# FalkorDriver(database='sage') passed as graph_driver= to Graphiti()
# database must never be None — silently falls back to default_db otherwise
```

#### C1 — Normalized Signal (`contracts/signal.py`)
The common envelope all four `sensory_agent` sub-agents emit onto the Redis queue. Stable envelope + per-source `payload` pocket so sub-agents evolve independently.

```python
class NormalizedSignal(BaseModel):
    signal_id: str           # ULID/UUID
    source: Literal["ais", "gdelt", "news", "sanctions", "price"]
    observed_at: datetime    # when true in the world → becomes Graphiti reference_time
    priority_hint: Literal["HIGH", "MED", "LOW"]
    force_synthesis: bool    # True bypasses triage gate (sanctions adds, BOCD breakpoints)
    entity_refs: list[str]   # display names of affected entities
    summary: str             # one-line description
    payload: dict            # source-specific fields (AisPayload, EventPayload, etc.)
```

#### C2 — Entity Ontology (`knowledge/schema/entities.py`)
11 node types passed to `graphiti.add_episode(entity_types=ENTITY_TYPES)`. Every field is `Optional` — required fields cause extraction failures. Docstrings and `Field(description=...)` are read verbatim by the extraction LLM; write them carefully.

| Entity | What it represents |
|---|---|
| `Corridor` | Maritime chokepoint — Hormuz, Bab-el-Mandeb, Suez. `choke_severity` 0–1, H3 cells. |
| `Supplier` | Crude exporting org — Saudi Aramco, NIOC. `daily_export_mbpd`, `sanctioned`. |
| `Refinery` | Processing plant — Jamnagar, Mangaluru. `inventory_days`, lat/lon. |
| `CrudeGrade` | Oil assay — Arab Medium, Bonny Light. `api_gravity`, `sulfur_pct`. |
| `Port` | Physical terminal — Vadinar, Yanbu. `draft_m`, `congestion`. |
| `SPRCavern` | Reserve site — Vizag (1.33 MMT), Mangaluru (1.5), Padur (2.5). |
| `Vessel` | Individual tanker by MMSI. `sanctioned`, `operator` (beneficial owner). |
| `GeoEvent` | Discrete event — IRGC exercise, Houthi strike. `event_time`, `severity`. |
| `Authority` | Sanctioning body — OFAC, EU, UN. Referenced by `SANCTIONED_BY` edges. |
| `PendingScenario` | Speculative sandbox fork. `confidence`, `status` (speculative→promoted→expired). |
| `ScenarioOutput` | Confirmed cascade result anchored to an entity. |

#### C3 — Edge Ontology (`knowledge/schema/edges.py`)
9 edge types + `EDGE_TYPE_MAP`. The `("Entity","Entity")` wildcard covers `RISK_STATE` and `AFFECTS_SCENARIO` — valid between any node pair.

```
Supplier   ──EXPORTS_VIA──►  Corridor
Corridor   ──FEEDS──────────►  Port
Port       ──SUPPLIES───────►  Refinery
Refinery   ──CONFIGURED_FOR─►  CrudeGrade   (carries yield_pct, compatibility 0–1)
Vessel     ──SANCTIONED_BY──►  Authority    (carries list_name, effective_date)
Supplier   ──SANCTIONED_BY──►  Authority
Supplier   ──BYPASS_ROUTE───►  Port         (carries cost_premium USD/bbl, added_days)
Refinery   ──FEEDS_RESERVE──►  SPRCavern
(any)      ──RISK_STATE─────►  (any)        ⭐ see C4
(any)      ──AFFECTS_SCENARIO► (any)        links entity to its PendingScenario/ScenarioOutput
```

#### C4 — RISK_STATE Edge ⭐ (`knowledge/schema/edges.py:RiskState`)
The contract the autonomous loop runs on. **Field names are frozen after Week-1 sign-off.** Computed by `sensory_agent`, stored by SAGE, polled by the LangGraph monitor every 30s.

```python
class RiskState(BaseModel):
    score: float          # fused risk 0–1
    band: str             # computed by SAGE at write time — never re-derive downstream
    factor_ais: float     # AIS / dark-vessel contribution
    factor_gdelt: float   # news / GDELT tone contribution
    factor_price: float   # price / war-risk-premium contribution
    factor_sanctions: float
    rationale: str        # one-line driver explanation
    model_version: str    # which fusion model produced this
```

Risk bands (`contracts/bands.py`) — single source of truth:

| Band | Score | What fires | UI colour |
|---|---|---|---|
| `calm` | < 0.25 | — | phosphor green |
| `watch` | 0.25 – 0.45 | — | cyan |
| `elevated` | 0.45 – 0.70 | sandbox fork if P(crossing in 24h) > 0.5 | amber |
| `action` | 0.70 – 0.90 | promote sandbox / fire Systems 2–4 | red |
| `critical` | ≥ 0.90 | immediate human escalation | pulsing red |

#### C5 — Output Episodes (`contracts/outputs.py`)
Systems 2/3/4 write results through typed data models. All outputs carry `scenario_id` so the full chain (signal → scenario → procurement → SPR) is retrievable in one graph hop.

| Model | Written by | Key fields |
|---|---|---|
| `ScenarioOutputData` | `scenario_agent` | `gap_mbpd`, `feedstock_gap_timeline[]`, `price_impact_low/high`, `spr_depletion_days`, `assumptions{}` |
| `ProcurementRecData` | `alt_procurement_agent` | `ranked: list[ProcurementOption]` — each with `topsis_score`, `grade_compatibility`, `rationale` |
| `SPRScheduleData` | `reserve_optim_agent` | `daily_plan: list[SPRDay]`, `prob_above_buffer`, `policy_memo` |

#### C6 — Sandbox / PendingScenario
Lifecycle of a speculative fork: `speculative` → `promoted` (on threshold crossing, ≤30s) → `expired` (72h TTL with no crossing). Speculative outputs are **never** written as `RISK_STATE` on live nodes.

#### C7 — Read/Write API (`knowledge/api/`)
The only interface all other agents use. Returns typed `*View` Pydantic models — never raw Graphiti internals.

```python
# Write (knowledge/api/write.py)
ingest_signal(signal: NormalizedSignal) -> IngestResult    # sensory_agent entry point
write_scenario(data: ScenarioOutputData) -> EpisodeRef     # scenario_agent
write_procurement(data: ProcurementRecData) -> EpisodeRef  # alt_procurement_agent
write_spr_schedule(data: SPRScheduleData) -> EpisodeRef    # reserve_optim_agent
write_pending(confidence, projected_crossing_hours, scenario_ref) -> EpisodeRef
promote_pending(scenario_ref: str) -> EpisodeRef           # LangGraph monitor on crossing

# Read (knowledge/api/read.py)
get_risk_scores() -> list[RiskScoreView]          # monitor + visualizer — all RISK_STATE edges
get_subgraph(entity, hops=2) -> SubgraphView      # scenario_agent — cascade initialisation
get_available_suppliers(risk_max=0.4) -> list[SupplierView]   # procurement — risk < max, not sanctioned
get_grade_specs(refinery) -> list[GradeSpecView]  # procurement — CONFIGURED_FOR edges
get_routes(risk_max=0.5) -> list[CorridorView]    # procurement — open corridors
get_spr_state() -> list[SPRCavernView]            # reserve — Vizag/Mangaluru/Padur fill levels
copilot_query(q: str) -> CopilotAnswer            # visualizer — EA-GraphRAG routed, cited
get_wiki_page(entity: str) -> WikiPage            # visualizer — narrative page on node click
```

---

## Wiring an Agent to the Knowledge Base

The KB exposes one import surface: `knowledge/api/read.py` and `knowledge/api/write.py`. No agent ever imports `graphiti_core`, `falkordb`, or any other KB internals. This section is the complete integration guide for any agent — current or future.

---

### 0. One-time startup (container entrypoint)

Every container that uses the KB must call `init()` once before any read or write. This connects to FalkorDB, builds indices, and seeds edge types.

```python
# In your container's startup / FastAPI lifespan / LangGraph entry
from knowledge.connection import init as kb_init
await kb_init()   # idempotent — safe to call on every boot
```

After `init()`, all KB functions are safe to call from any async context.

---

### 1. Writing signals (sensory_agent)

System 1 sub-agents push `NormalizedSignal` onto the Redis queue. The KB consumer loop picks them up and runs the full triage → synthesis → graph pipeline automatically. Sub-agents never call `ingest_signal()` directly.

```python
# sensory_agent/ais.py  (or news.py / sanctions.py / prices.py)
from contracts.signal import NormalizedSignal, AisPayload
from knowledge.ingest_queue import push_signal

signal = NormalizedSignal(
    signal_id="ais-20260228-001",
    source="ais",
    observed_at=datetime.now(timezone.utc),
    ingested_at=datetime.now(timezone.utc),
    priority_hint="HIGH",
    force_synthesis=True,           # dark vessel → bypass triage gate
    entity_refs=["Strait of Hormuz", "MT Destiny"],
    h3_cells=["8526800bfffffff"],
    summary="MT Destiny went AIS-dark near Larak Island — 6h gap, SAR confirmed",
    payload=AisPayload(
        mmsi="123456789", dark_vessel=True, anomaly_score=0.92, gap_hours=6.0
    ).model_dump(),
)
await push_signal(signal)   # pushes to Redis; consumer handles the rest
```

**Sanctions and price changepoints** set `force_synthesis=True` to bypass similarity triage — they are always written immediately.

---

### 2. Writing risk state (after fusion aggregation)

After the fusion model aggregates signals for a 30-second window, call `write_risk_state()` directly. This is the only function that creates `RISK_STATE` edges on live nodes.

```python
from knowledge.api.write import write_risk_state

await write_risk_state(
    entity="Strait of Hormuz",
    score=0.73,
    factor_ais=0.41,
    factor_gdelt=0.55,
    factor_price=0.30,
    factor_sanctions=0.00,
    rationale="3 dark-vessel gaps + BOCD price breakpoint",
    model_version="gbm-platt-v1.0",
    observed_at=datetime.now(timezone.utc),
)
```

> **Isolation rule:** never call `write_risk_state()` from the sandbox. Speculative risk uses `write_pending()` only.

---

### 3. Reading risk scores (LangGraph monitor)

```python
from knowledge.api.read import get_risk_scores
from contracts.bands import ACTION_THRESHOLD, CRITICAL_THRESHOLD

scores = await get_risk_scores()   # list[RiskScoreView]

for view in scores:
    print(view.entity, view.score, view.band)
    # view.factors → {"ais": 0.41, "gdelt": 0.55, "price": 0.30, "sanctions": 0.00}
    # view.valid_at, view.recorded_at → bitemporal timestamps

    if view.score >= ACTION_THRESHOLD:
        # fire systems 2/3/4
        pass
```

`RiskScoreView` matches the canonical JSON shape from §6.2 of the schema spec exactly.

---

### 4. Reading subgraph for cascade modelling (scenario_agent)

```python
from knowledge.api.read import get_subgraph

subgraph = await get_subgraph("Strait of Hormuz", hops=2)
# subgraph.nodes → list of entity dicts with uuid, display_name, labels, attributes
# subgraph.edges → list of edge dicts with relation_type, fact, valid_at, attributes
```

Use `subgraph.nodes` to initialise the ARIO IO matrix. Use `subgraph.edges` to identify which suppliers, ports, and refineries are connected to the disrupted corridor.

---

### 5. Writing scenario/procurement/SPR outputs (Systems 2/3/4)

Each system calls its dedicated write function. The function builds episode prose, writes to Graphiti, and creates an `AFFECTS_SCENARIO` edge back to the trigger entity so the copilot can retrieve the full chain in one hop.

```python
# scenario_agent
from knowledge.api.write import write_scenario
from contracts.outputs import ScenarioOutputData

result = await write_scenario(ScenarioOutputData(
    scenario_id="sc-20260228-001",
    trigger_entity="Strait of Hormuz",
    status="confirmed",
    confidence=0.85,
    gap_mbpd=1.2,
    gap_duration_days=14.0,
    feedstock_gap_timeline=[1.1, 1.2, 1.3, 1.2, 1.1, 1.0, 0.9],
    price_impact_low=8.0,
    price_impact_high=22.0,
    spr_depletion_days=6.5,
    assumptions={"import_dependence_pct": {"value": 88.2, "unit": "%", "source": "PPAC 2025"}},
))
# result.episode_uuid  — reference this in subsequent procurement/SPR writes

# alt_procurement_agent
from knowledge.api.write import write_procurement
from contracts.outputs import ProcurementRecData, ProcurementOption, ScoreBreakdown

await write_procurement(ProcurementRecData(
    scenario_id="sc-20260228-001",
    status="confirmed",
    ranked=[
        ProcurementOption(
            supplier="Saudi Aramco", grade="Arab Light", route_via="Yanbu bypass",
            landed_cost_usd_bbl=85.30, lead_time_days=12.0,
            grade_compatibility=0.92, corridor_risk=0.18, topsis_score=0.87,
            score_breakdown=ScoreBreakdown(
                cost_score=0.78, lead_time_score=0.85,
                grade_compatibility_score=0.92, corridor_risk_score=0.82,
            ),
            rationale="Yanbu pipeline bypasses Hormuz entirely...",
        )
    ],
))

# reserve_optim_agent
from knowledge.api.write import write_spr_schedule
from contracts.outputs import SPRScheduleData, SPRDay

await write_spr_schedule(SPRScheduleData(
    scenario_id="sc-20260228-001",
    status="confirmed",
    daily_plan=[
        SPRDay(day=1, action="draw", volume_mmt=0.18,
               reserve_after_mmt=5.15, days_cover_after=9.2,
               decision_driver="gap onset — begin draw"),
    ],
    prob_above_buffer=0.96,
    constraint_satisfied=True,
    policy_memo="Draw at 0.18 MMT/day for 14 days...",
))
```

---

### 6. Reading supply chain state for procurement routing (alt_procurement_agent)

```python
from knowledge.api.read import get_available_suppliers, get_grade_specs, get_routes

# Suppliers with risk < 0.4, not sanctioned
suppliers = await get_available_suppliers(risk_max=0.4)
for s in suppliers:
    print(s.display_name, s.country, s.daily_export_mbpd, s.risk_score)

# Crude grades compatible with a specific refinery
grades = await get_grade_specs("Jamnagar")
for g in grades:
    print(g.grade, g.api_gravity, g.sulfur_pct, g.compatibility)

# Corridors below risk threshold
routes = await get_routes(risk_max=0.5)
for r in routes:
    print(r.display_name, r.risk_score, r.h3_cells)
```

---

### 7. Reading SPR state (reserve_optim_agent)

```python
from knowledge.api.read import get_spr_state

caverns = await get_spr_state()
total_fill = sum(c.current_fill_mmt or 0 for c in caverns)
# India total capacity: 5.33 MMT (Vizag 1.33 + Mangaluru 1.50 + Padur 2.50)
```

---

### 8. Copilot and wiki (visualizer_agent)

```python
from knowledge.api.read import copilot_query, get_wiki_page

# EA-GraphRAG routed copilot
answer = await copilot_query("Why did the Hormuz risk score spike and which refineries are most exposed?")
print(answer.answer)      # Nova Pro synthesised prose
print(answer.citations)   # list of Graphiti episode UUIDs cited
print(answer.route)       # "vector" | "graph" — which search path was used
print(answer.latency_ms)  # ~380ms (vector) or ~1,800ms (graph)

# Narrative wiki page (shown on node click in the map)
page = await get_wiki_page("Strait of Hormuz")
print(page.content)        # Markdown prose from /wiki store
print(page.last_updated)
```

---

### 9. Sandbox / speculative lifecycle

```python
# sandbox.py — write a speculative PendingScenario (NEVER write_risk_state here)
from knowledge.api.write import write_pending, promote_pending

ref = await write_pending(
    confidence=0.73,
    projected_crossing_hours=18.0,
    scenario_ref="sandbox-abc12345",
    entity="Strait of Hormuz",
)

# When the monitor confirms a real crossing, promote it
episode = await promote_pending("sandbox-abc12345")
# This flips status → promoted and hooks into the feedback loop
```

---

### 10. Adding a new agent — checklist

1. **Do not import** `graphiti_core`, `falkordb`, `knowledge.connection`, or `knowledge.triage` — only `knowledge/api/read.py` and `knowledge/api/write.py`.
2. Call `await kb_init()` once in your container startup before any KB call.
3. If your agent **writes** a new output type, add a `write_<type>()` function to `knowledge/api/write.py` and a matching typed model to `contracts/outputs.py`. Don't call `add_episode()` directly.
4. If your agent **reads** a new view, add a `get_<thing>()` function to `knowledge/api/read.py` and a typed `*View` model. Don't return raw Graphiti objects.
5. All new entity types go in `knowledge/schema/entities.py` (update `ENTITY_TYPES` dict). All new edge types go in `knowledge/schema/edges.py` (update `EDGE_TYPES` and `EDGE_TYPE_MAP`). Bump `SCHEMA_VERSION` on breaking changes.
6. Check the import boundary in `CLAUDE.md` before submitting — `ruff` will not catch cross-module leakage.

---

## Per-System Knowledge Base Integration Guide

This section is the complete contract for each of the five systems: what data they receive from the KB, what data the KB expects from them, and how to wire the integration. The KB is the only shared state — no system talks to another system directly.

---

### System 1 — Geopolitical Risk Intelligence Agent (Sense)

**Role in the pipeline:** the only system that **writes raw signals**. Everything else reads. System 1 is a pure producer.

**What System 1 reads FROM the KB at startup:**
```python
from knowledge.api.read import get_risk_scores, get_subgraph

# Load which entities are currently tracked (to know which H3 cells / corridors to monitor)
scores = await get_risk_scores()
for view in scores:
    # view.entity      → entity display name (e.g. "Strait of Hormuz")
    # view.score       → current fused risk 0–1
    # view.band        → "calm" / "watch" / "elevated" / "action" / "critical"
    # view.valid_at    → when this risk state is true in the world (bitemporal)
    pass

# Optionally: pull entity metadata (H3 cells to watch, sanctioned suppliers)
subgraph = await get_subgraph("Strait of Hormuz", hops=1)
# subgraph.nodes[n]["attributes"]["h3_cells"] → list of H3 cell IDs for AIS monitoring
# subgraph.nodes[n]["attributes"]["sanctioned"] → True/False for supplier nodes
```

**What System 1 writes TO the KB (per sub-agent):**

All four sub-agents push a `NormalizedSignal` to the Redis queue. The KB consumer handles everything from there — sub-agents never call `ingest_signal()` or `write_risk_state()` directly.

```python
from contracts.signal import NormalizedSignal
from knowledge.ingest_queue import push_signal
import asyncio

# AIS sub-agent — dark vessel / anomalous gap
signal = NormalizedSignal(
    signal_id="ais-20260228-001",        # ULID or UUID, unique per signal
    source="ais",
    observed_at=datetime.now(timezone.utc),   # when true in the world
    ingested_at=datetime.now(timezone.utc),
    priority_hint="HIGH",
    force_synthesis=True,                # dark vessel → bypass triage cosine gate
    entity_refs=["Strait of Hormuz", "MT Destiny"],   # display names of affected entities
    h3_cells=["8526800bfffffff"],        # H3 cell IDs (optional, AIS-specific)
    summary="MT Destiny went AIS-dark near Larak Island — 6h gap, SAR confirmed",
    payload={
        "mmsi": "123456789",
        "dark_vessel": True,
        "anomaly_score": 0.92,
        "gap_hours": 6.0,
        "sar_confirmed": True,
    },
)
await push_signal(signal)

# GDELT / news sub-agent — extracted event
signal = NormalizedSignal(
    signal_id="gdelt-20260228-002",
    source="gdelt",
    observed_at=event_timestamp,
    ingested_at=datetime.now(timezone.utc),
    priority_hint="MED",
    force_synthesis=False,               # goes through triage cosine gate
    entity_refs=["Strait of Hormuz", "IRGC"],
    summary="IRGC announced live-fire naval drills in the Strait of Hormuz",
    payload={
        "actor": "IRGC", "action": "military_exercise",
        "target": "Strait of Hormuz", "severity": 0.72,
        "gdelt_tone": -4.5, "article_url": "...",
    },
)
await push_signal(signal)

# Sanctions sub-agent — new SDN listing
signal = NormalizedSignal(
    signal_id="ofac-20260228-003",
    source="sanctions",
    observed_at=datetime.now(timezone.utc),
    ingested_at=datetime.now(timezone.utc),
    priority_hint="HIGH",
    force_synthesis=True,                # sanctions always bypass triage
    entity_refs=["NIOC", "MT Destiny"],
    summary="OFAC added NIOC subsidiary to SDN list",
    payload={
        "list_name": "OFAC_SDN", "entity_name": "NIOC Trading Ltd",
        "effective_date": "2026-02-28", "vessel_mmsi": "123456789",
    },
)
await push_signal(signal)

# Prices sub-agent — BOCD changepoint
signal = NormalizedSignal(
    signal_id="price-20260228-004",
    source="price",
    observed_at=datetime.now(timezone.utc),
    ingested_at=datetime.now(timezone.utc),
    priority_hint="HIGH",
    force_synthesis=True,                # BOCD breakpoint → bypass triage
    entity_refs=["Brent crude"],
    summary="Brent crude BOCD breakpoint: +$8.20/bbl in 4 hours, war-risk premium spike",
    payload={
        "price_usd": 96.40, "price_delta": 8.20, "bocd_probability": 0.94,
        "regime": "stressed", "war_risk_premium_proxy": 0.61,
    },
)
await push_signal(signal)
```

**After fusion aggregation (30-second window):** write the fused risk state directly.

```python
from knowledge.api.write import write_risk_state

await write_risk_state(
    entity="Strait of Hormuz",
    score=0.73,                    # fused 0–1 score
    factor_ais=0.41,               # AIS / dark-vessel contribution
    factor_gdelt=0.55,             # news / GDELT tone contribution
    factor_price=0.30,             # price / war-risk-premium contribution
    factor_sanctions=0.00,
    rationale="3 dark-vessel gaps + BOCD price breakpoint",
    model_version="gbm-platt-v1.0",
    observed_at=datetime.now(timezone.utc),
)
# This creates / updates the RISK_STATE edge on the entity node.
# The LangGraph monitor picks it up within 30s. NEVER call this from sandbox.
```

**KB field expectations — what must be filled for correct graph behaviour:**
| Field | Required | Notes |
|---|---|---|
| `signal_id` | yes | Unique. Used as Graphiti episode name. |
| `source` | yes | Must be one of `"ais" "gdelt" "news" "sanctions" "price"`. |
| `observed_at` | yes | Graphiti reference_time — determines bitemporal validity window. |
| `entity_refs` | yes | Display names must match existing entity nodes or Graphiti will create new ones. Spell consistently. |
| `summary` | yes | One-line description. Becomes triage embedding input. |
| `force_synthesis=True` | for sanctions / BOCD | Bypasses 0.40 cosine similarity gate. |
| `priority_hint="HIGH"` | for dark vessels, sanctions, BOCD | Routes to synthesis, not just extraction. |

---

### System 2 — Disruption Scenario Modeller (Reason)

**Role:** triggered by the LangGraph sandbox or threshold monitor. Reads the supply-chain subgraph, runs ARIO/GNN, writes cascade results back.

**Trigger (automatic — no user action):**
```python
# orchestration/triggers.py fires this when risk band crosses "action" (score >= 0.70)
# OR when a PendingScenario is promoted from sandbox
from scenario_agent.runner import run_scenario
await run_scenario(trigger_entity="Strait of Hormuz", scenario_id="sc-20260228-001", status="confirmed")
```

**What System 2 reads FROM the KB:**
```python
from knowledge.api.read import get_subgraph, get_risk_scores

# Full 2-hop supply-chain subgraph around the disrupted entity
# Use this to initialise the ARIO IO matrix
subgraph = await get_subgraph("Strait of Hormuz", hops=2)

# subgraph.nodes → list of dicts:
#   {"uuid": "...", "display_name": "Jamnagar Refinery", "labels": ["Refinery"],
#    "attributes": {"inventory_days": 22.0, "throughput_capacity_mbpd": 1.24,
#                   "lat": 22.3, "lon": 70.1, "configured_grades": ["Arab Medium"]}}

# subgraph.edges → list of dicts:
#   {"uuid": "...", "source_uuid": "...", "target_uuid": "...",
#    "relation_type": "FEEDS", "fact": "Hormuz feeds Vadinar Port",
#    "attributes": {"throughput_share_pct": 42.0},
#    "valid_at": "2026-02-28T00:00:00Z", "invalid_at": null}

# Current risk scores to calibrate initial shock magnitude
scores = await get_risk_scores()
hormuz_score = next((s.score for s in scores if s.entity == "Strait of Hormuz"), 0.0)
```

**What System 2 writes TO the KB:**
```python
from knowledge.api.write import write_scenario
from contracts.outputs import ScenarioOutputData

result = await write_scenario(ScenarioOutputData(
    scenario_id="sc-20260228-001",          # matches trigger ID
    trigger_entity="Strait of Hormuz",
    status="confirmed",                      # "speculative" if from sandbox
    confidence=0.85,
    gap_mbpd=1.2,                           # supply gap in million barrels per day
    gap_duration_days=14.0,
    feedstock_gap_timeline=[1.1, 1.2, 1.3, 1.2, 1.1, 1.0, 0.9],  # day-by-day mbpd gap
    price_impact_low=8.0,                   # USD/bbl low estimate
    price_impact_high=22.0,                 # USD/bbl high estimate
    spr_depletion_days=6.5,                 # days until SPR below emergency threshold
    assumptions={
        "import_dependence_pct": {"value": 88.2, "unit": "%", "source": "PPAC 2025"},
        "hormuz_share_pct":      {"value": 42.0, "unit": "%", "source": "IEA 2025"},
        "spr_total_mmt":         {"value": 5.33, "unit": "MMT", "source": "MoPNG 2025"},
    },
))
# result.episode_uuid — pass this as scenario_ref to Systems 3 and 4
```

**Node properties used by ARIO initialisation:**
| Property | Node type | Unit | Notes |
|---|---|---|---|
| `throughput_capacity_mbpd` | Refinery | mbpd | Max crude intake |
| `inventory_days` | Refinery | days | Current feedstock buffer |
| `throughput_share_pct` | FEEDS edge | % | How much of refinery supply transits this corridor |
| `daily_export_mbpd` | Supplier | mbpd | Supplier's export volume |
| `sanctioned` | Supplier | bool | Exclude from supply mix |
| `choke_severity` | Corridor | 0–1 | Severity of closure (1.0 = full blockage) |
| `risk_score` (RISK_STATE) | any | 0–1 | Current live risk on this node |

---

### System 3 — Adaptive Procurement Orchestrator (Act)

**Role:** triggered by a new `ScenarioOutputData` node in the graph. Queries available suppliers, compatible grades, and open routes. Runs RF/EOS grade matching + OR-Tools routing + TOPSIS ranking. Writes back a ranked procurement recommendation.

**Trigger (automatic):**
```python
# orchestration/triggers.py detects new ScenarioOutput and fires:
from alt_procurement_agent.runner import run_procurement
await run_procurement(scenario_id="sc-20260228-001")
```

**What System 3 reads FROM the KB (three targeted queries):**
```python
from knowledge.api.read import get_available_suppliers, get_grade_specs, get_routes

# Query 1 — suppliers with risk < 0.4, not sanctioned, not on any watch list
suppliers = await get_available_suppliers(risk_max=0.4)
for s in suppliers:
    # s.display_name         → "Saudi Aramco"
    # s.country              → "Saudi Arabia"
    # s.daily_export_mbpd    → 6.2
    # s.risk_score           → 0.18
    # s.sanctioned           → False
    # s.available_grades     → ["Arab Light", "Arab Medium", "Arab Heavy"]
    pass

# Query 2 — crude grade specs each affected refinery is configured for
grades = await get_grade_specs("Jamnagar Refinery")
for g in grades:
    # g.grade          → "Arab Medium"
    # g.api_gravity    → 29.0
    # g.sulfur_pct     → 2.60
    # g.compatibility  → 0.95   (CONFIGURED_FOR edge attribute)
    pass

# Query 3 — corridors below risk threshold (Yanbu automatically appears if Hormuz > 0.5)
routes = await get_routes(risk_max=0.5)
for r in routes:
    # r.display_name   → "Yanbu bypass pipeline"
    # r.risk_score     → 0.12
    # r.h3_cells       → ["..."]
    # r.transit_days   → 12.0
    pass
```

**What System 3 writes TO the KB:**
```python
from knowledge.api.write import write_procurement
from contracts.outputs import ProcurementRecData, ProcurementOption, ScoreBreakdown

await write_procurement(ProcurementRecData(
    scenario_id="sc-20260228-001",
    status="confirmed",              # "speculative" if from sandbox
    ranked=[
        ProcurementOption(
            supplier="Saudi Aramco",
            grade="Arab Light",
            route_via="Yanbu bypass pipeline",
            landed_cost_usd_bbl=85.30,
            lead_time_days=12.0,
            grade_compatibility=0.92,     # RF + Peng-Robinson EOS output
            corridor_risk=0.12,           # Yanbu route risk score at query time
            topsis_score=0.87,            # TOPSIS multi-objective composite
            score_breakdown=ScoreBreakdown(
                cost_score=0.78,
                lead_time_score=0.85,
                grade_compatibility_score=0.92,
                corridor_risk_score=0.88,
            ),
            rationale="Yanbu pipeline bypasses Hormuz entirely; 12-day lead time "
                      "within feedstock buffer; Arab Light within Jamnagar gravity envelope.",
        ),
        # ... more ranked options
    ],
))
```

**How the KB knows which suppliers are live vs. sanctioned:**
A supplier's `sanctioned` attribute is updated in real time by System 1's sanctions sub-agent. When `get_available_suppliers(risk_max=0.4)` is called, it queries FalkorDB with `WHERE n.sanctioned = false AND r.score < 0.4` — a supplier sanctioned 30 minutes ago is already excluded because SAGE updated its node when the OFAC signal arrived.

---

### System 4 — Strategic Reserve Optimisation Agent (Act)

**Role:** runs in parallel with System 3, triggered by the same `ScenarioOutput` node. Reads current SPR fill levels and the gap volume from the scenario. Solves the SDP/CMDP Bellman iteration and writes a day-by-day drawdown schedule.

**Trigger (automatic, parallel to System 3):**
```python
from reserve_optim_agent.runner import run_spr_optimisation
await run_spr_optimisation(scenario_id="sc-20260228-001")
```

**What System 4 reads FROM the KB:**
```python
from knowledge.api.read import get_spr_state, get_subgraph

# Current fill levels for all three SPR caverns
caverns = await get_spr_state()
for c in caverns:
    # c.display_name          → "Vizag SPR Cavern"
    # c.capacity_mmt          → 1.33
    # c.current_fill_mmt      → 1.21     (most recent fill level from episode history)
    # c.days_cover            → 8.7      (fill / daily_consumption)
    # c.fill_pct              → 0.91
    pass

total_fill_mmt = sum(c.current_fill_mmt or 0 for c in caverns)
# India total: ~5.33 MMT = ~9.5 days cover at normal consumption

# Read gap volume and duration from System 2's ScenarioOutput
subgraph = await get_subgraph("Strait of Hormuz", hops=1)
# Find ScenarioOutput node linked via AFFECTS_SCENARIO edge
# scenario_node["attributes"]["gap_mbpd"] → 1.2
# scenario_node["attributes"]["gap_duration_days"] → 14.0
# scenario_node["attributes"]["confidence"] → 0.85
```

**What System 4 writes TO the KB:**
```python
from knowledge.api.write import write_spr_schedule
from contracts.outputs import SPRScheduleData, SPRDay

await write_spr_schedule(SPRScheduleData(
    scenario_id="sc-20260228-001",
    status="confirmed",
    daily_plan=[
        SPRDay(
            day=1, action="draw", volume_mmt=0.18,
            reserve_after_mmt=5.15, days_cover_after=9.2,
            decision_driver="gap onset — begin draw at sustained rate",
        ),
        SPRDay(
            day=8, action="draw", volume_mmt=0.18,
            reserve_after_mmt=3.89, days_cover_after=6.9,
            decision_driver="mid-crisis: maintain draw, monitor procurement arrival",
        ),
        SPRDay(
            day=15, action="hold", volume_mmt=0.0,
            reserve_after_mmt=3.89, days_cover_after=6.9,
            decision_driver="procurement alternatives arrived — halt draw, begin replenishment planning",
        ),
    ],
    prob_above_buffer=0.96,         # P(reserve > 3-day buffer) across the plan
    constraint_satisfied=True,      # CMDP chance constraint met: P(reserve < 3 days) ≤ 0.05
    policy_memo=(
        "Draw at 0.18 MMT/day for 14 days; buffer maintained at >6.9 days cover throughout. "
        "Real-options analysis shows positive waiting value is exhausted by Day 3 — delay "
        "beyond Day 3 risks hitting the 5-day buffer floor. Replenishment window opens at Day 20 "
        "assuming procurement alternatives arrive by Day 15."
    ),
))
```

**State space used by SDP solver:**
| Dimension | Source | Range |
|---|---|---|
| Reserve level | `get_spr_state()` | 0 – 5.33 MMT |
| Market regime | `get_risk_scores()` band | `calm / watch / elevated / action / critical` |
| Current crude price | Latest price signal payload | USD/bbl |
| Day in crisis | Gap duration from ScenarioOutput | 0 – gap_duration_days |

---

### System 5 — Supply Chain Digital Twin (Visualize)

**Role:** pure consumer — reads everything, writes nothing. Renders the live KB state as a geospatial map, staged-alert panel, procurement results, SPR timeline, copilot, and pipeline status bar.

**What System 5 reads FROM the KB (continuous + on-demand):**

```python
from knowledge.api.read import (
    get_risk_scores,       # continuous — every 30s, feeds map node colours
    get_subgraph,          # on node click — populates detail panel
    copilot_query,         # on user question — EA-GraphRAG routed
    get_wiki_page,         # on node click — narrative prose panel
    get_available_suppliers,   # for procurement results panel
    get_spr_state,         # for SPR timeline panel
)

# 1. Map node risk colours — polled every 30s via FastAPI background task
scores = await get_risk_scores()
for view in scores:
    # view.entity          → "Strait of Hormuz"
    # view.score           → 0.73
    # view.band            → "action"   → render as red + pulsing glow
    # view.factors         → {"ais": 0.41, "gdelt": 0.55, "price": 0.30, "sanctions": 0.00}
    # view.valid_at        → ISO8601 timestamp (shown in tooltip)
    pass

# Risk band → UI colour mapping (from contracts/bands.py):
# "calm"     (<0.25)  → phosphor green
# "watch"    (0.25–0.45) → cyan
# "elevated" (0.45–0.70) → amber
# "action"   (0.70–0.90) → red
# "critical" (≥0.90)  → pulsing red

# 2. Node click → detail panel
subgraph = await get_subgraph("Strait of Hormuz", hops=2)
# Render subgraph.nodes as the connected-entities list
# Render subgraph.edges as arc lines between map markers

# 3. Node click → wiki prose panel (RETRIEVED, not generated)
page = await get_wiki_page("Strait of Hormuz")
# page.content       → full Markdown prose from /wiki store
# page.last_updated  → timestamp of last synthesis run
# Render as-is in the right panel

# 4. Copilot question (user-initiated — only human-triggered step)
answer = await copilot_query("Which refineries are most exposed to a Hormuz closure?")
# answer.answer      → Nova Pro synthesised prose (≤400 words)
# answer.citations   → list of Graphiti episode UUIDs — render as clickable sources
# answer.route       → "vector" (~380ms) or "graph" (~1,800ms)
# answer.latency_ms  → show in UI for transparency

# 5. PendingScenario staged alert — polled with risk scores
# get_risk_scores() also returns entries where band is from a PendingScenario node:
# view.status == "speculative" → show Staged Alert: "{confidence}% probability, crossing in {hours}h"
# view.status == "promoted"   → show confirmed threshold crossing, surface procurement/SPR panels

# 6. Procurement panel — shown after threshold crosses
suppliers = await get_available_suppliers(risk_max=0.4)
# Render as ranked table: supplier / grade / route / TOPSIS score / rationale

# 7. SPR timeline
caverns = await get_spr_state()
# Render as bar chart: current fill vs. capacity, days cover, drawdown plan overlay
```

**WebSocket push (LangGraph → frontend):**
The pipeline bar (`SENSE → TRIAGE → SAGE → SANDBOX → SCENARIO → PROCURE → RESERVE`) is driven by LangGraph state-change events, not KB polling. Wire it in `orchestration/graph.py`:

```python
# In each LangGraph node, emit a status event:
async def emit_pipeline_status(stage: str, status: str):
    # stage: "SENSE" | "TRIAGE" | "SAGE" | "SANDBOX" | "SCENARIO" | "PROCURE" | "RESERVE"
    # status: "waiting" | "processing" | "staged" | "done" | "error"
    await websocket_manager.broadcast({"stage": stage, "status": status})
```

**System 5 writes NOTHING to the KB. If you find yourself calling a write function from visualizer_agent, stop — it belongs in one of Systems 1–4.**

---

### Graph Extraction — Edge Hallucination Prevention

Nova Lite (Graphiti's extraction LLM) reads every episode body and tries to extract relationships. If the text contains structured key-value labels like `"Current risk score: 0.73"` or `"Factor breakdown: AIS 0.41"`, Nova Lite invents edge types — `HAS_RISK_SCORE`, `HAS_FACTOR_BREAKDOWN` — that are not in SAGE's schema. Graphiti then fails to resolve the target entity (a bare number like `0.73` has no entity node) and logs a warning, dropping the edge.

**This is fixed by design in both write paths:**

- `knowledge/api/write.py:write_risk_state()` — uses flowing prose: `"risk level is assessed at 0.73 out of 1.0 (action band)"` instead of `"Current risk score: 0.73"`.
- `knowledge/synthesis.py:RISK_STATE_TEMPLATE` — uses the same prose format, with matching instructions in `SYNTH_PROMPT` to never use `"Current risk score:"` or `"Factor breakdown:"` as labels.

The actual risk data is identical — it just reads as a sentence, not a key-value pair. The `RISK_STATE` edge (which IS in the schema) is still extracted correctly from the prose because it matches the typed edge definition, not a hallucinated label.

---

## Team Ownership

| Module | Owner |
|---|---|
| `contracts/`, `knowledge/`, `scenario_agent/`, `orchestration/sandbox.py`, `orchestration/monitor.py` | Tom |
| `sensory_agent/`, `knowledge/triage.py` | Teammate B |
| `alt_procurement_agent/`, `reserve_optim_agent/` | Teammate C |
| `visualizer_agent/`, `orchestration/graph.py` | Teammate D |

---

## Quick Start

```bash
# 1. Copy and fill in environment variables
cp .env.example .env   # set FALKORDB_PASSWORD, BEDROCK_*, AISSTREAM_API_KEY, EIA_API_KEY, NEWSAPI_KEY

# 2. Start infrastructure first
docker compose up falkordb redis -d

# 3. Run the Day-1 smoke test
python -c "from knowledge.connection import build_graphiti, bootstrap; import asyncio; asyncio.run(bootstrap(build_graphiti()))"

# 4. Start everything
docker compose up

# 5. Open FalkorDB browser to inspect the graph
open http://localhost:3000
```

---

## Design Specs

Full architectural documentation lives in `.claude/design/`:

- [`SAGE_Knowledge_Base_Spec.md`](.claude/design/SAGE_Knowledge_Base_Spec.md) — architecture narrative and build order
- [`SAGE_Schema_and_Contracts_Spec.md`](.claude/design/SAGE_Schema_and_Contracts_Spec.md) — normative schema, all 7 contracts, lock-in artifact
- [`SAGE_Knowledge_Base_Deployment.md`](.claude/design/SAGE_Knowledge_Base_Deployment.md) — infrastructure, cost breakdown, deployment guide

---

## Cost

~$6/day during development (spot EC2), ~$13/day demo week (on-demand). Total 4-week cost ~$197, effectively $0 with AWS new-account credits. See deployment spec §6 for full breakdown.
