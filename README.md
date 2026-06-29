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
                                         │  typed read/write API only
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
├── contracts/                         # shared Pydantic contracts — imported by every package, imports nothing
│   ├── signal.py                      # NormalizedSignal: common envelope all sensory sub-agents emit
│   ├── outputs.py                     # ScenarioOutputData, ProcurementRecData, SPRScheduleData
│   └── bands.py                       # risk band thresholds (calm/watch/elevated/action/critical)
│
├── knowledge/                         # the knowledge base — only module that talks to Graphiti/FalkorDB
│   ├── connection.py                  # FalkorDriver bootstrap; build_indices_and_constraints()
│   ├── registry.py                    # canonical entity registry: 22 entities, H3 cells, alias lookup
│   ├── triage.py                      # source-aware routing gate: extract / synthesize / store / drop
│   ├── synthesis.py                   # Nova Pro wiki agent: reconciles signals → /wiki prose → Graphiti
│   ├── wikilink_processor.py          # [[wikilink]] normalizer, frontmatter validator, links_out builder
│   ├── ingest_queue.py                # Redis consumer loop; fusion model; write_risk_state dispatch
│   ├── schema/
│   │   ├── entities.py                # 11 entity types (Corridor, Supplier, Refinery…) as Pydantic + ENTITY_TYPES
│   │   └── edges.py                   # 9 edge types (RISK_STATE, EXPORTS_VIA…) + EDGE_TYPES + EDGE_TYPE_MAP
│   ├── wiki/                          # Store 3: one Markdown file per entity, git-versioned narrative pages
│   └── api/
│       ├── read.py                    # get_risk_scores, get_subgraph, copilot_query, get_wiki_page…
│       └── write.py                   # ingest_signal, write_scenario, write_procurement, write_spr_schedule…
│
├── orchestration/                     # LangGraph autonomous loop — drives the pipeline without human input
│   ├── state.py                       # SAGEState TypedDict
│   ├── monitor.py                     # polls get_risk_scores() every 30s; fires triggers on band crossings
│   ├── sandbox.py                     # anticipatory fork: snapshot → trajectory → GNN → pre-stage systems 3+4
│   ├── triggers.py                    # on_elevated / on_action / on_critical / on_sandbox_promoted
│   └── graph.py                       # LangGraph StateGraph: SENSE→TRIAGE→SAGE→SANDBOX→SCENARIO→PROCURE→RESERVE
│
├── sensory_agent/                     # System 1 — four always-on sub-agents; sole writer of raw signals
│   ├── ais.py                         # AIS websocket, H3 indexing, dark-vessel detection, SAR fusion
│   ├── news.py                        # GDELT + NewsAPI every 15 min; Nova Micro entity extraction
│   ├── sanctions.py                   # OFAC/EU/UN diff every 6h; any new addition is force_synthesis=True
│   └── prices.py                      # EIA + yfinance every 5 min; BOCD changepoint detection
│
├── scenario_agent/                    # System 2 — ARIO disruption cascade modeller
│   ├── ario.py                        # Hallegatte 2008 dynamic IO cascade
│   ├── runner.py                      # reads subgraph → runs ARIO or GNN → write_scenario()
│   └── gnn/
│       ├── model.py                   # PyTorch GraphSAGE surrogate; <150ms on T4 GPU
│       └── train.py                   # Monte Carlo ARIO sweep → GNN training
│
├── alt_procurement_agent/             # System 3 — finds and ranks alternative crude sources
│   ├── routing.py                     # OR-Tools MILP over corridors and ports
│   ├── grade.py                       # RF + Peng-Robinson EOS: crude compatibility per refinery
│   ├── rank.py                        # TOPSIS multi-objective ranking
│   └── runner.py                      # reads KB → ranks options → write_procurement()
│
├── reserve_optim_agent/               # System 4 — optimal SPR drawdown under supply shock uncertainty
│   ├── sdp.py                         # Bellman iteration; CMDP Lagrangian relaxation
│   ├── options.py                     # real-options valuation: value of waiting before drawdown
│   └── runner.py                      # reads SPR state + scenario gap → write_spr_schedule()
│
├── visualizer_agent/                  # System 5 — digital twin UI; pure consumer, writes nothing
│   ├── api_gateway/
│   │   └── main.py                    # FastAPI + WebSocket: REST, risk-score push, copilot, wiki
│   └── frontend/
│       └── src/                       # React + deck.gl: geospatial map, H3 heatmap, copilot, pipeline bar
│
└── demo_cache/                        # pre-recorded Feb 23–28 2026 Hormuz replay for DEMO_MODE=true
```

---

## Knowledge Base — What You Need to Know

The KB has **three stores**, all written in one sequence by `knowledge/api/write.py`. No agent touches Graphiti, FalkorDB, or the wiki files directly.

| Store | What | Where |
|---|---|---|
| **Episodic** | Every synthesized episode node + provenance. Non-lossy ground truth. | FalkorDB (Graphiti-managed) |
| **Semantic graph** | Typed entity nodes + typed edges + embeddings + bitemporal validity windows. | FalkorDB (Graphiti-managed) |
| **/wiki store** | One Markdown file per entity. Human-readable intelligence pages with YAML frontmatter and `[[wikilinks]]`. | `knowledge/wiki/` volume |

**The only write path:**
```
NormalizedSignal → Redis queue → ingest_signal() → triage → synthesis → add_episode()
```

**The only import surface for agents:**
```python
from knowledge.api.read import ...    # reads
from knowledge.api.write import ...   # writes
# Never import graphiti_core, falkordb, or knowledge internals directly
```

**Key contracts (all in `contracts/`):**

```python
# NormalizedSignal — System 1's only output
class NormalizedSignal(BaseModel):
    signal_id: str                                               # ULID/UUID unique per signal
    source: Literal["ais", "gdelt", "news", "sanctions", "price"]
    observed_at: datetime                                        # when true in the world
    priority_hint: Literal["HIGH", "MED", "LOW"]
    force_synthesis: bool                                        # bypasses triage gate
    entity_refs: list[str]                                       # canonical display names
    summary: str                                                 # one-line description
    payload: dict                                                # source-specific fields

