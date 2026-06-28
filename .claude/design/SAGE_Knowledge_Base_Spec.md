# SAGE Knowledge Base — Build Specification

**Project:** SAGE · Problem Statement 2 (AI-Driven Energy Supply Chain Resilience)
**SAGE =** **S**ynthesis-first **A**gentic **G**raph-**E**nhanced knowledge architecture
**Owner:** Knowledge Layer
**Stack:** Graphiti + FalkorDB + SAGE coordination layer

> **Scope.** This spec covers **only the knowledge layer**: Graphiti configuration, the domain ontology (entity + edge types), the narrative synthesis layer, the risk-score edge contract, and the read/write APIs that Systems 1–5 depend on. The sensing models, scenario models, and UI are out of scope — they are *consumers* of this layer.
>
> **Companion document.** This file is the *narrative build guide* (the "why" and the build order). The **normative, lock-in artifact** — the exact, copy-pasteable Pydantic models, JSON contracts, and API signatures that the whole team codes against — lives in **[`SAGE_Schema_and_Contracts_Spec.md`](./SAGE_Schema_and_Contracts_Spec.md)**. Where the two ever disagree, the schema & contracts spec wins.

---

## 1. Architecture — Two Layers

The knowledge base is **two layers**. Graphiti is the substrate you *configure and compose*. The SAGE coordination layer is what you *build* on top.

### 1.1 Layer 1 — Graphiti (composed, not built)

Graphiti handles, out of the box, everything below. You configure it; you do not implement it:

- **Episodic store** — every ingested signal preserved as an Episode node, non-lossy, with provenance via `MENTIONS` edges to extracted entities.
- **Typed entity graph** — entities and relationships as nodes and edges, classified by your custom Pydantic types.
- **Embeddings** — every node and edge embedded; hybrid semantic + BM25 + graph search built in.
- **Bitemporal facts** — every fact carries `valid_at` (when true in world) and `created_at` (when recorded). Facts are *invalidated, never deleted*.
- **Incremental updates** — new episodes integrate immediately, no batch recomputation.

### 1.2 Layer 2 — SAGE coordination (you build this)

Everything Graphiti does not do. This is your engineering surface:

- **Triage gate** — scores each incoming signal HIGH/MED/LOW, decides whether full synthesis runs.
- **Narrative synthesis agent** — loads current entity state, reconciles new signal against it, writes a coherent `/wiki` page, then hands the synthesized text to Graphiti.
- **Risk-score handoff** — receives the computed risk score from System 1, writes it as a structured edge property with factor breakdown.
- **Write orchestration** — keeps the `/wiki` narrative store and Graphiti consistent; one write path, no divergence.
- **Read API wrappers** — typed query functions Systems 2–5 call, so they never touch raw Graphiti search directly.

> **🔑 Key rule.** You write to Graphiti through **synthesized episodes, never raw signals**. The text handed to `add_episode()` is the reconciled assessment — so embeddings and extracted facts capture *synthesized understanding*, not isolated raw data. This is the entire reason the narrative layer sits above Graphiti.

---

## 2. Environment & Stack

### 2.1 Versions (verified)

| Component | Version / choice | Notes |
|---|---|---|
| `graphiti-core` | `pip install graphiti-core[falkordb]` | FalkorDB extra bundles the backend driver |
| FalkorDB | 1.1.2+ (Docker) | Redis-based graph DB; ~500× faster p99 subgraph vs Neo4j |
| Python | 3.11+ | 3.12+ only if using `falkordblite` embedded |
| LLM (extraction) | Bedrock Nova Pro | Graphiti needs structured-output-capable model; Nova Pro supports it |
| Embeddings | Titan Text v2 or BGE-m3 | Configure via Graphiti embedder client |
| LangGraph | latest | Orchestration — triage + monitor; your layer exposes hooks |

