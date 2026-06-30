# SAGE Context Bundle — Schema & Template

A **context bundle** is SAGE's foundational static knowledge: the supply-chain entities and the
structural relationships between them, with full provenance. It is the "pretrained knowledge" you
instantiate the system with before any live signal arrives.

```python
from knowledge.context import load_bundle
bundle = load_bundle("data/india-energy-2026.context")   # parse + validate
await bundle.instantiate(graphiti)                        # load into the graph
```

Swap the bundle to re-base SAGE's worldview — by **year** (`india-energy-2027.context`), by
**region** (`europe-gas-2026.context`), or by **domain**. System 1's live feeds then layer dynamic
signals on top of whichever foundation you loaded.

---

## Mental model

| ML analogy | SAGE |
|---|---|
| Pretrained weights / `from_pretrained()` | **Context bundle** (this) |
| Continual / online learning at inference | System 1 live feeds |
| Domain adapter / region fine-tune | Region-specific bundle |

It is a **load**, not a train — there is no optimization. The bundle deterministically seeds a known
graph state. Think "checkpoint" or "save file," not "fit."

---

## Directory layout

A bundle has **three layers**: `facts/` (structured ground truth, loaded directly), `sources/`
(real fetched evidence text), and `narratives/` (per-entity prose routed through synthesis —
grounded on the sources when present).

```
<name>-<domain>-<year>.context/
├── manifest.yaml          # metadata, source registry, estimation methods, contents
├── facts/                 # LAYER 1 — structured values → graph attributes (deterministic)
│   ├── nodes/
│   │   ├── corridors.csv      ports.csv        authorities.csv
│   │   ├── suppliers.csv      spr_caverns.csv  geo_events.csv      (historical events)
│   │   ├── refineries.csv     crude_grades.csv
│   └── edges/
│       ├── exports_via.csv    supplies.csv     bypass_routes.csv
│       ├── feeds.csv          configured_for.csv
├── sources_index.csv      # entity_id, url, note  → which URLs to fetch per entity
├── sources/               # LAYER 2 — real fetched evidence (the grounding text, RAG)
│   ├── event_2024_red_sea.md   #   fetched by scripts/fetch_sources.py (or curated)
│   └── ...
└── narratives/            # LAYER 3 — prose with [[wikilinks]] → synthesis path → wiki store
    ├── corridor_hormuz.md   #   filename = entity_id; optional hand-authored override
    └── ...
```

The bundle carries the **graph values + narrative context**. Entity **identity** (ids, aliases, H3
cells, price instruments) lives in `knowledge/registry.py` — keep the two in sync via `entity_id`.

### How the two layers load (`bundle.instantiate(g)`)

| Layer | Path | Stores populated |
|---|---|---|
| **Facts** | `facts/*.csv` → structural episodes → `add_episode()` | Episodic + semantic graph (typed attributes) |
| **Narratives** | `narratives/*.md` → `render_wiki_page()` → `write_wiki_page()` + `add_episode()` | Wiki + episodic + semantic + vector (with `[[wikilinks]]` → `links_out` relations) |