# Risk bands — contracts/bands.py
# calm (<0.25) · watch (0.25–0.45) · elevated (0.45–0.70) · action (0.70–0.90) · critical (≥0.90)
```

Full schema: [`.claude/design/SAGE_Schema_and_Contracts_Spec.md`](.claude/design/SAGE_Schema_and_Contracts_Spec.md)

---

## One-Time Startup (All Containers)

```python
from knowledge.connection import init as kb_init
await kb_init()   # idempotent — call once at container boot before any KB call
```

---

## System 1 — Sensory Agent Wiring Guide

System 1 is the **sole producer** of raw signals. Its four sub-agents run continuously and push `NormalizedSignal` objects onto the Redis queue. The KB consumer handles everything from there — sub-agents never call `ingest_signal()` or `write_risk_state()` directly.

### How Entity Resolution Works

Before emitting any signal, System 1 must populate `entity_refs` with **canonical display names** that match the entity registry. Inconsistent naming creates duplicate graph nodes.

```python
# Import these resolvers — never guess entity names manually
from knowledge.registry import (
    resolve_h3,           # AIS: H3 cell → entity_id
    resolve_instrument,   # Price: ticker → [entity_id, ...]
    resolve_name,         # Sanctions/News: free-form name → entity_id
    canonical_name,       # entity_id → exact display name string
)

# AIS example
entity_id = resolve_h3("8a2a1072b59ffff")        # → "corridor_hormuz"
display = canonical_name(entity_id)               # → "Strait of Hormuz"

# Price example
entity_ids = resolve_instrument("BZ=F")           # → ["corridor_hormuz", "corridor_bab_el_mandeb"]
displays = [canonical_name(eid) for eid in entity_ids]

# Sanctions/News example
entity_id = resolve_name("Aramco")                # → "supplier_aramco"
display = canonical_name(entity_id)               # → "Saudi Aramco"
```

**All 22 tracked entities live in `knowledge/registry.py`.** Canonical names by category:

| Category | Canonical names |
|---|---|
| Corridors | `"Strait of Hormuz"`, `"Bab-el-Mandeb"`, `"Suez Canal"`, `"Strait of Malacca"` |
| Suppliers | `"Saudi Aramco"`, `"NIOC"`, `"ADNOC"`, `"Rosneft"`, `"Iraqi Oil Ministry"` |
| Refineries | `"Jamnagar Refinery"`, `"Mangaluru"`, `"Paradip"` |
| Ports | `"Vadinar"`, `"Yanbu"`, `"Sikka"`, `"Fujairah"` |
| SPR sites | `"Vizag SPR"`, `"Mangaluru SPR"`, `"Padur SPR"` |
| Authorities | `"OFAC"`, `"EU"`, `"UN"` |

---

### Sub-Agent 1: AIS (always-on, push on anomaly only)

**What it monitors:** vessel position stream from aisstream.io. Runs internal H3 clustering to detect dark-vessel gaps and anomaly clusters.

**When to push:** only on detected anomaly events. Never push individual position pings — high-frequency telemetry that isn't an anomaly is noise, not signal.

**Frequency:** event-driven (whenever gap > 4h or anomaly cluster detected). Typically 0–10 pushes per hour under normal conditions; up to 50/hour during a crisis event.

**Triage routing:** always `"extract"` — AIS telemetry updates the `factor_ais` contribution to the risk score but never authors wiki prose directly. The narrative update happens at the next fusion flush window when news corroborates.

```python
from contracts.signal import NormalizedSignal
from knowledge.ingest_queue import push_signal
from knowledge.registry import resolve_h3, canonical_name