> **⚠️ Critical.** Graphiti depends on structured JSON output for entity extraction. It works best with OpenAI / Anthropic / Gemini / Nova Pro. **Do NOT use a tiny local model** for Graphiti's extraction LLM — small models emit malformed JSON and cause ingestion failures. If you must run local, use `json_object` mode and the largest model your hardware runs.

### 2.2 Start FalkorDB

```bash
docker run -p 6379:6379 -p 3000:3000 -it --rm \
  falkordb/falkordb:latest

# FalkorDB browser UI on :3000 — use it to inspect the graph visually
```

### 2.3 Initialise Graphiti

> **⚠️ API corrected (Graphiti ≥ 0.17).** The connection is no longer made via a `uri=` / `graph_name=` string on the `Graphiti` constructor. You **instantiate a `FalkorDriver`** and pass it as `graph_driver`. See the [schema & contracts spec](./SAGE_Schema_and_Contracts_Spec.md) §2 for the locked connection contract.

```python
from graphiti_core import Graphiti
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.nodes import EpisodeType

falkor = FalkorDriver(
    host='localhost', port=6379,
    username=None, password=FALKORDB_PASSWORD,
    database='sage',          # the multi-tenant graph name; must be non-None
)
graphiti = Graphiti(graph_driver=falkor)

# one-time: build indices and constraints
await graphiti.build_indices_and_constraints()
```

---

## 3. Domain Ontology — Entity Types

Defined as Pydantic models, passed to `add_episode()`. Graphiti extracts text, classifies entities against these types, validates, and populates custom attributes.

> **Reserved attribute names you CANNOT use:** `uuid`, `name`, `group_id`, `labels`, `created_at`, `summary`, `attributes`, `name_embedding`.

### 3.1 The nine entity types

| Entity type | Key custom attributes | Example |
|---|---|---|
| `Corridor` | `throughput_mbpd`, `choke_severity`, `h3_cells` | Strait of Hormuz |
| `Supplier` | `country`, `daily_export_mbpd`, `sanctioned` (bool) | Saudi Aramco, NIOC |
| `Refinery` | `capacity_mbpd`, `inventory_days`, `location_lat/lon` | Jamnagar, Mangaluru |
| `CrudeGrade` | `api_gravity`, `sulfur_pct`, `origin` | Arab Medium Sour |
| `Port` | `location_lat/lon`, `draft_m`, `congestion` | Vadinar, Yanbu |
| `SPRCavern` | `capacity_mmt`, `current_fill_mmt`, `location` | Vizag, Padur |
| `Vessel` | `dwt`, `flag`, `operator`, `sanctioned` (bool) | MT Destiny |
| `GeoEvent` | `actor`, `action`, `severity`, `event_time` | IRGC exercise |
| `PendingScenario` | `confidence`, `projected_crossing`, `status` | sandbox output |

### 3.2 Example Pydantic definition

```python
from pydantic import BaseModel, Field

class Corridor(BaseModel):
    '''A maritime chokepoint or shipping lane through which
    crude oil transits. Risk-bearing transit node.'''
    throughput_mbpd: float = Field(...,
        description='Current daily throughput, million bbl/day')
    choke_severity: float = Field(...,
        description='Structural importance 0-1, e.g. Hormuz=0.95')
    h3_cells: list[str] = Field(default_factory=list,
        description='H3 cell IDs covering this corridor')

class Refinery(BaseModel):
    '''An oil refinery that processes specific crude grades.'''
    capacity_mbpd: float = Field(..., description='Refining capacity')
    inventory_days: float = Field(...,
        description='Days of crude inventory on hand')
    location_lat: float = Field(..., description='Latitude')
    location_lon: float = Field(..., description='Longitude')
```

> **💡 Why explicit types.** Without custom types, Graphiti's LLM extraction invents entity labels from text — "Strait of Hormuz", "Hormuz Strait", "the Strait" become separate nodes. Custom types + clear docstrings constrain extraction to your ontology and dramatically cut duplicates. **The docstring and Field descriptions are READ BY THE LLM during extraction — write them carefully.**

---

