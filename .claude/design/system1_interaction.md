# SAGE — System 1 × Knowledge Base Interaction Guide
## How the Sensory Agent Reads From and Writes To the KB

**Audience:** System 1 sub-agent builders (AIS, GDELT/News, Prices, Sanctions)  
**Owner:** Knowledge Layer  
**Companion specs:**
- [`SAGE_Schema_and_Contracts_Spec.md`](./SAGE_Schema_and_Contracts_Spec.md) — normative contracts (C1–C4, C7)
- [`SAGE_Knowledge_Base_Spec.md`](./SAGE_Knowledge_Base_Spec.md) — KB architecture narrative
- [`system2_designspec.md`](./system2_designspec.md) — downstream consumer of what you write

---

## 0. One Paragraph Summary

System 1 is the **sole producer** of signals into the KB. Its four sub-agents push `NormalizedSignal` objects onto a Redis queue. SAGE core pops them, runs the triage gate, and decides which of three paths each signal takes: full narrative synthesis (wiki updated, Graphiti episode written), entity extraction only (Graphiti episode, no wiki), or raw storage (episode only, no extraction). After every flush window (30s or every 10 signals), the fusion model aggregates all signals per entity and calls `write_risk_state()` — the only function that writes a `RISK_STATE` edge to the graph. **System 1 never calls Graphiti directly and never touches wiki files directly.** All KB writes go through the typed API in `knowledge/api/write.py`.

---

## 1. What System 1 Writes — Signal Construction

System 1's **only KB interaction** is pushing a `NormalizedSignal` onto the Redis queue `sage:ingest`:

```python
from contracts.signal import NormalizedSignal
from knowledge.ingest_queue import push_signal

signal = NormalizedSignal(
    schema_version="1.0.0",
    signal_id="<ULID>",
    source="news",                          # ais | gdelt | news | sanctions | price
    observed_at=datetime.now(timezone.utc), # when the event happened in the world
    ingested_at=datetime.now(timezone.utc), # when your sub-agent emitted it
    priority_hint="HIGH",                   # HIGH | MED | LOW — your estimate
    force_synthesis=False,                  # True bypasses triage gate entirely
    entity_refs=["Strait of Hormuz"],       # CRITICAL — see §3 for how to populate
    h3_cells=["855b3557fffffff"],
    lat=26.5,
    lon=56.4,
    summary="Reuters: IRGC vessels shadow tanker convoy near Larak Island.",
    payload={...},                          # source-specific sub-schema (see §2)
    source_url="https://reuters.com/...",
    raw_ref="s3://sage-raw/news/abc123",
)

await push_signal(signal)
```

This is the complete interface. The sub-agent does not call `ingest_signal()`, `write_risk_state()`, or any other KB function directly.

---

## 2. Per-Source Signal Construction

### 2.1 AIS

AIS sub-agent processes the raw stream internally. **It does NOT push individual position pings.** It pushes only anomaly-detection events — one episode per detected anomaly cluster:

```python
# CORRECT — push the detection event, not the raw ping
NormalizedSignal(
    source="ais",
    priority_hint="HIGH",       # AIS anomalies are always HIGH by rule
    force_synthesis=False,      # AIS never force-synthesizes (see §4 — source routing)
    entity_refs=["Strait of Hormuz"],  # the corridor the anomaly was observed in
    h3_cells=["855b3557fffffff", "855b355bfffffff"],
    lat=26.1,
    lon=57.2,
    summary="AIS dark-vessel gap cluster: 4 vessels, Larak Island area, 14:30 UTC",
    payload={
        "mmsi":           "477553000",     # representative MMSI if single vessel
        "vessel_name":    "MT Destiny",
        "gap_hours":      6.5,             # AisPayload.gap_hours
        "dark_vessel":    True,            # AisPayload.dark_vessel
        "anomaly_score":  0.81,            # 0..1
        "sar_confirmed":  False,
        # Additional detection metadata (non-schema, safe in open payload):
        "dark_count":     4,               # how many vessels in cluster
        "h3_cluster":     ["855b3557fffffff"],
    },
)

# WRONG — do not push this
NormalizedSignal(
    source="ais",
    summary="MMSI 477553000 at 26.1N 57.2E speed 0.1kt",   # single position ping
    ...
)
```

**What the AIS sub-agent does internally before pushing:**
1. Runs H3 cell clustering on position stream
2. Detects gaps (vessel disappears > 4h from monitored cell)
3. Identifies dark-vessel clusters (SAR cross-reference, AIS gap + SAR imagery)
4. Runs anomaly score (HABIT model or similar)
5. **Only then** emits a NormalizedSignal with the detected event

### 2.2 GDELT / News

These are the richest signals and the primary driver of wiki narrative. Push per article/event:

```python
NormalizedSignal(
    source="news",           # or "gdelt" for raw GDELT records
    priority_hint="HIGH",    # set by article severity; news is always MED+ if entity matched
    force_synthesis=False,   # triage decides (high-similarity news will get it anyway)
    entity_refs=["Strait of Hormuz", "IRGC"],   # all entities mentioned in article
    summary="Reuters: Iran's IRGC vessels shadow crude tanker convoy near Larak Island, "
            "raising fears of Strait of Hormuz closure.",
    payload={
        "actor":       "IRGC",            # EventPayload.actor
        "action":      "shadow tanker",   # EventPayload.action
        "target":      "MT Destiny",      # EventPayload.target (optional)
        "tone":        -4.2,              # EventPayload.tone (GDELT: negative = hostile)
        "severity":    0.72,              # 0..1 (your estimate or GDELT Goldstein)
        "goldstein":   -7.0,              # EventPayload.goldstein (optional)
    },
    source_url="https://reuters.com/...",
)
```

### 2.3 Prices

**Only changepoints and regime shifts become signals.** Normal ticks are never pushed:

```python
# CORRECT — push only on BOCD breakpoint or regime shift
NormalizedSignal(
    source="price",
    priority_hint="HIGH",        # changepoints are always HIGH
    force_synthesis=True,        # BOCD changepoints bypass triage — they are always episodic
    entity_refs=["Strait of Hormuz"],   # the entity whose risk the price affects
    summary="Brent BOCD breakpoint: war-risk premium 0.38% → 0.41%, regime STRESSED",
    payload={
        "instrument":         "BZ=F",          # PricePayload.instrument
        "price":              83.40,            # USD/bbl
        "changepoint":        True,             # PricePayload.changepoint
        "regime":             "stressed",       # PricePayload.regime
        "war_risk_premium":   0.0041,           # PricePayload.war_risk_premium
        # extra detection metadata (open payload)
        "price_change_pct":   2.1,
        "bocd_probability":   0.94,
    },
)

# WRONG — do not push this
NormalizedSignal(
    source="price",
    summary="Brent crude at $83.40",   # normal price tick
    ...
)
```