async def on_ais_anomaly(h3_cell: str, mmsi: str, gap_hours: float, anomaly_score: float):
    entity_id = resolve_h3(h3_cell)
    if not entity_id:
        return  # cell not in tracked registry — discard

    await push_signal(NormalizedSignal(
        signal_id=f"ais-{ulid()}",
        source="ais",
        observed_at=datetime.now(timezone.utc),    # when the gap started, not when detected
        ingested_at=datetime.now(timezone.utc),
        priority_hint="HIGH",                       # AIS anomalies are always HIGH
        force_synthesis=False,                      # NEVER True for AIS — triage handles routing
        entity_refs=[canonical_name(entity_id)],   # e.g. "Strait of Hormuz"
        h3_cells=[h3_cell],
        lat=26.1, lon=57.2,                         # cluster centroid
        summary=f"AIS dark-vessel gap: MMSI {mmsi}, {gap_hours:.1f}h gap, "
                f"anomaly score {anomaly_score:.2f}, H3 cell {h3_cell}",
        payload={
            "mmsi":           mmsi,
            "gap_hours":      gap_hours,
            "dark_vessel":    True,
            "anomaly_score":  anomaly_score,
            "sar_confirmed":  False,         # update to True if SAR cross-reference confirms
            "dark_count":     1,             # number of vessels in cluster
        },
    ))
```

**Vessel cluster (multiple dark vessels):**
```python
# When multiple vessels show coordinated dark gaps — push one signal per cluster, not per vessel
await push_signal(NormalizedSignal(
    signal_id=f"ais-cluster-{ulid()}",
    source="ais",
    priority_hint="HIGH",
    force_synthesis=False,
    entity_refs=["Strait of Hormuz"],
    summary=f"AIS dark-vessel cluster: {dark_count} vessels, Larak Island area, {gap_hours:.0f}h max gap",
    payload={
        "mmsi":          representative_mmsi,    # most significant vessel
        "dark_vessel":   True,
        "dark_count":    dark_count,             # cluster size
        "gap_hours":     gap_hours,              # maximum gap in cluster
        "anomaly_score": cluster_anomaly_score,
        "h3_cluster":    h3_cells,               # all cells in cluster
    },
))
```

**What NOT to push:**
```python
# WRONG — do not push position pings
NormalizedSignal(source="ais", summary="MMSI 477553000 at 26.1N 57.2E speed 0.1kt", ...)

# WRONG — do not push routine AIS data
NormalizedSignal(source="ais", summary="Vessel transiting Hormuz at normal speed", ...)
```

---

### Sub-Agent 2: News / GDELT (every 15 minutes)

**What it monitors:** GDELT event stream and NewsAPI for articles mentioning tracked entities.

**When to push:** after Nova Micro extraction pass identifies a tracked entity. Push per article, not per topic batch.

**Frequency:** every 15 minutes poll → push 0–20 signals per cycle depending on news volume. During a crisis event, can be higher. Do not debounce within the same article.

**Triage routing:** similarity-based. Articles with cosine similarity > 0.72 against the entity's current page trigger full synthesis (wiki updated). Articles scoring 0.40–0.72 trigger extraction only (graph updated, wiki unchanged). Below 0.40 → stored raw.

```python
from knowledge.registry import resolve_name, canonical_name, REGISTRY
from knowledge.triage import _embed_text, _cosine   # for embedding fallback