## 4. Domain Ontology — Edge Types

Edge types are also Pydantic models, with an entity-pair mapping telling Graphiti which edge types are valid between which node types. Unmapped pairs fall back to a generic `RELATES_TO`.

### 4.1 The core edges

| Edge type | From → To | Carries |
|---|---|---|
| `EXPORTS_VIA` | Supplier → Corridor | `volume_mbpd` |
| `FEEDS` | Corridor → Port | — |
| `SUPPLIES` | Port → Refinery | — |
| `CONFIGURED_FOR` | Refinery → CrudeGrade | `yield_pct`, `compatibility` |
| `RISK_STATE` | (any) → RiskAssessment | `score`, `factors` (see §5) |
| `SANCTIONED_BY` | Vessel/Supplier → Authority | `list`, `date` |
| `BYPASS_ROUTE` | Supplier → Port | `cost_premium`, `added_days` |
| `FEEDS_RESERVE` | Refinery → SPRCavern | — |

### 4.2 Edge definition + mapping

```python
class RiskState(BaseModel):
    '''Current risk assessment for an entity, with the
    factor breakdown that produced the score.'''
    score: float = Field(..., description='Fused risk 0-1')
    factor_ais: float = Field(0, description='AIS contribution')
    factor_gdelt: float = Field(0, description='News tone contribution')
    factor_price: float = Field(0, description='Price stress contribution')
    factor_sanctions: float = Field(0, description='Sanctions contribution')

# entity-pair → allowed edge types
edge_type_map = {
    ('Supplier','Corridor'): ['EXPORTS_VIA'],
    ('Corridor','Port'): ['FEEDS'],
    ('Refinery','CrudeGrade'): ['CONFIGURED_FOR'],
    # ... etc
}
```

---

## 5. The Risk-Score Edge Contract

> **⭐ Most important section.** This is the contract System 1 writes to and the LangGraph monitor reads from. Get this exactly right — it is the interface the autonomous loop runs on. **Lock it in Week 1.**

### 5.1 Who computes, who stores, who reads

| Step | Component | Responsibility |
|---|---|---|
| Compute | System 1 fusion | Produces score + factor breakdown from signals. **NOT the KB's job.** |
| Store | SAGE (your layer) | Writes score as `RISK_STATE` edge property with `valid_at` timestamp. |
| Read | LangGraph monitor | Polls `RISK_STATE` edges every 30s; fires pipeline on threshold. |
| Read | Systems 2–5 | Read current score for context, display, scenario input. |

**The knowledge base never computes a risk score.** It stores what System 1 computes, and serves it to readers. This separation is a strength — state of truth in the graph, scoring logic in System 1, triggering policy in LangGraph.

### 5.2 How SAGE writes the score

During synthesis, after System 1 hands you the score, embed it in the episode text **and** set it as a structured fact. Because Graphiti extracts facts from episode text, state the score explicitly in the synthesized narrative, then rely on the `RiskState` edge type to capture it structurally:

```python
episode_text = f'''
Strait of Hormuz — risk assessment {now}.
Current risk score: {score:.2f} (ELEVATED).
Factor breakdown: AIS anomalies {f_ais:.2f}, GDELT tone
{f_gdelt:.2f}, war-risk premium {f_price:.2f}, sanctions
{f_sanc:.2f}. {narrative_synthesis_prose}
'''

await graphiti.add_episode(
    name=f'hormuz_risk_{now_iso}',
    episode_body=episode_text,
    source=EpisodeType.text,
    source_description='SAGE synthesis',
    reference_time=valid_at,   # bitemporal: when true in world
    entity_types={'Corridor': Corridor, 'Refinery': Refinery, ...},
    edge_types={'RISK_STATE': RiskState, ...},
    edge_type_map=edge_type_map,
)
```

### 5.3 How the monitor reads it