### 2.4 Sanctions

Every sanctions change (diff result) is pushed — sanctions are always significant:

```python
NormalizedSignal(
    source="sanctions",
    priority_hint="HIGH",
    force_synthesis=True,        # sanctions always bypass triage
    entity_refs=["NIOC", "MT Destiny"],   # sanctioned entity + its operator if known
    summary="OFAC SDN: MT Destiny (MMSI 477553000) added, operator NIOC, 280K DWT",
    payload={
        "list":          "OFAC",          # SanctionsPayload.list
        "change":        "add",           # SanctionsPayload.change (add | remove)
        "subject":       "MT Destiny",    # SanctionsPayload.subject
        "subject_type":  "vessel",        # vessel | entity | person
        "effective_date": "2026-02-23",
        # Additional operational metadata (open payload):
        "mmsi":          "477553000",
        "dwt":           280000,
        "operator":      "NIOC",
    },
)
```

---

## 3. How System 1 Knows Which Wiki File / Graph Node to Write To

**System 1 does not choose the wiki file.** It populates `entity_refs` with display names, and SAGE core resolves those names to graph nodes and wiki files.

### 3.1 The resolution chain

```
signal.entity_refs = ["Strait of Hormuz"]
         │
         ▼
triage.py → _get_entity_embedding("Strait of Hormuz")
         │   → searches Graphiti for existing node
         │   → if found: uses stored node embedding
         │   → if not: embeds the display_name string
         │
         ▼
ingest_signal() → synthesize(signal=signal, entity="Strait of Hormuz")
         │
         ▼
synthesis._wiki_path("Strait of Hormuz")
  → slug = "strait_of_hormuz"
  → path = /app/wiki/strait_of_hormuz.md
```

The mapping is **display_name → slug → wiki file → Graphiti node**. All four are derived from the same `entity_refs` string.

### 3.2 Entity naming rules — CRITICAL

System 1 sub-agents MUST use canonical display names that match the KB's entity ontology. Inconsistent naming creates duplicate nodes ("Hormuz", "Strait of Hormuz", "the Strait") instead of updating the same one.

**Canonical names System 1 must use:**

| Category | Canonical name | Do NOT use |
|---|---|---|
| Corridors | `"Strait of Hormuz"`, `"Bab-el-Mandeb"`, `"Suez Canal"`, `"Strait of Malacca"` | "Hormuz", "the Strait", "HOZ" |
| Suppliers | `"Saudi Aramco"`, `"NIOC"`, `"ADNOC"`, `"Rosneft"`, `"Iraqi Oil Ministry"` | "Aramco", "Iran", "Saudi Arabia" |
| Refineries | `"Jamnagar"`, `"Mangaluru"`, `"Paradip"`, `"Vizag Refinery"` | "Reliance", "HPCL Mangaluru" |
| Ports | `"Vadinar"`, `"Yanbu"`, `"Sikka"`, `"Fujairah"` | "Vadinar Port", "Port of Yanbu" |
| SPR sites | `"Vizag SPR"`, `"Mangaluru SPR"`, `"Padur SPR"` | "Vizag", "ISPRL Mangaluru" |
| Authorities | `"OFAC"`, `"EU"`, `"UN"` | "US Treasury", "European Union" |

**Where to find the canonical list:** `knowledge/schema/entities.py` — the `ENTITY_TYPES` docstrings contain example names that the extraction LLM uses for entity resolution. System 1 sub-agents should use the same example names.

### 3.3 Multiple entity_refs

When a signal concerns multiple entities, list them all. SAGE synthesizes a page for each:

```python
entity_refs=["Strait of Hormuz", "IRGC", "Saudi Aramco"]
# → synthesize() runs three times, one per entity
# → three wiki pages are updated
# → all three get MENTIONS edges to the same episode node
```

If unsure which entities a signal concerns, use a shorter list and let Graphiti's extraction LLM find additional entities in the episode text. Better to give one correct entity_ref than three guesses.

---

## 4. The Four Streams — What Hits Each Store

The four streams are **not symmetric**. News and sanctions produce prose. AIS and prices produce factors. Treating them identically burns cost and produces meaningless synthesis.

### 4.1 Decision matrix

| Source | Triage outcome | Store 1 (Episode) | Wiki (narrative) | Store 2 (Graph: nodes + edges) | Store 3 (Vectors) |
|---|---|---|---|---|---|
| **news / gdelt** | Similarity-based (0.72+→synthesize) | Always, full body | ✅ Full synthesis — PRIMARY wiki driver | Entities + GeoEvent nodes, `factor_gdelt` on RISK_STATE | Synthesized Current Assessment embedded |
| **ais** | force_synthesis=False; NEVER triggers prose synthesis | Per anomaly event (not raw pings) | ❌ Never direct; feeds `factor_ais` + Signal Basis line only | GeoEvent node + `factor_ais` update on RISK_STATE | Via the entity page that AIS triggered re-synthesis of |
| **price** | force_synthesis=True (changepoints only) | Per changepoint only | ❌ Never direct; feeds `factor_price` + corroborating clause | `factor_price` on RISK_STATE, market state note | Via updated entity pages |
| **sanctions** | force_synthesis=True always | Always | ✅ Light synthesis — implications-focused | Heavy: Vessel/Supplier nodes, SANCTIONED_BY edges, `factor_sanctions` | Updated entity pages |

### 4.2 Source-aware routing rule

The triage gate does NOT currently distinguish source type — this is a known implementation gap (see §6.1). Until fixed, System 1 sub-agents can enforce the correct behavior by setting `force_synthesis` carefully:

| Source | `force_synthesis` | `priority_hint` | Expected outcome |
|---|---|---|---|
| `news` / `gdelt` | `False` (let triage decide) | `HIGH` / `MED` | High-quality articles → synthesize; noise → extract/store |
| `ais` | `False` ALWAYS | `HIGH` | Triage will route to extract (structural fact) — not synthesize |
| `price` | `True` only on changepoints; `False` otherwise | `HIGH` on change | Changepoints → synthesize with source-routing fix; normal ticks → never pushed |
| `sanctions` | `True` always | `HIGH` | Bypasses triage → synthesize → light implications prose |

---

## 5. The Enforced Wiki Format

**Every wiki page MUST conform to this exact schema.** Without enforcement, LLM-generated pages diverge on every write, embeddings become inconsistent, and memo assembly breaks.