async def on_news_article(article_text: str, article_url: str, published_at: datetime):
    # Step 1: Nova Micro extraction — extract candidate entity names from article
    candidate_names = await nova_micro_extract_entities(article_text)
    # returns e.g. ["IRGC", "Strait of Hormuz", "Larak Island", "MT Destiny"]

    # Step 2: Resolve candidates against registry
    entity_refs = []
    for name in candidate_names:
        entity_id = resolve_name(name)           # alias lookup (fast, deterministic)
        if entity_id:
            entity_refs.append(canonical_name(entity_id))
        # else: not a tracked entity — skip (don't add unresolved names)

    if not entity_refs:
        return   # article mentions no tracked entities — discard

    # Step 3: Push one signal covering all resolved entities in the article
    severity = await estimate_severity(article_text)   # 0..1 based on tone/goldstein
    tone = await get_gdelt_tone(article_url)           # negative = hostile

    await push_signal(NormalizedSignal(
        signal_id=f"news-{ulid()}",
        source="news",
        observed_at=published_at,                  # article publish time, not now
        ingested_at=datetime.now(timezone.utc),
        priority_hint="HIGH" if severity > 0.6 else "MED",
        force_synthesis=False,                     # let triage decide — don't bypass
        entity_refs=entity_refs,
        summary=f"{source_name}: {article_headline}",   # first sentence of article
        payload={
            "actor":      extracted_actor,         # e.g. "IRGC"
            "action":     extracted_action,        # e.g. "naval exercise"
            "target":     extracted_target,        # e.g. "Strait of Hormuz" (optional)
            "tone":       tone,                    # GDELT tone score (negative = hostile)
            "severity":   severity,                # 0..1 severity estimate
            "goldstein":  goldstein_score,         # GDELT Goldstein scale (optional)
        },
        source_url=article_url,
        raw_ref=f"s3://sage-raw/news/{article_id}",
    ))
```

**GDELT stream (raw event records):**
```python
# GDELT event records don't need Nova Micro — entity is already in the record
await push_signal(NormalizedSignal(
    signal_id=f"gdelt-{gdelt_global_event_id}",
    source="gdelt",
    observed_at=gdelt_event_date,
    priority_hint="MED",
    force_synthesis=False,
    entity_refs=[canonical_name(resolve_name(gdelt_actor1))] if resolve_name(gdelt_actor1) else [],
    summary=f"GDELT: {gdelt_event_code_description} — {gdelt_actor1} vs {gdelt_actor2}",
    payload={
        "actor":      gdelt_actor1,
        "action":     gdelt_event_code,
        "tone":       gdelt_avg_tone,
        "goldstein":  gdelt_goldstein_scale,
        "severity":   abs(gdelt_avg_tone) / 10.0,   # normalize GDELT tone to 0..1
    },
))
```

---

### Sub-Agent 3: Sanctions (every 6 hours + immediate on diff)

**What it monitors:** OFAC SDN, EU consolidated list, UN sanctions committee list. Runs a diff against the last cached version.

**When to push:** immediately on any detected change (add or remove). The 6-hour polling interval is the minimum check frequency — push as soon as the diff is detected, even if outside the normal poll window.

**Frequency:** 0–5 pushes per 6-hour cycle under normal conditions. During a sanctions burst (coordinated designations), can be 20+ pushes in a single cycle.

**Triage routing:** always `"synthesize"` — `_ALWAYS_SYNTH_SOURCES = {"sanctions"}` in triage. Every sanctions change produces a wiki update because it always changes a specific tracked entity's status.

**New vessels — register before pushing:**
```python
from knowledge.registry import resolve_name, canonical_name, register_vessel

async def on_ofac_diff(diff_entries: list[dict]):
    for entry in diff_entries:
        subject_name = entry["subject"]
        mmsi = entry.get("mmsi")

        # Try to resolve against existing registry first
        entity_id = resolve_name(subject_name)

        if not entity_id and mmsi:
            # New vessel — register it now so entity_refs resolves correctly
            entity_id = register_vessel(
                mmsi=mmsi,
                vessel_name=subject_name,
                imo=entry.get("imo"),
            )

        entity_refs = [canonical_name(entity_id)] if entity_id else [subject_name]

        # Also include the operator if known and tracked
        operator_name = entry.get("operator")
        if operator_name:
            op_id = resolve_name(operator_name)
            if op_id:
                entity_refs.append(canonical_name(op_id))

        await push_signal(NormalizedSignal(
            signal_id=f"sanctions-{entry['list']}-{ulid()}",
            source="sanctions",
            observed_at=datetime.now(timezone.utc),
            ingested_at=datetime.now(timezone.utc),
            priority_hint="HIGH",
            force_synthesis=True,              # ALWAYS True for sanctions
            entity_refs=entity_refs,
            summary=f"{entry['list']}: {subject_name} {entry['change']}ed — "
                    f"{entry.get('subject_type', 'entity')}, operator: {operator_name or 'unknown'}",
            payload={
                "list":          entry["list"],            # "OFAC_SDN" | "EU" | "UN"
                "change":        entry["change"],          # "add" | "remove"
                "subject":       subject_name,
                "subject_type":  entry.get("subject_type", "entity"),  # "vessel" | "entity" | "person"
                "effective_date": entry.get("effective_date"),
                "mmsi":          mmsi,
                "dwt":           entry.get("dwt"),         # vessel deadweight tonnage
                "operator":      operator_name,
            },
        ))
