<div align="center">

# SAGE — AI-Driven Energy Supply Chain Resilience

### Synthesis-first Agentic Graph-Enhanced knowledge architecture for India's crude oil import risk.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Graphiti](https://img.shields.io/badge/Graphiti-Core-6B46C1?style=flat-square)](https://github.com/getzep/graphiti)
[![FalkorDB](https://img.shields.io/badge/FalkorDB-Graph-DC143C?style=flat-square)](https://www.falkordb.com/)
[![Amazon Bedrock](https://img.shields.io/badge/Amazon%20Bedrock-Nova%20Pro-232F3E?style=flat-square&logo=amazonaws&logoColor=white)](https://aws.amazon.com/bedrock/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Autonomous%20Loop-1C3C3C?style=flat-square)](https://langchain-ai.github.io/langgraph/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

</div>

---

## What SAGE Does — In One Sentence

SAGE continuously ingests geopolitical and logistics signals from four always-on sensory sub-agents (AIS, news, sanctions, prices), synthesizes them into a bitemporal knowledge graph and a human-readable wiki store via a triage-gated Nova Pro pipeline, and autonomously triggers disruption modelling, procurement rerouting, and SPR drawdown recommendations — turning a reactive crisis response into a managed, anticipatory process with a 28× speedup from threshold crossing to ranked output.

---

## Table of Contents

1. [Why SAGE Stands Out](#why-sage-stands-out)
2. [Role in the SAGE System](#role-in-the-sage-system)
3. [Data Model](#data-model)
4. [Contracts](#contracts)
5. [System 1 — Sensory Agent Wiring Guide](#system-1--sensory-agent-wiring-guide)
6. [Tech Stack](#tech-stack)
7. [Getting Started](#getting-started)
8. [Team Ownership](#team-ownership)
9. [License](#license)

---

## Why SAGE Stands Out

| Property | Detail |
|---|---|
| **Synthesis-first ingest** | Raw signals never enter the vector store directly. Nova Pro reconciles every new signal against the current wiki page before `add_episode()` is called — the vector store holds synthesised, contradiction-resolved episodes, not raw facts. |
| **Anticipatory sandbox** | When risk crosses `elevated`, the sandbox forks a speculative future, runs the full ARIO cascade and procurement solver speculatively, and pre-stages results. When the crossing is confirmed, output appears in 300ms rather than 8,500ms (28× speedup). |
| **Bitemporal graph** | Every edge carries `observed_at` (when the event happened in the world) and `ingested_at` (when SAGE recorded it). `invalid_at IS NULL` = current fact. Old values are invalidated, never deleted. |
| **Source-aware triage** | AIS and price signals always route to `"extract"` (numeric, never prose). Sanctions always route to `"synthesize"`. News routes on cosine similarity. The routing decision is deterministic code, not an LLM call. |
| **Canonical entity registry** | 22 seed entities, 123 aliases, 11 H3 cells. Three lookup indices: alias → entity_id, H3 cell → entity_id, price instrument → [entity_id]. No duplicate graph nodes; alias resolution happens before any LLM is invoked. |
| **Obsidian-style second brain** | Every entity has a git-versioned Markdown wiki page with YAML frontmatter and `[[Canonical Name]]` wikilinks. Opens natively in Obsidian; also parsed by the geospatial renderer for ArcLayer edges. |
| **No-hallucination risk scores** | Risk scores are expressed as prose sentences only (`_RISK_SENTENCE_TEMPLATE`). The synthesis prompt explicitly bans `"Current risk score:"` labels — prevents Nova Lite from inventing schema-less edge types. |

---

## Role in the SAGE System

```
  sensory_agent/ (System 1)
  ├── ais.py          → AIS websocket, H3 indexing, dark-vessel detection
  ├── news.py         → GDELT + NewsAPI every 15 min; Nova Micro entity extraction
  ├── sanctions.py    → OFAC/EU/UN diff every 6h; force_synthesis=True always
  └── prices.py       → yfinance every 5 min; BOCD changepoint detection
           │  NormalizedSignal → Redis queue
           ▼
  knowledge/ingest_queue.py
  ├── fusion model (_FeatureVector, 17-dim)
  ├── triage gate (source-aware routing: extract / synthesize / store / drop)
  └── write_risk_state() every 30s flush
           │
           ▼
  ┌────────────────────────────────────────────┐
  │          SAGE Knowledge Base               │
  │  Store 1: episodic (Graphiti episodes)     │
  │  Store 2: semantic graph (FalkorDB nodes   │
  │           + edges + 1024-D embeddings)     │
  │  Store 3: /wiki (Markdown pages,           │
  │           YAML frontmatter, [[wikilinks]]) │
  └───────────────────┬────────────────────────┘
                      │  typed read API only
     ┌────────────────┼────────────────┐
     ▼                ▼                ▼
  scenario_agent/  alt_procurement/  reserve_optim/
  (ARIO cascade)   (OR-Tools MILP)   (Bellman SDP)
                      │
                      ▼
                visualizer_agent/
                (FastAPI + deck.gl digital twin)
                      │
                      ▲
           orchestration/ (LangGraph)
           monitor → sandbox → triggers
           SENSE→TRIAGE→SAGE→SANDBOX→SCENARIO→PROCURE→RESERVE
```

The knowledge base is the single source of truth — System 1 is the sole writer of raw signals; Systems 2–5 are pure consumers via `knowledge/api/read.py`. No agent imports `graphiti_core`, `falkordb`, or any `knowledge/` internal directly.

---

## Data Model

### Three Stores

| Store | What | Where | Written by |
|---|---|---|---|
| **Episodic** | Every synthesised episode node with body text + `reference_time`. Non-lossy provenance ledger. | FalkorDB (Graphiti-managed) | `add_episode()` only |
| **Semantic graph** | Typed entity nodes + typed edges + 1024-D embeddings + bitemporal validity windows (`valid_at` / `invalid_at`). | FalkorDB (Graphiti-managed) | `add_episode()` only |
| **/wiki store** | One Markdown file per entity. YAML frontmatter + `[[Canonical Name]]` wikilinks + `links_out` list. Git-versioned. | `knowledge/wiki/` | `write_wiki_page()` only, after `add_episode()` succeeds |

### Entity Types

| Type | Count | Examples |
|---|---|---|
| `Corridor` | 4 | Strait of Hormuz, Bab-el-Mandeb, Suez Canal, Strait of Malacca |
| `Supplier` | 5 | Saudi Aramco, NIOC, ADNOC, Rosneft, Iraqi Oil Ministry |
| `Refinery` | 3 | Jamnagar Refinery, Mangaluru, Paradip |
| `Port` | 4 | Vadinar, Yanbu, Sikka, Fujairah |
| `SPRCavern` | 3 | Vizag SPR, Mangaluru SPR, Padur SPR |
| `Authority` | 3 | OFAC, EU, UN |
| `Vessel` | dynamic | registered at runtime via `register_vessel()` |
| `GeoEvent` | dynamic | `[[AIS Anomaly — Larak Cluster]]`, `[[2019 Tanker Attacks]]` |
| `PendingScenario` | dynamic | speculative futures from sandbox |
| `ScenarioOutput` | dynamic | ARIO results |
| `CrudeGrade` | static | Arab Light, Basra Heavy, etc. |

### Edge Types

| Edge | From → To | Key Attributes |
|---|---|---|
| `RISK_STATE` | Corridor / Supplier / Refinery → itself | `score`, `band`, `factor_ais`, `factor_gdelt`, `factor_price`, `factor_sanctions`, `rationale` |
| `EXPORTS_VIA` | Supplier → Corridor | `daily_export_mbpd`, `throughput_share_pct` |
| `FEEDS` | Corridor → Refinery / Port | `throughput_share_pct` |
| `SUPPLIES` | Supplier → Refinery | `grade`, `daily_export_mbpd` |
| `CONFIGURED_FOR` | Refinery → CrudeGrade | `compatibility_score`, `gravity_range_api` |
| `SANCTIONED_BY` | Vessel / Supplier → Authority | `effective_date`, `list_name` |
| `BYPASS_ROUTE` | Corridor → Corridor | `capacity_mbpd`, `lead_time_days` |
| `FEEDS_RESERVE` | Supplier / Port → SPRCavern | `fill_rate_mmt_day` |
| `AFFECTS_SCENARIO` | Corridor → ScenarioOutput | `gap_mbpd`, `confidence` |

### Wiki Frontmatter Schema

```yaml
---
entity_id:       corridor_hormuz
entity_type:     Corridor
risk_score:      0.67
risk_band:       elevated
factors:
  ais:           0.80
  gdelt:         0.55
  price:         0.60
  sanctions:     0.20
last_updated:    2026-02-26T14:32:00Z
valid_at:        2026-02-26T14:00:00Z
source_episodes: []
coordinates:     {lat: 26.5, lon: 56.4}
links_out:       [supplier_aramco, refinery_jamnagar, port_vadinar]
---
```

---

## Contracts

All inter-agent contracts live in `contracts/` and import nothing from the rest of the codebase — they are pure Pydantic schema. This is the strict boundary that allows every system to be built in parallel without coupling.

**`NormalizedSignal`** (`contracts/signal.py`) is System 1's only output type. It carries the signal source, timestamps (both `observed_at` for when the event happened in the world and `ingested_at` for when the sub-agent emitted it), `entity_refs` (canonical display names from the registry), a one-line `summary` that becomes the triage embedding input, `force_synthesis` to bypass the similarity gate, and a `payload` dict for source-specific fields. Every sub-agent emits this type; the KB consumer accepts nothing else.

**`ScenarioOutputData`** (`contracts/outputs.py`) is System 2's output. It encodes the ARIO disruption model result: supply gap in mbpd, gap duration, day-by-day feedstock gap timeline, price impact bounds, SPR depletion projection, and a `status` field (`"speculative"` when produced by the sandbox, `"confirmed"` when produced from a live crossing). Systems 3 and 4 read this to scope their work.

**`ProcurementRecData`** (`contracts/outputs.py`) is System 3's output. It contains a TOPSIS-ranked list of alternative procurement options, each with supplier, grade, corridor, landed cost, lead time, grade compatibility score, and rationale. System 5 renders this directly in the copilot recommendations panel.

**`SPRScheduleData`** (`contracts/outputs.py`) is System 4's output. It encodes a day-by-day draw/hold/refill plan for India's three SPR caverns, the probability the buffer constraint is satisfied, and a policy memo for the System 5 copilot to cite.

**`contracts/bands.py`** defines the five risk bands (`calm · watch · elevated · action · critical`) and their score thresholds. The orchestration monitor, the triage gate, and the UI colour mapping all import from this single source — changing a threshold here propagates everywhere automatically.

The contracts are the freeze boundary. If any field name changes after System 1 and System 2 are both in development, serialization breaks silently at runtime. Treat `contracts/` as append-only once two or more systems depend on it.

---

## System 1 — Sensory Agent Wiring Guide

System 1 is the **sole producer** of raw signals. Sub-agents push `NormalizedSignal` onto the Redis queue via `push_signal()` — they never call `ingest_signal()` or `write_risk_state()` directly.

### Entity Resolution

Before emitting any signal, populate `entity_refs` with canonical display names from the entity registry. Wrong names create duplicate graph nodes.

```python
from knowledge.registry import resolve_h3, resolve_instrument, resolve_name, canonical_name

# AIS: H3 cell → entity
entity_id = resolve_h3("8a2a1072b59ffff")       # → "corridor_hormuz"
display    = canonical_name(entity_id)            # → "Strait of Hormuz"

# Price: ticker → entities
entity_ids = resolve_instrument("BZ=F")           # → ["corridor_hormuz", "corridor_bab_el_mandeb"]
displays   = [canonical_name(eid) for eid in entity_ids]

# Sanctions / News: free-form name → entity
entity_id = resolve_name("Hormuz Strait")         # → "corridor_hormuz"  (alias lookup)
display    = canonical_name(entity_id)            # → "Strait of Hormuz"
```

**Canonical names — all 22 tracked entities:**

| Category | Canonical names |
|---|---|
| Corridors | `"Strait of Hormuz"`, `"Bab-el-Mandeb"`, `"Suez Canal"`, `"Strait of Malacca"` |
| Suppliers | `"Saudi Aramco"`, `"NIOC"`, `"ADNOC"`, `"Rosneft"`, `"Iraqi Oil Ministry"` |
| Refineries | `"Jamnagar Refinery"`, `"Mangaluru"`, `"Paradip"` |
| Ports | `"Vadinar"`, `"Yanbu"`, `"Sikka"`, `"Fujairah"` |
| SPR sites | `"Vizag SPR"`, `"Mangaluru SPR"`, `"Padur SPR"` |
| Authorities | `"OFAC"`, `"EU"`, `"UN"` |

### Sub-Agent Rules

| Sub-agent | Push trigger | `force_synthesis` | Frequency |
|---|---|---|---|
| **AIS** | Anomaly cluster detected (gap > 4h or dark vessels); NEVER per position ping | Always `False` | 0–10/hr normal, up to 50/hr during crisis |
| **News** | Per article, after Nova Micro finds ≥1 resolved entity; discard unresolved | Always `False` | 0–20 per 15-min cycle |
| **Sanctions** | Immediately on any diff (add or remove); both adds and removals matter | Always `True` | 0–5 per 6h cycle; up to 20+ during burst |
| **Price** | BOCD changepoint or sustained regime shift only; normal ticks never pushed | Always `False` | 0–3/day calm; up to 15/day crisis |

**New vessels (sanctions sub-agent):** call `register_vessel(mmsi, name)` before `push_signal()` so the new entity resolves correctly in the next news article.

### `_FeatureVector` — Fusion Model Interface

```python
@dataclass
class _FeatureVector:
    ais_gap_count_24h:          float   # AIS gaps > 4h in last 24h
    ais_dark_vessel_count:      float
    ais_anomaly_score_max:      float   # max HABIT score (0..1)
    ais_gap_duration_max_h:     float
    ais_monitored_cell_pct:     float   # % of tracked H3 cells with activity
    ais_velocity_std:           float
    gdelt_tone_24h_mean:        float   # negative = hostile
    gdelt_tone_delta:           float
    news_severity_max:          float   # 0..1
    news_event_count_24h:       float   # count of severity > 0.7 events
    price_brent_pct_change_24h: float
    price_bocd_flag:            float   # 1.0 if BOCD breakpoint detected
    price_regime:               float   # 1.0 if regime = stressed
    price_war_risk_premium:     float   # 0..1
    sanctions_new_additions_24h: float
    sanctions_vessel_count:     float
    sanctions_major_entity:     float   # 1.0 if major state entity sanctioned
```

### Build Checklist

- [ ] Sub-agent calls only `push_signal()` — never `ingest_signal()` or `write_risk_state()`
- [ ] AIS: `resolve_h3()` → `canonical_name()` for `entity_refs`; push per anomaly cluster, never per ping
- [ ] Price: `resolve_instrument()` → `canonical_name()`; push only on BOCD changepoint or regime shift
- [ ] Sanctions: `resolve_name()` → `register_vessel()` for new MMSI before push; `force_synthesis=True` always
- [ ] News: Nova Micro extraction → `resolve_name()` for each candidate → discard unresolved
- [ ] `observed_at` = when the event happened in the world, not when your sub-agent detected it
- [ ] `signal_id` = ULID or UUID, unique per emission
- [ ] `raw_ref` = S3 key or DB ID of verbatim raw record
- [ ] Container calls `await kb_init()` before the first `push_signal()`

---

## Tech Stack

| Layer | Technology | Role |
|---|---|---|
| Graph database | FalkorDB | Stores Graphiti episodic nodes, typed edges, embeddings |
| Knowledge graph | `graphiti-core[falkordb]` | Bitemporal episode management, semantic search, entity extraction |
| LLM (synthesis) | Amazon Bedrock — Nova Pro | Wiki reconciliation, contradiction resolution, wikilink generation |
| LLM (extraction) | Amazon Bedrock — Nova Micro | Entity name extraction from news articles (low-cost, high-frequency) |
| LLM (copilot) | Amazon Bedrock — Nova Pro | EA-GraphRAG copilot queries from System 5 |
| Embeddings | Amazon Bedrock — Titan Embed v2 | 1024-D episode and entity embeddings |
| Orchestration | LangGraph | Autonomous pipeline loop: SENSE→TRIAGE→SAGE→SANDBOX→SCENARIO→PROCURE→RESERVE |
| Disruption model | Custom ARIO (Hallegatte 2008) | Day-by-day IO cascade; PyTorch GraphSAGE surrogate (<150ms) |
| Procurement solver | OR-Tools MILP | Alternative supplier routing under corridor constraints |
| Reserve optimisation | Bellman SDP + real-options | Optimal SPR drawdown schedule under uncertainty |
| Queue | Redis | Sensory agent → ingest queue; decouples sub-agents from KB consumer |
| API gateway | FastAPI + WebSocket | Risk score push, copilot, wiki endpoints for System 5 frontend |
| Frontend | React + deck.gl | Geospatial H3 heatmap, ArcLayer edges, pipeline bar, copilot panel |
| Geospatial indexing | H3 (Uber) | res-10 cell indexing for AIS anomaly clustering and dedup |
| Language | Python 3.11+ | All backend systems |
| Schema | Pydantic v2 | All inter-agent contracts; validated at system boundaries |
| Wiki format | Markdown + YAML frontmatter | `[[wikilinks]]`, `links_out` frontmatter; Obsidian-native |

---

## Getting Started

### Prerequisites

- Python 3.11+
- Docker + Docker Compose
- AWS CLI configured for the `vigia-developer` account (`203800220566`), region `us-east-1`
- The following API keys available before starting:

| Key | Used by |
|---|---|
| `AISSTREAM_API_KEY` | sensory_agent/ais.py |
| `EIA_API_KEY` | sensory_agent/prices.py |
| `NEWSAPI_KEY` | sensory_agent/news.py |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Amazon Bedrock (Nova Pro, Titan Embed) |
| `FALKORDB_PASSWORD` | knowledge/connection.py |
| `REDIS_URL` | knowledge/ingest_queue.py |

### Install

```bash
pip install -e ".[dev]"
```

### Environment Variables

```bash
cp .env.example .env
# Fill in: FALKORDB_PASSWORD, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
#          AWS_REGION, AISSTREAM_API_KEY, EIA_API_KEY, NEWSAPI_KEY, REDIS_URL
```

| Variable | Default | Purpose |
|---|---|---|
| `DEMO_MODE` | `false` | `true` replays `demo_cache/` instead of hitting live APIs |
| `AWS_REGION` | `us-east-1` | Bedrock region |
| `FUSION_FLUSH_INTERVAL_S` | `30` | Seconds between `write_risk_state()` flushes |

### Start Infrastructure

```bash
docker compose up falkordb redis -d
```

### Smoke Test

```bash
python3.11 -c "
from knowledge.connection import init
from knowledge.registry import REGISTRY, resolve_h3, canonical_name
import asyncio
asyncio.run(init())
print('Registry:', len(REGISTRY), 'entities')
print('Hormuz H3 lookup:', canonical_name(resolve_h3('8a2a1072b59ffff')))
"
# Expected: Registry: 22 entities
#           Hormuz H3 lookup: Strait of Hormuz
```

### Start Everything

```bash
docker compose up
```

### Demo Mode (no live API keys needed)

```bash
DEMO_MODE=true docker compose up
# Replays pre-recorded Feb 23–28 2026 Hormuz closure timeline from demo_cache/
```

### One-Time KB Init (all containers)

```python
from knowledge.connection import init as kb_init
await kb_init()   # idempotent — call once at container boot before any KB call
```

---

## Team Ownership

| Module | Owner |
|---|---|
| `contracts/`, `knowledge/`, `orchestration/sandbox.py`, `orchestration/monitor.py` | Tom |
| `sensory_agent/`, `knowledge/triage.py`, `knowledge/ingest_queue.py` | Teammate B |
| `alt_procurement_agent/`, `reserve_optim_agent/` | Teammate C |
| `visualizer_agent/`, `orchestration/graph.py` | Teammate D |
| `scenario_agent/` | Tom + Teammate B |

---

## License

MIT License — Copyright © 2026 Tom Mathew