```markdown
---
entity_id: corridor_hormuz
entity_type: Corridor
risk_score: 0.67
risk_band: ELEVATED
factors:
  ais: 0.31
  gdelt: 0.19
  price: 0.12
  sanctions: 0.05
last_updated: 2026-02-23T14:42:00Z
valid_at: 2026-02-23T14:00:00Z
source_episodes:
  - ep_8841
  - ep_8843
  - ep_8847
coordinates:
  lat: 26.5
  lon: 56.4
---

## Current Assessment

The Strait of Hormuz remains at elevated risk as of 14:42 UTC. IRGC vessels are
shadowing a 4-tanker convoy near Larak Island, corroborated by 4 AIS dark gaps
and a rising war-risk premium (0.41%). Vessel traffic has not yet been interrupted,
but operational disruption risk within 24 hours is assessed at 65%.

## Contradiction Note

Reuters reports surface traffic normal; AIS detector shows 4 dark gaps. The
discrepancy is consistent with shadow-fleet vessels (non-reporting, MMSI-spoofing)
operating alongside the visible convoy — the two measurements capture different
fleet segments.

## Historical Pattern

Matches the February 2012 IRGC naval exercise pattern: 3-day vessel-shadowing
phase preceded a 72-hour corridor partial closure. 78% similar to current signal
sequence.

## Affected Entities

- Jamnagar (HIGH exposure — 42% of crude via Hormuz)
- Vadinar (HIGH — primary discharge port for Gulf crude)
- NIOC (ELEVATED — 3 additional vessels sanctioned this week)

## Signal Basis

- AIS: 4 dark-vessel gaps, Larak area, 14:30 UTC [ep_8841]
- GDELT: Reuters article, tone -4.2, severity 0.72 [ep_8843]
- Price: Brent BOCD breakpoint, war-risk 0.41% [ep_8847]
```

### 5.1 Frontmatter rules

**All frontmatter fields are required and machine-parsed by SAGE.** If synthesis output is missing any field, the write is rejected and the old page is kept:

| Field | Type | Rule |
|---|---|---|
| `entity_id` | string | `{entity_type}_{slug}` — e.g. `corridor_hormuz` |
| `entity_type` | string | One of the 11 C2 entity types exactly |
| `risk_score` | float | Current fused score 0..1; populated by `write_risk_state()` |
| `risk_band` | string | `CALM` \| `WATCH` \| `ELEVATED` \| `ACTION` \| `CRITICAL` |
| `factors` | dict | `ais`, `gdelt`, `price`, `sanctions` — all four, 0..1 each |
| `last_updated` | ISO8601 | When this page was last written |
| `valid_at` | ISO8601 | The `observed_at` of the signal that triggered synthesis |
| `source_episodes` | list[str] | Episode UUIDs whose content produced this page (for citation) |
| `coordinates` | dict | `lat`, `lon` — optional, required for Corridor/Port/Refinery |

### 5.2 Body section rules

| Section | When present | Length |
|---|---|---|
| `## Current Assessment` | **Always** — mandatory | 2-3 sentences only. This is the text embedded in Store 3. |
| `## Contradiction Note` | Only when sources disagree | Explain WHY, not just WHAT |
| `## Historical Pattern` | When a precedent exists | One paragraph, with similarity estimate |
| `## Affected Entities` | Always for HIGH-risk entities | Bulleted, with exposure level |
| `## Signal Basis` | Always | One line per contributing signal with episode ID |

### 5.3 Synthesis prompt template (enforced)

The synthesis prompt must pass the template to the LLM and validate the output against it. System 1 does not write this prompt — SAGE's `synthesis.py` does. But System 1 needs to know that **the signal summary becomes the "NEW SIGNAL" block**, so the summary must be high-quality prose:

```
CURRENT PAGE:
{current_wiki_page}         ← loaded from /wiki by synthesis.py

NEW SIGNAL:
Source: news | Priority: HIGH | Observed: 2026-02-23 14:30 UTC
Reuters: IRGC vessels shadow tanker convoy near Larak Island...

Produce an updated page in EXACTLY this format:
---
entity_id: {entity_id}
entity_type: {entity_type}
risk_score: {current_risk_score}
risk_band: {current_risk_band}
...
---

## Current Assessment
[2-3 sentences maximum. The ONLY paragraph that gets embedded.]
...
```

---

## 6. Critical Mismatches Between Current Implementation and This Spec

These are bugs or missing features in the current KB codebase that System 1 sub-agents must be aware of. Some require KB fixes; some require System 1 workarounds until fixed.

---

### 6.1 ❌ CRITICAL: Triage gate is source-blind

**File:** `knowledge/triage.py:49`  
**Problem:** `triage()` makes no distinction between `signal.source` values. An AIS anomaly event with `entity_refs=["Strait of Hormuz"]` and a high cosine similarity will be routed to `"synthesize"` — triggering Nova Pro to write narrative prose about a single AIS detection. This is the exact mistake the design spec warns about: burning cost and producing "meaningless prose."

**Current code:**
```python
async def triage(signal: NormalizedSignal) -> tuple[TriageDecision, float]:
    if signal.force_synthesis:
        return "synthesize", 1.0
    # ... cosine similarity only — no source check
    if max_sim > SYNTH_THRESHOLD:
        return "synthesize", max_sim   # ← AIS signal lands here if sim > 0.72
```

**Required fix (in `knowledge/triage.py`):**
```python
# Sources that should NEVER produce standalone wiki prose
_NUMERIC_SOURCES = {"ais", "price"}
# Sources that always get light synthesis (implications-focused)
_ALWAYS_SYNTH_SOURCES = {"sanctions"}

async def triage(signal: NormalizedSignal) -> tuple[TriageDecision, float]:
    if signal.force_synthesis and signal.source not in _NUMERIC_SOURCES:
        return "synthesize", 1.0
    if signal.source in _NUMERIC_SOURCES:
        # AIS and price: always extract (update graph factors), never synthesize wiki
        return "extract", 1.0 if signal.force_synthesis else 0.5
    if signal.source in _ALWAYS_SYNTH_SOURCES:
        return "synthesize", 1.0
    # news/gdelt: similarity-based
    ...
```

**System 1 workaround until fixed:** AIS and price sub-agents must set `priority_hint="MED"` and ensure their summaries are brief (not article-like prose). A cosine similarity above 0.72 on a short AIS summary is unlikely but not impossible when the entity name is in the summary.

---

### 6.2 ❌ CRITICAL: Wiki format has no frontmatter — machine-readable fields are absent

**File:** `knowledge/synthesis.py:135` (`render_wiki_page`)  
**Problem:** The current wiki format is:
```
# Strait of Hormuz

_Last updated: 2026-02-23 14:42 UTC_

[synthesized prose]
```
There is NO YAML frontmatter. This means:
- `risk_score`, `risk_band`, `factors`, `valid_at`, `source_episodes` are nowhere in the file
- The monitor cannot read the current score from the wiki (it reads the graph instead)
- Synthesis cannot validate its own output against a schema
- System 5 copilot cannot parse structured fields from a wiki page
- The `write_risk_state()` function appends free-form markdown rather than updating a structured field