```

**Removal events are also significant** — a delisted supplier or vessel changes procurement options:
```python
# Sanctions removal (entity restored) — still force_synthesis=True
NormalizedSignal(
    source="sanctions",
    force_synthesis=True,
    priority_hint="HIGH",
    summary=f"OFAC removed {subject_name} from SDN list — entity restored",
    payload={"change": "remove", ...},
)
```

---

### Sub-Agent 4: Prices (every 5 minutes poll, push on changepoint only)

**What it monitors:** Brent (BZ=F) and WTI (CL=F) via yfinance every 5 minutes. Runs BOCD (Bayesian Online Changepoint Detection) on the rolling price series. Also monitors EIA weekly reserves.

**When to push:** only on BOCD changepoint detection or market regime shift. Normal price ticks are never pushed — a `$0.20` move in Brent is noise.

**Frequency:** 0–3 pushes per day under calm conditions. During a crisis event with volatile prices, up to 10–15 per day.

**Triage routing:** always `"extract"` — price signals update `factor_price` in the risk score but never author wiki prose directly. The narrative update happens via fusion when multiple signals align.

```python
from knowledge.registry import resolve_instrument, canonical_name

async def on_price_tick(instrument: str, price: float, price_series: list[float]):
    # Run BOCD on rolling window
    bocd_result = detect_changepoint(price_series)

    if not bocd_result.is_changepoint and not bocd_result.regime_shift:
        return   # normal tick — do not push

    # Resolve which entities this instrument affects
    entity_ids = resolve_instrument(instrument)     # e.g. ["corridor_hormuz", "corridor_bab_el_mandeb"]
    if not entity_ids:
        return

    entity_refs = [canonical_name(eid) for eid in entity_ids]

    price_change_pct = (price - price_series[-2]) / price_series[-2] * 100
    war_risk_premium = estimate_war_risk_premium(price_series)

    await push_signal(NormalizedSignal(
        signal_id=f"price-{instrument}-{ulid()}",
        source="price",
        observed_at=datetime.now(timezone.utc),
        ingested_at=datetime.now(timezone.utc),
        priority_hint="HIGH",                      # changepoints are always HIGH
        force_synthesis=False,                     # price never triggers wiki prose directly
        entity_refs=entity_refs,
        summary=f"{instrument} BOCD changepoint: {price_change_pct:+.1f}% move, "
                f"war-risk premium {war_risk_premium:.2%}, regime {bocd_result.regime}",
        payload={
            "instrument":           instrument,         # "BZ=F" | "CL=F"
            "price":                price,
            "price_change_pct":     price_change_pct,
            "changepoint":          bocd_result.is_changepoint,
            "bocd_probability":     bocd_result.probability,
            "regime":               bocd_result.regime,        # "calm" | "stressed" | "crisis"
            "war_risk_premium":     war_risk_premium,
            "regime_stressed":      1.0 if bocd_result.regime != "calm" else 0.0,
        },
    ))
```

**Regime shift (distinct from individual changepoint):**
```python
# A sustained regime change (e.g. calm → stressed for 3+ consecutive ticks) is also worth pushing
if regime_changed:
    await push_signal(NormalizedSignal(
        source="price",
        force_synthesis=False,
        summary=f"{instrument} regime shift: {old_regime} → {new_regime}, "
                f"sustained for {duration_minutes:.0f}min",
        payload={
            "instrument": instrument,
            "regime":     new_regime,
            "regime_stressed": 1.0 if new_regime != "calm" else 0.0,
            "changepoint": False,   # regime shift, not a point change
        },
    ))