```python
# LangGraph monitor — every 30s
facts = await graphiti.search(
    query='current risk score corridor refinery',
    num_results=20,
)
# filter RISK_STATE edges, compare score vs thresholds
for f in facts:
    if f.score > 0.7 and f.entity not in already_fired:
        trigger_scenario(f.entity)        # action band
    elif f.score > 0.45 and rising_fast(f):
        fork_sandbox(f.entity)            # anticipatory band
```

### 5.4 Threshold bands

| Band | Level | Fires |
|---|---|---|
| Synthesis | triage HIGH | Narrative synthesis runs (pre-score) |
| Sandbox | projected > action | Speculative fork, pre-stage Systems 3+4 |
| Action | `score > 0.70` | System 2 on confirmed state, then 3+4 |
| Critical | `score > 0.90` | Escalate human notification to immediate |

---

## 6. The Narrative Synthesis Layer

This is your genuine contribution above Graphiti. It runs between triage and the Graphiti write.

### 6.1 The synthesis loop

1. **Load current state.** Query Graphiti for the affected entity's current wiki page (from your `/wiki` store) and recent related facts.
2. **Reconcile.** LLM prompt: given the new signal and the current assessment, identify contradictions, explain them, produce an updated assessment. *This is the interpretive step Graphiti does not do.*
3. **Write `/wiki` page.** Save the reconciled prose to your `/wiki` markdown store, keyed by entity. Git-versioned so history is preserved.
4. **Hand to Graphiti.** Call `add_episode()` with the synthesized text — Graphiti extracts entities, updates edges, embeds, versions.

### 6.2 The `/wiki` store

A separate store your layer owns — **NOT inside Graphiti**. Markdown files (or a simple table), one per entity, git-versioned. Graphiti stores the *embedding* of the page as part of the episode; the canonical prose lives in `/wiki`. This gives you: human-editable pages, full version history, and a clean source for decision-memo assembly.

### 6.3 Synthesis prompt skeleton

```python
SYNTH_PROMPT = '''You maintain the intelligence page for
{entity}. A new signal has arrived.

CURRENT PAGE:
{current_wiki_page}

NEW SIGNAL:
{new_signal}

Produce an updated assessment. You MUST:
1. State the current reconciled status in 2-3 sentences.
2. If the new signal contradicts the current page, explain
   WHY the contradiction exists (lagging data? different
   measurement? genuine change?). Do not just overwrite.
3. Note any historical pattern this matches.
4. List affected downstream entities.
Keep it factual, cited, under 250 words.'''
```

> **💡 Triage first.** Synthesis is the expensive step. The triage gate runs BEFORE it: embed the incoming signal, cosine-similarity against tracked entity embeddings. Only HIGH (>0.72 similarity, or any sanctions/changepoint) triggers full synthesis. MED → fact extraction only. LOW → store raw, no synthesis. This keeps ~88% of signals out of the expensive path.

---

## 7. The Read/Write API — What Other Systems Call

You expose a thin typed wrapper over Graphiti so the other four teammates never write raw search calls. This is the contract. **Lock the signatures Week 1; implement bodies Week 2.**

### 7.1 Write API

| Function | Called by | Effect |
|---|---|---|
| `ingest_signal(signal)` | System 1 | Triage → synth → Graphiti write. The main entry point. |
| `write_scenario(out)` | System 2 | Stores `Scenario_Output` episode |
| `write_procurement(rec)` | System 3 | Stores `ProcurementRec` episode |
| `write_spr_schedule(sch)` | System 4 | Stores `SPRSchedule` episode |
| `write_pending(scenario)` | Sandbox | Stores `PendingScenario` (speculative, isolated) |

### 7.2 Read API