Facts are deterministic (you don't reconcile a known number through an LLM). Narratives go through the
**same synthesis path System 1 uses** — they get reconciled prose, wikilinks, and relations.

**Narrative authoring precedence (per entity), highest first:**
1. **Hand-authored** `narratives/<entity_id>.md` — curated prose.
2. **Source-grounded** — if `sources/<entity_id>.md` exists, Nova Pro writes the page from **that
   real text + the facts only** (RAG). This is the anti-hallucination path.
3. **Facts-only LLM** — constrained to the structured facts (no source available).
4. **Deterministic stub** — facts + relationships, no LLM (`--no-llm-author`).

So the wiki store is always fully covered, and entities with fetched evidence are grounded in real
source text rather than the model's parametric memory.

### Grounding: `sources_index.csv` + `scripts/fetch_sources.py`

`sources_index.csv` (columns `entity_id, url, note`) lists the authoritative URLs per entity.
`fetch_sources.py` fetches them into `sources/<entity_id>.md` (cached evidence, kept for
reproducibility / link-rot). For bot-blocked or messy pages, paste clean text into the file manually —
the loader treats any text there as the grounding evidence.

### Canonicalization (`canonicalize_graph`) — duplicate handling

LLM extraction can create duplicate edges and alias-variant nodes (e.g. "Abu Dhabi National Oil
Company" vs "ADNOC"). `instantiate(canonicalize=True)` runs a final pass that (1) keeps one
`RELATES_TO` per (src, dst, edge-type) and (2) merges any node whose name is a registry **alias** of a
canonical entity into that canonical node (re-pointing its edges). Distinct concepts (e.g. the country
"Saudi Arabia" vs the company "Saudi Aramco") are left alone — only registry-alias matches merge.

### Narrative file format (`narratives/<entity_id>.md`)

```markdown
---
entity_id: corridor_hormuz       # required (also inferred from filename)
source_url: https://...          # provenance for the narrative content
as_of: 2024
tier: real
---

## Strategic Role
The [[Strait of Hormuz]] ... references other entities as [[Canonical Name]] wikilinks,
which the synthesis path resolves into `links_out` relations automatically.
```

---

## The provenance contract (the core rule)

**Every row must carry a `tier` and a `source`. No exceptions. The loader rejects the bundle otherwise.**

| `tier` | Meaning | `source` resolves to |
|---|---|---|
| `real` | Exact published value from an authoritative source | a key in `manifest.sources` |
| `derived` | Computed from real aggregates via a documented method | a key in `manifest.estimation_methods` |
| `estimated` | No public source exists; documented best estimate | a key in `manifest.estimation_methods` |

This is what makes "no simulated data" auditable: a reviewer asking "where's this number from?"
always gets either a URL (`real`) or a stated method (`derived`/`estimated`). A bare number fails
`validate_bundle()` and the build stops.

---

## Universal columns (every CSV)

| Column | Required | Notes |
|---|---|---|
| `tier` | ✅ | `real` \| `derived` \| `estimated` |
| `source` | ✅ | key into `manifest.sources` or `manifest.estimation_methods` |
| `as_of` | ✅ | vintage of the value (year or date) |
| `notes` | optional | per-field caveats (e.g. "choke_severity analyst-assigned") |

Node CSVs also have `entity_id` + `canonical_name`. Edge CSVs have `src_entity_id` + `dst_entity_id`.

---

## Node CSV schemas

Property columns mirror `knowledge/schema/entities.py`. Units are in the column name.

**`nodes/corridors.csv`** — `Corridor`
`entity_id, canonical_name, throughput_mbpd, choke_severity, location_lat, location_lon, tier, source, as_of, notes`

**`nodes/suppliers.csv`** — `Supplier`
`entity_id, canonical_name, country, daily_export_mbpd, sanctioned, tier, source, as_of, notes`

**`nodes/refineries.csv`** — `Refinery`
`entity_id, canonical_name, capacity_mbpd, inventory_days, location_lat, location_lon, tier, source, as_of, notes`

**`nodes/crude_grades.csv`** — `CrudeGrade`
`entity_id, canonical_name, api_gravity, sulfur_pct, origin, yield_naphtha_pct, yield_kerosene_pct, yield_diesel_pct, yield_vgo_pct, yield_residue_pct, tier, source, as_of, notes`

**`nodes/ports.csv`** — `Port`
`entity_id, canonical_name, draft_m, congestion, location_lat, location_lon, tier, source, as_of, notes`

**`nodes/spr_caverns.csv`** — `SPRCavern`
`entity_id, canonical_name, capacity_mmt, current_fill_mmt, location, tier, source, as_of, notes`

**`nodes/authorities.csv`** — `Authority`
`entity_id, canonical_name, jurisdiction, tier, source, as_of, notes`

**`nodes/geo_events.csv`** — `GeoEvent` (historical / geopolitical events)
`entity_id, canonical_name, actor, action, severity, event_time, tier, source, as_of, notes`

## Edge CSV schemas

Edge attributes mirror `knowledge/schema/edges.py`. Direction is `src → dst`.

| File | Edge | src type → dst type | Attribute columns |
|---|---|---|---|
| `edges/exports_via.csv` | `EXPORTS_VIA` | Supplier → Corridor | `volume_mbpd` |
| `edges/feeds.csv` | `FEEDS` | Corridor → Port | `throughput_share_pct` |
| `edges/supplies.csv` | `SUPPLIES` | Port → Refinery | `throughput_share_pct` |
| `edges/configured_for.csv` | `CONFIGURED_FOR` | Refinery → CrudeGrade | `compatibility, yield_pct` |
| `edges/bypass_routes.csv` | `BYPASS_ROUTE` | Supplier → Port | `cost_premium, added_days` |

Each plus the universal `tier, source, as_of, notes`.

---

## `manifest.yaml`

```yaml
bundle_id:      india-energy-2026          # unique id, used in episode names
name:           India Energy Supply Chain — 2026
schema_version: 1.0.0                       # this schema's version
domain:         oil-supply-chain
region:         India
vintage:        2026
created:        2026-06-30
description:    >
  One-paragraph summary of what this bundle covers.

tiers: [real, derived, estimated]

sources:                                    # every `real` row's source key
  EIA-chokepoints:
    label: EIA World Oil Transit Chokepoints
    url:   https://www.eia.gov/...

estimation_methods:                         # every `derived`/`estimated` row's source key
  DERIVED-import-volume:
    method: PPAC national share × total ÷ 7.33 ÷ 365 = mbpd
    tier:   derived

nodes:                                      # facts layer — node CSVs
  - {type: Corridor, file: facts/nodes/corridors.csv}
  # ...
edges:                                       # facts layer — edge CSVs
  - {type: EXPORTS_VIA, file: facts/edges/exports_via.csv}
  # ...
narratives_dir: narratives                   # layer 2 — auto-discovered *.md (filename = entity_id)
```

---

## What you must provide to instantiate SAGE (checklist for a new bundle)

These are the inputs the three downstream systems read. A bundle is "complete" when all are present.

| Needed by | Data | Bundle file |
|---|---|---|
| System 2 (ARIO) | corridor throughput, refinery capacity + inventory days, FEEDS/SUPPLIES/EXPORTS_VIA edges | corridors, refineries, feeds, supplies, exports_via |
| System 3 (Procurement) | supplier export + sanctions, crude assays + yields, CONFIGURED_FOR, BYPASS_ROUTE | suppliers, crude_grades, configured_for, bypass_routes |
| System 4 (SPR) | SPR cavern capacity + fill | spr_caverns |
| System 5 (Map) | coordinates on every geo node | (lat/lon columns above) |

---

## Refresh cadence (how often to rebuild a bundle)

| Cadence | Fields | Action |
|---|---|---|
| Never / multi-year | coordinates, H3, sea distances, chokepoint identity, SPR capacity | set once |
| ~Annual | refinery capacity, crude assays, import **shares** | refresh yearly from PPAC/Aramco |
| Monthly | per-country import **volumes**, refinery throughput | optional EIA-API fetcher |
| Event-driven | sanctions, prices, bypass capacity | **not static** — System 1 live feeds |

**Most of a bundle changes once a year.** A new bundle = a new dated directory
(`india-energy-2027.context`); keep the old one for reproducibility. Do not build scrapers to
"refresh" annual/constant data — pull once, commit, version. The only automation worth adding is a
thin EIA-API client for monthly import volumes; everything live is already System 1's job.

---

## Validation

```bash
python -c "from knowledge.context import load_bundle; \
print(load_bundle('data/india-energy-2026.context').summary())"
```

`load_bundle()` calls `validate_bundle()` automatically. Build fails if any row is unsourced, has an
invalid tier, or references an unknown source key. Run against live Bedrock (not the stub LLM) so the
structural episodes actually extract typed fields.