```

---

### After the Fusion Flush (every 30s): Write Risk State

The ingest queue consumer automatically calls `write_risk_state()` after accumulating 10 signals or 30 seconds — whichever comes first. **You do not call `write_risk_state()` from sub-agents.** But you must implement the fusion model if overriding the default weighted-sum fallback.

The built-in weighted-sum fusion (`knowledge/ingest_queue.py:_weighted_fusion`) is the default. To replace it with a trained GBM:

```python
# sensory_agent/fusion_model.pkl — place trained model here
# The consumer loop loads it automatically on next flush
# Interface contract: model.predict(fv: _FeatureVector) -> _FusionResult

@dataclass
class _FeatureVector:
    ais_gap_count_24h:         float   # number of AIS gaps > 4h in last 24h
    ais_dark_vessel_count:     float   # dark vessels in monitored cells
    ais_anomaly_score_max:     float   # max HABIT anomaly score (0..1)
    ais_gap_duration_max_h:    float   # max gap duration in hours
    ais_monitored_cell_pct:    float   # % of tracked H3 cells with activity
    ais_velocity_std:          float   # velocity standard deviation
    gdelt_tone_24h_mean:       float   # average GDELT tone (negative = hostile)
    gdelt_tone_delta:          float   # tone change in last window
    news_severity_max:         float   # max article severity (0..1)
    news_event_count_24h:      float   # number of severity > 0.7 events
    price_brent_pct_change_24h: float  # Brent 24h % change
    price_bocd_flag:           float   # 1.0 if BOCD breakpoint detected
    price_regime:              float   # 1.0 if regime = stressed
    price_war_risk_premium:    float   # war-risk premium proxy (0..1)
    sanctions_new_additions_24h: float # new SDN additions in last 24h
    sanctions_vessel_count:    float   # sanctioned vessels in monitored corridors
    sanctions_major_entity:    float   # 1.0 if major state entity sanctioned
```

---

### System 1 KB Field Requirements

| Field | Required? | Rules |
|---|---|---|
| `signal_id` | Yes | Unique ULID/UUID per signal. Used as Graphiti episode name. |
| `source` | Yes | Exactly one of: `"ais" "gdelt" "news" "sanctions" "price"` |
| `observed_at` | Yes | When the event happened in the world — not when your sub-agent detected it. This is `reference_time` in Graphiti. |
| `entity_refs` | Yes | **Canonical display names from `knowledge/registry.py`**. Wrong names = duplicate graph nodes. Always use `canonical_name(resolve_*(x))`. |
| `summary` | Yes | One-line prose description. Becomes the triage embedding input. Write informative sentences, not log-line format. |
| `force_synthesis` | Conditional | `True` for sanctions always. `False` for AIS always. `False` for price (triage handles routing). `False` for news (let triage decide). |
| `priority_hint` | Recommended | `"HIGH"` for: dark vessels, sanctions adds, BOCD breakpoints. `"MED"` for: routine news. `"LOW"` rarely used. |
| `raw_ref` | Recommended | S3 URI or DB ID of verbatim raw record. Required for full audit trail. |
| `source_url` | For news | Article or source URL. Used for citation in copilot. |
| `h3_cells` | For AIS | H3 cell IDs of the anomaly cluster. Used for spatial indexing. |

### System 1 Build Checklist

- [ ] Sub-agent calls only `push_signal()` — never `ingest_signal()` or `write_risk_state()`
- [ ] AIS imports `resolve_h3()` → uses `canonical_name()` for `entity_refs` population
- [ ] Price imports `resolve_instrument()` → uses `canonical_name()` for `entity_refs`
- [ ] Sanctions imports `resolve_name()` → calls `register_vessel()` for new MMSI before pushing
- [ ] News runs Nova Micro extraction → resolves candidates via `resolve_name()` → discards unresolved
- [ ] AIS: `force_synthesis=False` always; pushes per anomaly cluster, never per position ping
- [ ] Price: `force_synthesis=False`; pushes only on BOCD changepoint or regime shift
- [ ] Sanctions: `force_synthesis=True` always; pushes both add and remove events
- [ ] News: `force_synthesis=False`; pushes per article, not per topic batch
- [ ] `observed_at` is the event time in the world, not the sub-agent's current time
- [ ] `signal_id` is a ULID or UUID — unique per signal emission
- [ ] `raw_ref` set to the S3 key or DB ID of the verbatim raw record
- [ ] Container calls `await kb_init()` before the first `push_signal()`

---

## System 2 — Disruption Scenario Modeller

**Trigger:** automatic, via `orchestration/triggers.py` when risk band crosses `action` (score ≥ 0.70) or a sandbox `PendingScenario` is promoted.

**Reads from KB:**
```python
from knowledge.api.read import get_subgraph, get_risk_scores