**Required fix (in `knowledge/synthesis.py`):**
```python
import yaml

def render_wiki_page(
    entity: str,
    synthesized_text: str,
    entity_type: str = "Unknown",
    risk_score: float = 0.0,
    risk_band: str = "calm",
    factors: dict | None = None,
    valid_at: str | None = None,
    source_episodes: list[str] | None = None,
    coordinates: dict | None = None,
) -> str:
    stamp = datetime.now(timezone.utc).isoformat()
    slug  = entity.lower().replace(" ", "_").replace("/", "-")
    fm = {
        "entity_id":      f"{entity_type.lower()}_{slug}",
        "entity_type":    entity_type,
        "risk_score":     round(risk_score, 4),
        "risk_band":      risk_band.upper(),
        "factors":        factors or {"ais": 0.0, "gdelt": 0.0, "price": 0.0, "sanctions": 0.0},
        "last_updated":   stamp,
        "valid_at":       valid_at or stamp,
        "source_episodes": source_episodes or [],
    }
    if coordinates:
        fm["coordinates"] = coordinates
    frontmatter = yaml.dump(fm, default_flow_style=False, allow_unicode=True)
    return f"---\n{frontmatter}---\n\n{synthesized_text}"
```

**Impact on System 1:** Sub-agents are unaffected — they don't write wiki files. But the information that populates the frontmatter must come from `write_risk_state()` and `ingest_signal()`, which are KB responsibilities.

---

### 6.3 ❌ `write_risk_state()` appends instead of updating frontmatter

