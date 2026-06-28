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