# 2-hop supply-chain subgraph for ARIO initialisation
subgraph = await get_subgraph("Strait of Hormuz", hops=2)
# subgraph.nodes: [{uuid, display_name, labels, attributes}]
# subgraph.edges: [{relation_type, attributes: {throughput_share_pct}, valid_at}]

scores = await get_risk_scores()
hormuz_score = next(s.score for s in scores if s.entity == "Strait of Hormuz")
```

**Key node attributes used by ARIO:**

| Property | Node type | Unit |
|---|---|---|
| `throughput_capacity_mbpd` | Refinery | mbpd |
| `inventory_days` | Refinery | days |
| `throughput_share_pct` | FEEDS / SUPPLIES edge | 0..1 fraction |
| `daily_export_mbpd` | Supplier | mbpd |
| `choke_severity` | Corridor | 0..1 |

**Writes to KB:**
```python
from knowledge.api.write import write_scenario
from contracts.outputs import ScenarioOutputData

result = await write_scenario(ScenarioOutputData(
    scenario_id="sc-20260228-001",
    trigger_entity="Strait of Hormuz",
    status="confirmed",             # "speculative" if from sandbox
    confidence=0.85,
    gap_mbpd=1.2,
    gap_duration_days=14.0,
    feedstock_gap_timeline=[1.1, 1.2, 1.3, 1.2, 1.1, 1.0, 0.9],
    price_impact_low=8.0,
    price_impact_high=22.0,
    spr_depletion_days=6.5,
    assumptions={
        "import_dependence_pct": {"value": 88.2, "unit": "%", "source": "PPAC 2025"},
        "hormuz_share_pct":      {"value": 42.0, "unit": "%", "source": "IEA 2025"},
    },
))
# result.episode_uuid → pass as scenario_ref to Systems 3 and 4
```

---

## System 3 — Adaptive Procurement Orchestrator

**Trigger:** automatic, via `orchestration/triggers.py` when a new `ScenarioOutput` node appears.

**Reads from KB:**
```python
from knowledge.api.read import get_available_suppliers, get_grade_specs, get_routes

suppliers = await get_available_suppliers(risk_max=0.4)  # excludes sanctioned + high-risk
grades    = await get_grade_specs("Jamnagar Refinery")   # CONFIGURED_FOR edges
routes    = await get_routes(risk_max=0.5)               # open corridors
```

**Writes to KB:**
```python
from knowledge.api.write import write_procurement
from contracts.outputs import ProcurementRecData, ProcurementOption, ScoreBreakdown

await write_procurement(ProcurementRecData(
    scenario_id="sc-20260228-001",
    status="confirmed",
    ranked=[
        ProcurementOption(
            supplier="Saudi Aramco", grade="Arab Light", route_via="Yanbu bypass",
            landed_cost_usd_bbl=85.30, lead_time_days=12.0,
            grade_compatibility=0.92, corridor_risk=0.12, topsis_score=0.87,
            score_breakdown=ScoreBreakdown(
                cost_score=0.78, lead_time_score=0.85,
                grade_compatibility_score=0.92, corridor_risk_score=0.88,
            ),
            rationale="Yanbu pipeline bypasses Hormuz; Arab Light within Jamnagar gravity envelope.",
        ),
    ],
))
```

**Note:** a supplier's `sanctioned` flag is updated in real time by System 1's sanctions sub-agent. When `get_available_suppliers()` runs, a supplier sanctioned 30 minutes ago is already excluded.

---

## System 4 — Strategic Reserve Optimisation

**Trigger:** automatic, parallel to System 3.

**Reads from KB:**
```python
from knowledge.api.read import get_spr_state, get_subgraph

caverns = await get_spr_state()
total_fill_mmt = sum(c.current_fill_mmt or 0 for c in caverns)
# India total capacity: 5.33 MMT (Vizag 1.33 + Mangaluru 1.50 + Padur 2.50)
```

**Writes to KB:**
```python
from knowledge.api.write import write_spr_schedule
from contracts.outputs import SPRScheduleData, SPRDay