| Function | Called by | Returns |
|---|---|---|
| `get_subgraph(entity, hops=2)` | System 2 | Connected nodes + current properties for scenario init |
| `get_available_suppliers()` | System 3 | Suppliers with `risk<0.4`, not sanctioned |
| `get_grade_specs(refinery)` | System 3 | `CONFIGURED_FOR` edges + crude specs |
| `get_routes(risk_max=0.5)` | System 3 | Corridors below risk threshold |
| `get_spr_state()` | System 4 | All `SPRCavern` fill levels |
| `get_risk_scores()` | Monitor/S5 | All current `RISK_STATE` edges |
| `copilot_query(q)` | System 5 | EA-GraphRAG routed hybrid search result |
| `get_wiki_page(entity)` | System 5 | Narrative synthesis page for node click |

### 7.3 Example read implementation

```python
async def get_subgraph(entity: str, hops: int = 2):
    '''System 2 calls this to init a scenario.'''
    results = await graphiti.search(
        query=f'supply chain nodes connected to {entity}',
        num_results=20,
        center_node_uuid=resolve(entity),  # rerank by graph distance
    )
    return shape_for_scenario(results)
```

---

## 8. Your Build Order (Week-by-Week)

### 8.1 Week 1 — Schema + contracts (BLOCKING for the team)

- **Day 1:** FalkorDB running, Graphiti connected, `build_indices_and_constraints()` succeeds, smoke-test `add_episode` + `search` on toy data.
- **Day 2:** Define all 9 entity types + edge types as Pydantic models. Write docstrings carefully (the LLM reads them).
- **Day 2–3:** Lock the `RISK_STATE` edge contract (§5). Sign off with whoever owns System 1 and the LangGraph monitor.
- **Day 3–4:** Stub all read/write API signatures (§7). Hand them to the team — they build against these.
- **Day 4–5:** End-to-end smoke test — ingest a real Hormuz signal, confirm entities extracted, `RISK_STATE` edge queryable, `/wiki` page written.

> **🚧 Gate.** The team cannot build in parallel until the schema and API signatures are locked. This is your Week 1 deliverable — **not a working KB, but a STABLE CONTRACT.**

### 8.2 Week 2 — Synthesis + triage

- Build the triage gate (embedding similarity scorer).
- Build the narrative synthesis agent + `/wiki` store + git versioning.
- Implement read API bodies against real Graphiti.
- Wire Bedrock Nova Pro as Graphiti's extraction LLM; verify structured output works.

### 8.3 Week 3 — Integration hardening

- Real signal ingestion at volume; tune `SEMAPHORE_LIMIT` for Bedrock rate limits.
- Entity-resolution QA — check for duplicate nodes, tighten type docstrings if needed.
- Backtest the risk-edge writes on Feb 2026 Hormuz timeline; confirm monitor fires correctly.

### 8.4 Week 4 — Demo readiness

- Pre-cache the golden-path graph state for `DEMO_MODE`.
- FalkorDB browser (`:3000`) ready as a backup visual of the live graph.
- Consistency audit: `/wiki`, graph edges, embeddings all reflect the same state.

---

## 9. Known Pitfalls & Mitigations

| Pitfall | Mitigation |
|---|---|
| Small LLM emits malformed JSON → ingestion fails | Use Nova Pro / capable model. If local, use `json_object` mode. |
| Duplicate entity nodes (Hormuz vs the Strait) | Strong custom-type docstrings; review FalkorDB browser; tune descriptions. |
| Rate-limit 429s on bulk ingest | Lower `SEMAPHORE_LIMIT`; use `add_episode_bulk` only for empty-graph backfill. |
| Risk score not queryable by monitor | Lock `RISK_STATE` contract Week 1; state score explicitly in episode text. |
| `/wiki` and graph drift apart | Single write path — synthesis writes both, in sequence, same function. |
| Sandbox `PendingScenario` contaminates ground truth | Tag speculative; isolate; never let it set `RISK_STATE` on live nodes. |
| `add_episode_bulk` skips edge invalidation | Use plain `add_episode` for live updates; bulk only for initial load. |

> **⭐ Single most important thing.** Lock the entity schema and the `RISK_STATE` edge contract in Week 1 and circulate them. Every other system codes against these. If they change in Week 3, four people refactor. **Stability of the contract matters more than perfection of the contract.**