**File:** `knowledge/api/write.py:289`  
**Problem:** Every time `write_risk_state()` is called (every 30s per entity), it appends a new `---\n**Risk Assessment**` block to the wiki file. After 24 hours, the Hormuz wiki page would have 2,880 appended sections. It grows without bound, the current score is ambiguous (it's in multiple blocks), and parsing is impossible.

**Current code:**
```python
current = load_wiki_page(entity)
risk_section = f"\n\n---\n**Risk Assessment** _{now.strftime('%Y-%m-%d %H:%M UTC')}_\n\n{episode_text}"
write_wiki_page(entity, current.rstrip() + risk_section)
```

**Required fix:** `write_risk_state()` should parse the frontmatter and update `risk_score`, `risk_band`, `factors`, `valid_at` in place — not append. The page body (Current Assessment, etc.) should only change when full synthesis runs.

```python
def _update_wiki_risk_frontmatter(entity: str, score: float, band: str,
                                   factors: dict, valid_at: str) -> None:
    """Update only the frontmatter fields related to risk score. Body unchanged."""
    content = load_wiki_page(entity)
    if content.startswith("---"):
        # Parse existing frontmatter
        end = content.index("---", 3)
        fm_text = content[3:end]
        body    = content[end+3:]
        fm = yaml.safe_load(fm_text) or {}
    else:
        fm, body = {}, content

    fm["risk_score"]  = round(score, 4)
    fm["risk_band"]   = band.upper()
    fm["factors"]     = factors
    fm["valid_at"]    = valid_at
    fm["last_updated"] = datetime.now(timezone.utc).isoformat()

    new_content = f"---\n{yaml.dump(fm)}---\n{body}"
    write_wiki_page(entity, new_content)
```

---

### 6.4 ❌ `source_episodes` not tracked anywhere

**File:** `knowledge/api/write.py`, `knowledge/synthesis.py`  
**Problem:** The wiki frontmatter spec requires `source_episodes: [ep_8841, ep_8843]` — the list of episode UUIDs whose content produced the current assessment. Currently no code tracks which episode IDs contributed to which wiki page. This means:
- System 5 copilot cannot cite the source of a factual claim on a wiki page
- There is no audit trail linking wiki content to raw signals

**Required fix:** `ingest_signal()` should maintain a `source_episodes` list per entity (in-memory or Redis), and `render_wiki_page()` should include it. `synthesize()` should receive the episode UUID from `add_episode()` and pass it to `render_wiki_page()`.

**System 1 impact:** None — this is a KB-internal tracking issue. But System 1 should ensure `raw_ref` is populated on every signal (it's used for audit even if `source_episodes` isn't yet tracked).

---

### 6.5 ⚠ Entity resolution is not validated at ingestion

**File:** `knowledge/triage.py:106` (`_get_entity_embedding`)  
**Problem:** When System 1 writes `entity_refs=["Hormuz"]` (wrong) instead of `"Strait of Hormuz"` (canonical), `triage()` embeds the string `"Hormuz"` and finds a high cosine similarity to the Hormuz corridor entity. But `ingest_signal()` then calls `synthesize(signal, entity="Hormuz")` which writes a wiki file at `/wiki/hormuz.md` — a new file, separate from `/wiki/strait_of_hormuz.md`. A new, duplicate entity node would also be extracted in Graphiti.

**There is no resolution step** between `signal.entity_refs` and the canonical entity name.

**Required fix:** A canonical entity name resolver should run on `entity_refs` before synthesis, mapping free-form names to the canonical display names:
```python
# In knowledge/entity_resolver.py (to be built)
CANONICAL_NAMES = {
    "hormuz": "Strait of Hormuz",
    "the strait": "Strait of Hormuz",
    "aramco": "Saudi Aramco",
    "nioc": "NIOC",   # this one is already canonical
    ...
}

def resolve_entity_refs(entity_refs: list[str]) -> list[str]:
    return [CANONICAL_NAMES.get(e.lower(), e) for e in entity_refs]
```

**System 1 workaround:** Always use the canonical names from §3.2 of this document. Until an entity resolver is built, the KB will silently create duplicate nodes on name mismatch.

---

### 6.6 ⚠ AIS signals with `force_synthesis=True` would bypass the source-routing fix

**File:** `knowledge/ingest_queue.py:239`  
**Problem:** The ingest queue fires `force_synthesis=True` on HIGH signals via `_maybe_sandbox_fork()`. If an AIS signal has `priority_hint="HIGH"` and `force_synthesis=True`, it bypasses triage entirely and goes straight to narrative synthesis — wrong behavior.

**Required fix:** The source-blind triage fix in §6.1 must also guard the `force_synthesis=True` path. `force_synthesis` should be blocked for `source in {"ais", "price"}` regardless of priority.

**System 1 workaround:** AIS sub-agent must NEVER set `force_synthesis=True`. Use `priority_hint="HIGH"` to signal urgency without bypassing triage routing.

---

### 6.7 ℹ `write_risk_state()` is called by `ingest_queue` — System 1 does NOT call it

**File:** `knowledge/ingest_queue.py:350`  
**Clarification:** Some System 1 builders may expect to call `write_risk_state()` directly from the sub-agent after running the fusion model. Do NOT do this. The call sequence is:

```
System 1 sub-agent
  → push_signal(NormalizedSignal)            [sub-agent responsibility]
  → Redis queue (sage:ingest)
  → ingest_queue.run_consumer_loop()         [KB responsibility]
  → ingest_signal()                          [KB, per signal]
  → _run_fusion_for_entity()                 [KB, per entity, per flush window]
  → write_risk_state()                       [KB, after fusion]
```

System 1 sub-agents push signals. The KB aggregates them, runs fusion, and writes the risk state. Sub-agents never call `write_risk_state()` or `add_episode()` directly.

---

## 7. What System 1 Can Read From the KB

System 1 sub-agents generally do not need to read from the KB — they are producers, not consumers. But there are two legitimate read operations:

### 7.1 Reading current risk score (for priority calibration)

If a sub-agent wants to know whether its entity is already at high risk before deciding `priority_hint`:

```python
from knowledge.api.read import get_risk_scores

scores = await get_risk_scores()
hormuz = next((s for s in scores if s.entity == "Strait of Hormuz"), None)
if hormuz and hormuz.score > 0.45:
    priority_hint = "HIGH"
```

This is **optional** — the triage gate handles prioritization correctly without it. Use it only if a sub-agent has its own priority logic that benefits from knowing current KB state.

### 7.2 Reading existing wiki page (for context-aware summary generation)

A sub-agent could read the current wiki page to write a better `signal.summary`:

```python
from knowledge.api.read import get_wiki_page

page = await get_wiki_page("Strait of Hormuz")
# Use page.content to inform signal.summary with relevant context
```

This is generally **not recommended** — it couples sub-agents to the KB read path and adds latency. Sub-agents should produce summaries from their own domain knowledge, not from the KB.

---

## 8. Build Checklist for Each Sub-Agent

Before connecting a sub-agent to the KB:

- [ ] Sub-agent never calls `ingest_signal()` or `write_risk_state()` directly
- [ ] Sub-agent calls only `push_signal(NormalizedSignal)` via `knowledge.ingest_queue`
- [ ] All `entity_refs` use canonical display names from §3.2
- [ ] AIS sub-agent: pushes per anomaly event, NOT per position ping; `force_synthesis=False` always
- [ ] Price sub-agent: pushes ONLY on BOCD changepoints / regime shifts; `force_synthesis=True` on changepoints
- [ ] Sanctions sub-agent: `force_synthesis=True` always
- [ ] News/GDELT sub-agent: `force_synthesis=False`; let triage decide; ensure `source_url` is set
- [ ] `payload` conforms to the per-source schema in C1 §3.1 of the schema spec
- [ ] `raw_ref` is set to the S3 key or DB ID of the verbatim raw record
- [ ] `observed_at` is the event time in the world, NOT when the sub-agent emitted
- [ ] `signal_id` is a ULID or UUID — unique per signal, not per entity

---

## 9. KB Fixes Required Before System 1 Integration Is Reliable

Priority order for KB team to fix before System 1 is connected:

| Priority | Fix | File | Symptom if not fixed |
|---|---|---|---|
| P0 | Source-aware routing in triage (§6.1) | `knowledge/triage.py` | AIS/price signals trigger expensive Nova Pro synthesis; meaningless wiki pages written |
| P0 | Wiki frontmatter schema (§6.2) | `knowledge/synthesis.py` | Monitor, copilot, System 5 cannot parse structured data from wiki pages |
| P1 | `write_risk_state` updates frontmatter, not append (§6.3) | `knowledge/api/write.py` | Wiki pages grow unboundedly; current risk score is ambiguous in file |
| P1 | Entity name resolver (§6.5) | `knowledge/entity_resolver.py` (new) | Duplicate nodes created for same entity with variant names |
| P2 | `source_episodes` tracking (§6.4) | `knowledge/api/write.py`, `knowledge/synthesis.py` | No citation audit trail in wiki pages |
| P2 | Block `force_synthesis=True` for AIS/price (§6.6) | `knowledge/ingest_queue.py` | AIS HIGH signals could bypass triage source-routing fix |

---

## 10. Entity Resolution — Which Node and Which .md File

This is the make-or-break detail for the whole knowledge base. Get it wrong and you either create duplicate nodes (two "Hormuz" pages, two "Strait of Hormuz" graph nodes) or write to the wrong entity entirely.

There are **two separate resolution mechanisms** operating at two different layers. Conflating them is where confusion creeps in.

- **Layer 1 — Wiki routing (SAGE layer):** which `.md` file to load before synthesis runs
- **Layer 2 — Graph routing (Graphiti layer):** which entity node the synthesized episode attaches to

These use different mechanisms because they operate on different things. Graphiti resolves from extracted text using embeddings + LLM. The wiki layer must resolve *before* synthesis runs so it can load the right current page to reconcile against. Wiki routing happens first.

---

### 10.1 Layer 1 — Wiki Routing (SAGE Layer, Before Synthesis)

**The critical design point:** `entity_refs` are attached during System 1's detection, not guessed at synthesis time. Each stream's detector knows what it's looking at before the signal ever reaches the KB:

| Stream | How `entity_refs` is populated | Mechanism |
|---|---|---|
| **AIS** | H3 cell → entity lookup in canonical registry | `CELL_TO_ENTITY["8a2a1072b59ffff"] == "corridor_hormuz"` |
| **Price** | Instrument → entity mapping in canonical registry | `INSTRUMENT_TO_ENTITY["BZ=F"] == ["corridor_hormuz", "global_market"]` |
| **Sanctions** | Named entity in structured OFAC/EU/UN record | Literal string extraction — "MT Destiny" is in the XML |
| **News / GDELT** | Nova Micro extraction pass against registry | LLM returns candidate names; matched against registry aliases + embedding fallback |

By the time any signal reaches `ingest_signal()`, `entity_refs` is already populated. The wiki router then does something simple and deterministic:

```python
# In knowledge/api/write.py → ingest_signal(), synthesis path
for entity_id in signal.entity_refs:
    page = load_wiki(entity_id)          # /wiki/{entity_id}.md
    synthesized_text = await synthesize(signal, entity=entity_id, current_page=page)
    save_wiki(entity_id, synthesized_text)
```

The `.md` file is keyed by `entity_id` directly. `corridor_hormuz` → `/wiki/corridor_hormuz.md`. There is no ambiguity at this layer — resolution already happened in the detector.

**Current KB mismatch:** The KB currently uses `entity` (display name string like `"Strait of Hormuz"`) as the wiki key, deriving the slug via `entity.lower().replace(" ", "_")`. This works only if every sub-agent uses the exact same string. The canonical registry (§10.3) replaces this with `entity_id` as the key — a stable, lowercase, underscore-separated identifier that doesn't depend on display-name formatting.

---

### 10.2 Layer 2 — Graph Routing (Graphiti Layer, During Write)

Once synthesis runs and `add_episode()` is called with the synthesized text, Graphiti does its own entity resolution independently. It reads the synthesized text, extracts entities, and for each one checks whether it already exists in the graph using embedding similarity + an LLM confirmation step.

**The alignment problem:** If the wiki router decided this signal is about `corridor_hormuz` but Graphiti's extraction creates a new "Hormuz Strait" node because it didn't recognise the existing "Strait of Hormuz" node, the two stores have diverged. The wiki updated one entity; the graph created a different one.

**Three mechanisms keep them aligned:**

1. **Canonical name in the synthesized text.** When synthesis runs for `corridor_hormuz`, the synthesized text always opens with `"Strait of Hormuz"` (the canonical display name from the registry). Graphiti's extractor sees the canonical form, not an alias. This is the primary alignment mechanism.

2. **Strong type docstrings.** The `Corridor` entity docstring says: *"e.g. 'Strait of Hormuz', 'Bab-el-Mandeb', 'Suez Canal'"*. This example acts as an anchor for Graphiti's classifier — it collapses "Hormuz", "the Strait", "SoH" onto the same node because it's seen the canonical name as an example.

3. **Explicit entity assertion (robust path).** Because the wiki router already resolved the entity from the registry, SAGE doesn't have to let Graphiti rediscover it from scratch. The synthesis text can assert the entity explicitly:

```python
# In synthesize() — always open with the canonical name so Graphiti anchors correctly
episode_text = (
    f"Strait of Hormuz — intelligence update {observed_at}.\n"   # canonical name first
    f"{synthesized_assessment}\n"
    f"{risk_block}\n"
)
```

If Graphiti still creates a duplicate despite this (a known Graphiti footgun on first-time extraction), `add_triplet()` can be used to explicitly assert the entity by its known UUID — but that requires knowing the UUID, which means a prior graph lookup. For the hackathon, the canonical-name-first approach is sufficient.

---

### 10.3 The Canonical Entity Registry — The Shared Key Space

For both layers to agree, you need a single source of truth for entity identity. This is a piece that must be built. Without it, alias resolution is ad-hoc and sub-agents will silently create duplicate entities.

**Location:** `knowledge/registry.py` (new file to build)

**Structure:**

```python
# knowledge/registry.py
from dataclasses import dataclass, field

@dataclass
class EntityRegistryEntry:
    entity_id:      str          # stable key: e.g. "corridor_hormuz"
    entity_type:    str          # C2 type: "Corridor" | "Supplier" | ...
    canonical_name: str          # exact string used in wiki files and graph episodes
    aliases:        list[str]    # all variants that resolve to this entity
    h3_cells:       list[str] = field(default_factory=list)   # AIS routing (Corridor/Port only)
    instruments:    list[str] = field(default_factory=list)   # price routing (market entities)
    coordinates:    dict     = field(default_factory=dict)    # lat/lon for spatial entities

REGISTRY: dict[str, EntityRegistryEntry] = {
    # ── Corridors ──────────────────────────────────────────────────────────────
    "corridor_hormuz": EntityRegistryEntry(
        entity_id="corridor_hormuz",
        entity_type="Corridor",
        canonical_name="Strait of Hormuz",
        aliases=["Hormuz", "Hormuz Strait", "the Strait", "SoH", "Strait of Hormuz"],
        h3_cells=["8a2a1072b59ffff", "8a2a1072b4fffff", "8a2a10728b7ffff"],   # Larak + Hormuz mouth
        instruments=["BZ=F", "CL=F"],    # Brent and WTI price changepoints affect Hormuz
        coordinates={"lat": 26.5, "lon": 56.4},
    ),
    "corridor_bab_el_mandeb": EntityRegistryEntry(
        entity_id="corridor_bab_el_mandeb",
        entity_type="Corridor",
        canonical_name="Bab-el-Mandeb",
        aliases=["Bab el Mandeb", "BAM", "Red Sea Strait", "Mandeb"],
        h3_cells=["8a2a4d64b0fffff", "8a2a4d64b27ffff"],
        instruments=["BZ=F"],
        coordinates={"lat": 12.5, "lon": 43.3},
    ),
    "corridor_suez": EntityRegistryEntry(
        entity_id="corridor_suez",
        entity_type="Corridor",
        canonical_name="Suez Canal",
        aliases=["Suez", "the Canal", "SUMED", "Suez Canal Authority"],
        h3_cells=["8a3900000007fff"],
        coordinates={"lat": 30.7, "lon": 32.3},
    ),
    # ── Suppliers ──────────────────────────────────────────────────────────────
    "supplier_aramco": EntityRegistryEntry(
        entity_id="supplier_aramco",
        entity_type="Supplier",
        canonical_name="Saudi Aramco",
        aliases=["Aramco", "Saudi Arabian Oil Company", "Aramco Trading"],
    ),
    "supplier_nioc": EntityRegistryEntry(
        entity_id="supplier_nioc",
        entity_type="Supplier",
        canonical_name="NIOC",
        aliases=["National Iranian Oil Company", "Iran National Oil", "NIOC Trading"],
    ),
    "supplier_adnoc": EntityRegistryEntry(
        entity_id="supplier_adnoc",
        entity_type="Supplier",
        canonical_name="ADNOC",
        aliases=["Abu Dhabi National Oil Company", "Abu Dhabi NOC"],
    ),
    "supplier_rosneft": EntityRegistryEntry(
        entity_id="supplier_rosneft",
        entity_type="Supplier",
        canonical_name="Rosneft",
        aliases=["Rosneft Oil", "PJSC Rosneft"],
    ),
    "supplier_iraqoil": EntityRegistryEntry(
        entity_id="supplier_iraqoil",
        entity_type="Supplier",
        canonical_name="Iraqi Oil Ministry",
        aliases=["SOMO", "State Organisation for Marketing of Oil", "Iraq oil"],
    ),
    # ── Refineries ─────────────────────────────────────────────────────────────
    "refinery_jamnagar": EntityRegistryEntry(
        entity_id="refinery_jamnagar",
        entity_type="Refinery",
        canonical_name="Jamnagar",
        aliases=["Reliance Jamnagar", "RIL Jamnagar", "Jamnagar Refinery"],
        coordinates={"lat": 22.5, "lon": 70.0},
    ),
    "refinery_mangaluru": EntityRegistryEntry(
        entity_id="refinery_mangaluru",
        entity_type="Refinery",
        canonical_name="Mangaluru",
        aliases=["MRPL Mangaluru", "Mangalore Refinery", "MRPL"],
        coordinates={"lat": 12.9, "lon": 74.8},
    ),
    "refinery_paradip": EntityRegistryEntry(
        entity_id="refinery_paradip",
        entity_type="Refinery",
        canonical_name="Paradip",
        aliases=["IOCL Paradip", "Paradip Refinery", "IOC Paradip"],
        coordinates={"lat": 20.3, "lon": 86.7},
    ),
    # ── Ports ──────────────────────────────────────────────────────────────────
    "port_vadinar": EntityRegistryEntry(
        entity_id="port_vadinar",
        entity_type="Port",
        canonical_name="Vadinar",
        aliases=["Vadinar Port", "Vadinar Terminal", "Reliance Vadinar"],
        coordinates={"lat": 22.5, "lon": 69.8},
    ),
    "port_yanbu": EntityRegistryEntry(
        entity_id="port_yanbu",
        entity_type="Port",
        canonical_name="Yanbu",
        aliases=["Yanbu Terminal", "Yanbu Al Bahr", "Yanbu port"],
        coordinates={"lat": 24.1, "lon": 38.1},
    ),
    "port_sikka": EntityRegistryEntry(
        entity_id="port_sikka",
        entity_type="Port",
        canonical_name="Sikka",
        aliases=["Sikka Port", "Sikka Terminal", "IOCL Sikka"],
        coordinates={"lat": 22.6, "lon": 69.9},
    ),
    # ── SPR Caverns ────────────────────────────────────────────────────────────
    "spr_vizag": EntityRegistryEntry(
        entity_id="spr_vizag",
        entity_type="SPRCavern",
        canonical_name="Vizag SPR",
        aliases=["Visakhapatnam SPR", "Vizag cavern", "ISPRL Vizag"],
        coordinates={"lat": 17.7, "lon": 83.3},
    ),
    "spr_mangaluru": EntityRegistryEntry(
        entity_id="spr_mangaluru",
        entity_type="SPRCavern",
        canonical_name="Mangaluru SPR",
        aliases=["Padur SPR Mangaluru", "ISPRL Mangaluru", "Mangalore SPR"],
        coordinates={"lat": 12.9, "lon": 74.8},
    ),
    "spr_padur": EntityRegistryEntry(
        entity_id="spr_padur",
        entity_type="SPRCavern",
        canonical_name="Padur SPR",
        aliases=["Padur cavern", "ISPRL Padur", "Padur storage"],
        coordinates={"lat": 13.1, "lon": 74.7},
    ),
    # ── Authorities ────────────────────────────────────────────────────────────
    "authority_ofac": EntityRegistryEntry(
        entity_id="authority_ofac",
        entity_type="Authority",
        canonical_name="OFAC",
        aliases=["US Treasury OFAC", "Office of Foreign Assets Control", "Treasury SDN"],
    ),
    "authority_eu": EntityRegistryEntry(
        entity_id="authority_eu",
        entity_type="Authority",
        canonical_name="EU",
        aliases=["European Union", "EU sanctions", "Council of the EU"],
    ),
    "authority_un": EntityRegistryEntry(
        entity_id="authority_un",
        entity_type="Authority",
        canonical_name="UN",
        aliases=["United Nations", "UN Security Council", "UNSC"],
    ),
}

# ── Lookup indices (built once at startup) ──────────────────────────────────────

# H3 cell → entity_id  (AIS routing)
H3_TO_ENTITY: dict[str, str] = {
    cell: entry.entity_id
    for entry in REGISTRY.values()
    for cell in entry.h3_cells
}

# Instrument → list[entity_id]  (price routing)
INSTRUMENT_TO_ENTITIES: dict[str, list[str]] = {}
for entry in REGISTRY.values():
    for inst in entry.instruments:
        INSTRUMENT_TO_ENTITIES.setdefault(inst, []).append(entry.entity_id)

# Alias (lowercase) → entity_id  (sanctions + news resolution)
ALIAS_TO_ENTITY: dict[str, str] = {
    alias.lower(): entry.entity_id
    for entry in REGISTRY.values()
    for alias in [entry.canonical_name] + entry.aliases
}


def resolve_name(name: str) -> str | None:
    """Resolve a free-form name to an entity_id, or None if not in registry."""
    return ALIAS_TO_ENTITY.get(name.lower())


def resolve_h3(h3_cell: str) -> str | None:
    """Resolve an H3 cell index to an entity_id, or None if cell not tracked."""
    return H3_TO_ENTITY.get(h3_cell)


def resolve_instrument(instrument: str) -> list[str]:
    """Resolve a price instrument to the entity_ids it affects."""
    return INSTRUMENT_TO_ENTITIES.get(instrument, [])


def canonical_name(entity_id: str) -> str:
    """Return the canonical display name for an entity_id."""
    return REGISTRY[entity_id].canonical_name
```

---

### 10.4 How Each Stream Populates `entity_refs` Using the Registry

```python
# ── AIS sub-agent ─────────────────────────────────────────────────────────────
from knowledge.registry import resolve_h3, canonical_name

entity_id = resolve_h3("8a2a1072b59ffff")   # → "corridor_hormuz"
if entity_id:
    signal = NormalizedSignal(
        entity_refs=[canonical_name(entity_id)],   # "Strait of Hormuz"
        ...
    )
```

```python
# ── Price sub-agent ───────────────────────────────────────────────────────────
from knowledge.registry import resolve_instrument, canonical_name

entity_ids = resolve_instrument("BZ=F")   # → ["corridor_hormuz", ...]
signal = NormalizedSignal(
    entity_refs=[canonical_name(eid) for eid in entity_ids],
    ...
)
```

```python
# ── Sanctions sub-agent ───────────────────────────────────────────────────────
from knowledge.registry import resolve_name, canonical_name

# Named entities come directly from structured OFAC/EU/UN XML
raw_name = "NIOC"                          # literal string from the XML record
entity_id = resolve_name(raw_name)
if entity_id:
    entity_refs = [canonical_name(entity_id)]
else:
    # New entity — add to registry (see §10.5) or use raw name for extraction only
    entity_refs = [raw_name]
```

```python
# ── News / GDELT sub-agent ───────────────────────────────────────────────────
# Step 1: Nova Micro extraction pass on the article
candidate_names = await nova_micro_extract_entities(article_text)
# returns e.g. ["IRGC", "Strait of Hormuz", "Larak Island", "MT Destiny"]

# Step 2: resolve against registry (alias lookup + embedding fallback)
from knowledge.registry import resolve_name, canonical_name, REGISTRY
from knowledge.triage import _embed_text, _cosine

entity_refs = []
for name in candidate_names:
    entity_id = resolve_name(name)   # alias lookup first (fast, deterministic)
    if entity_id:
        entity_refs.append(canonical_name(entity_id))
    else:
        # Embedding fallback: check cosine similarity against all canonical names
        name_emb = await _embed_text(name)
        best_sim, best_id = 0.0, None
        for eid, entry in REGISTRY.items():
            canon_emb = await _embed_text(entry.canonical_name)
            sim = _cosine(name_emb, canon_emb)
            if sim > best_sim:
                best_sim, best_id = sim, eid
        if best_sim > 0.88:            # high bar for embedding fallback
            entity_refs.append(canonical_name(best_id))
        # else: not a tracked entity — don't add to entity_refs (see §10.5)

signal = NormalizedSignal(entity_refs=entity_refs, ...)
```

---

### 10.5 The New-Entity Decision

Both layers need a rule for signals that mention something not in the registry. A new tanker appears in OFAC. A new port becomes relevant. An actor not previously tracked shows up in GDELT.

**Rule: admit a new entity only if it's connected to a tracked entity and crosses a significance bar.**

| Scenario | Decision | Action |
|---|---|---|
| Newly-sanctioned vessel operated by a tracked supplier (NIOC) | **Admit** | Add `vessel_{mmsi}` to registry; create node + wiki page; write `SANCTIONED_BY` edge |
| Minor port mentioned in passing in a news article, no connection to tracked entities | **Reject** | Signal stored as episode; entity not promoted; not added to registry |
| New geopolitical actor (e.g. new IRGC unit name) directly threatening a tracked corridor | **Admit** | Add `geoevent_{slug}` to registry; create `GeoEvent` node |
| Price instrument not in `INSTRUMENT_TO_ENTITIES` | **Reject** | Store raw; do not create entity |

The triage gate already enforces the significance bar indirectly: LOW-relevance signals that mention untracked entities get `"store"` or `"extract"` decisions, meaning their entities don't get wiki pages or graph nodes. HIGH signals that mention a genuinely new connected entity should trigger a registry addition. This is a manual step during the hackathon — the sanctions sub-agent adds newly-sanctioned vessels to the registry at ingest time because it always has enough structured data (MMSI, operator) to create a well-formed entry.

**How to add a new entity at runtime (sanctions example):**

```python
# In sensory_agent/sanctions.py — when a vessel not in registry is sanctioned
from knowledge.registry import REGISTRY, ALIAS_TO_ENTITY, EntityRegistryEntry

new_entry = EntityRegistryEntry(
    entity_id=f"vessel_{mmsi}",
    entity_type="Vessel",
    canonical_name=vessel_name,          # e.g. "MT Destiny"
    aliases=[vessel_name, mmsi, imo_number],
)
REGISTRY[new_entry.entity_id]  = new_entry
for alias in [vessel_name, mmsi]:
    ALIAS_TO_ENTITY[alias.lower()] = new_entry.entity_id
# Now push the signal with entity_refs=[vessel_name, "NIOC"] — both resolve correctly
```

---

### 10.6 Full Resolution Trace — AIS Anomaly End to End

```
1. AIS detector fires anomaly in H3 cell "8a2a1072b59ffff"
   → resolve_h3("8a2a1072b59ffff") == "corridor_hormuz"
   → signal.entity_refs = ["Strait of Hormuz"]

2. Signal pushed to Redis sage:ingest
   → ingest_queue.run_consumer_loop() pops it

3. triage() runs
   → source = "ais" → _NUMERIC_SOURCES → decision = "extract"
   → (no wiki synthesis for this signal alone)

4. _run_fusion_for_entity("Strait of Hormuz", [signal, ...])
   → weighted-sum fusion on accumulated AIS buffer
   → factor_ais = 0.31
   → write_risk_state("Strait of Hormuz", score=0.62, factor_ais=0.31, ...)

5. write_risk_state()
   → add_episode("corridor_hormuz_risk_...", "Strait of Hormuz risk level is assessed at...")
   → Graphiti extracts entity: "Strait of Hormuz" → matches existing Corridor node
     (canonical name in episode text = unambiguous match)
   → updates RISK_STATE edge: score=0.62, factor_ais=0.31, invalid_at=NULL
   → _update_wiki_risk_frontmatter("Strait of Hormuz", score=0.62, ...)
     → parses /wiki/strait_of_hormuz.md frontmatter
     → updates risk_score, risk_band, factors.ais in place
     → body (Current Assessment prose) unchanged until next synthesis

6. If a related news article also arrives in the same flush window:
   → triage() on news signal: similarity > 0.72 → "synthesize"
   → synthesize("Strait of Hormuz", current_page=load_wiki("strait_of_hormuz"))
   → LLM reconciles: "AIS dark gaps corroborate Reuters report"
   → wiki Current Assessment rewritten, source_episodes updated
   → add_episode("news_...", synthesized text) → Graphiti MENTIONS edge added
```

Both layers resolved to the same entity because:
- Wiki router used `entity_refs=["Strait of Hormuz"]` (from H3 registry lookup)
- Graphiti saw `"Strait of Hormuz"` as the first tokens of the episode body (canonical name)

---

### 10.7 Registry Wiring Checklist

- [ ] `knowledge/registry.py` created with all 20 seed entities (3 corridors, 5 suppliers, 3 refineries, 3 ports, 3 SPR caverns, 3 authorities)
- [ ] `H3_TO_ENTITY` populated with all H3 cells from `Corridor` entity `h3_cells` fields
- [ ] `INSTRUMENT_TO_ENTITIES` wired to corridors and market entities affected by each instrument
- [ ] `ALIAS_TO_ENTITY` covers all plausible variants for every tracked entity
- [ ] AIS sub-agent imports `resolve_h3()` and uses it exclusively for `entity_refs` population
- [ ] Price sub-agent imports `resolve_instrument()` and uses it exclusively
- [ ] Sanctions sub-agent imports `resolve_name()` and adds new vessels via registry mutation at ingest
- [ ] News sub-agent runs Nova Micro extraction, then `resolve_name()` + embedding fallback
- [ ] All sub-agents call `canonical_name(entity_id)` to populate `entity_refs` — never free-form strings
- [ ] `ingest_signal()` uses `entity_refs` as the wiki key directly (not re-inferring the entity from signal content)
- [ ] `synthesize()` opens every episode body with `canonical_name(entity_id)` so Graphiti anchors correctly
- [ ] New-entity admission logic: sanctions sub-agent mutates registry at runtime; others reject unrecognised entities