await write_spr_schedule(SPRScheduleData(
    scenario_id="sc-20260228-001",
    status="confirmed",
    daily_plan=[
        SPRDay(day=1, action="draw", volume_mmt=0.18,
               reserve_after_mmt=5.15, days_cover_after=9.2,
               decision_driver="gap onset — begin draw"),
        SPRDay(day=15, action="hold", volume_mmt=0.0,
               reserve_after_mmt=3.89, days_cover_after=6.9,
               decision_driver="procurement alternatives arrived — halt draw"),
    ],
    prob_above_buffer=0.96,
    constraint_satisfied=True,
    policy_memo="Draw at 0.18 MMT/day for 14 days; buffer maintained at >6.9 days cover.",
))
```

---

## System 5 — Digital Twin (Visualizer)

**Pure consumer — reads everything, writes nothing.** If you find yourself calling a write function from `visualizer_agent`, it belongs in one of Systems 1–4.

```python
from knowledge.api.read import (
    get_risk_scores,            # every 30s — drives map node colours
    get_subgraph,               # on node click — connected entities
    get_wiki_page,              # on node click — narrative prose panel
    copilot_query,              # on user question — EA-GraphRAG routed
    get_available_suppliers,    # for procurement results panel
    get_spr_state,              # for SPR timeline panel
)

# Risk band → UI colour
# "calm" (<0.25) → phosphor green
# "watch" (0.25–0.45) → cyan
# "elevated" (0.45–0.70) → amber
# "action" (0.70–0.90) → red
# "critical" (≥0.90) → pulsing red

# Copilot
answer = await copilot_query("Which refineries are most exposed to a Hormuz closure?")
# answer.answer      → Nova Pro synthesised prose
# answer.citations   → Graphiti episode UUIDs — render as clickable sources
# answer.latency_ms  → show in UI

# Wiki page on node click
page = await get_wiki_page("Strait of Hormuz")
# page.content → Markdown with [[wikilinks]] and YAML frontmatter
```

**Pipeline bar** (`SENSE → TRIAGE → SAGE → SANDBOX → SCENARIO → PROCURE → RESERVE`) is driven by WebSocket events from `orchestration/graph.py` — not KB polling.

---

## Sandbox / Speculative Lifecycle

```python
from knowledge.api.write import write_pending, promote_pending

# sandbox.py — speculative fork (NEVER write_risk_state here)
await write_pending(
    confidence=0.73,
    projected_crossing_hours=18.0,
    scenario_ref="sandbox-abc12345",
    entity="Strait of Hormuz",
)

# orchestration/monitor.py — on confirmed live crossing
await promote_pending("sandbox-abc12345")
```

Lifecycle: `speculative` → `promoted` (within 30s of crossing) → `expired` (72h TTL).

---

## Quick Start

```bash
# 1. Copy and fill in environment variables
cp .env.example .env
# set FALKORDB_PASSWORD, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION,
#     AISSTREAM_API_KEY, EIA_API_KEY, NEWSAPI_KEY, REDIS_URL

# 2. Start infrastructure
docker compose up falkordb redis -d

# 3. Smoke test the KB
python3 -c "
from knowledge.connection import init
from knowledge.registry import REGISTRY, resolve_h3, canonical_name
import asyncio
asyncio.run(init())
print('Registry:', len(REGISTRY), 'entities')
print('Hormuz H3 lookup:', canonical_name(resolve_h3('8a2a1072b59ffff')))
"

# 4. Start everything
docker compose up

# 5. FalkorDB graph browser
open http://localhost:3000

# 6. Demo mode (pre-recorded signals, no live API keys needed)
DEMO_MODE=true docker compose up
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

## Design Specs

Full documentation in `.claude/design/`:

| Spec | What it covers |
|---|---|
| [`SAGE_Schema_and_Contracts_Spec.md`](.claude/design/SAGE_Schema_and_Contracts_Spec.md) | Normative schema, all 7 contracts, lock-in artifact |
| [`system1_interaction.md`](.claude/design/system1_interaction.md) | How each sensing stream writes to and reads from the KB; entity resolution detail |
| [`system2_designspec.md`](.claude/design/system2_designspec.md) | ARIO model equations, GNN surrogate, India parameters, demo targets |
| [`secondbrain_design.md`](.claude/design/secondbrain_design.md) | Wikilink format, `links_out` frontmatter, Obsidian + geospatial visualization |
| [`SAGE_Knowledge_Base_Spec.md`](.claude/design/SAGE_Knowledge_Base_Spec.md) | KB architecture narrative and build order |
| [`SAGE_Knowledge_Base_Deployment.md`](.claude/design/SAGE_Knowledge_Base_Deployment.md) | Infrastructure, cost breakdown, deployment guide |

---

## Cost

~$6/day development (spot EC2), ~$13/day demo week (on-demand). Total 4-week cost ~$197 — effectively $0 with AWS new-account credits. See deployment spec §6 for full breakdown.
