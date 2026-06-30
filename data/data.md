# SAGE Data Catalog — `data/india-energy-2026.context`

Every data file in the context bundle, with its source and provenance. This is the
reviewer-facing index: where each number comes from. The bundle is the single source of
foundational truth; the loader **rejects any unsourced row** (tier + source required).

Provenance tiers: **real** (exact published value) · **derived** (computed from real
aggregates) · **estimated** (no public source; documented method). Full sourcing rationale:
[`docs/data.md`](../docs/data.md). Bundle format: [`CONTEXT_BUNDLE_SCHEMA.md`](CONTEXT_BUNDLE_SCHEMA.md).

---

## 1. Facts layer — `facts/` (structured graph values)

| File | Type | Rows | Primary sources |
|---|---|---|---|
| `facts/nodes/corridors.csv` | Corridor | 5 | EIA World Oil Transit Chokepoints |
| `facts/nodes/suppliers.csv` | Supplier | 13 | PPAC imports FY24-25; OFAC (sanctioned) |
| `facts/nodes/refineries.csv` | Refinery | 8 | PPAC Installed Refinery Capacity |
| `facts/nodes/crude_grades.csv` | CrudeGrade | 16 | Aramco / BP / S&P / ExxonMobil assays |
| `facts/nodes/ports.csv` | Port | 6 | Deendayal Port Authority, Shipnext |
| `facts/nodes/spr_caverns.csv` | SPRCavern | 3 | ISPRL |
| `facts/nodes/authorities.csv` | Authority | 4 | OFAC, EU, UN, G7 |
| `facts/nodes/geo_events.csv` | GeoEvent | 6 | Wikipedia event articles (historical) |
| `facts/edges/exports_via.csv` | EXPORTS_VIA | — | derived: PPAC import share × geography |
| `facts/edges/feeds.csv` | FEEDS | — | derived: India ~42% Hormuz dependence |
| `facts/edges/supplies.csv` | SUPPLIES | — | estimated: port–refinery co-location |
| `facts/edges/configured_for.csv` | CONFIGURED_FOR | — | derived: refinery NCI × crude assay |
| `facts/edges/bypass_routes.csv` | BYPASS_ROUTE | — | IEA Petroline+ADCOP capacity |

---

## 2. Model parameters — `params/` (System 2 economic coefficients)

| File | What | Key sources |
|---|---|---|
| `params/ario_params.csv` | 14 ARIO coefficients (consumption, Hormuz share, SPR draw, bypass, **price elasticity**, **GDP/inflation per $/bbl**) | PPAC, ISPRL, IEA, EIA; **price elasticity** derived from Fed IFDP 1173 / IMF WP17-15; **GDP/inflation** from NIPFP WP2012-99 ($10/bbl → −40bps GDP) |
| `params/sectors.csv` | 8 economic sectors: petroleum-consumption share + GDP weight + criticality | PPAC/Nielsen All-India Sectoral Demand Study (transport 70% diesel, agri 13%, …) |

---

## 3. Input-Output layer — `io/` (full Leontief model)

| File | What | Source & honesty note |
|---|---|---|
| `io/io_sectors.csv` | 8 sectors: value-added share, final demand, **petroleum input coefficient** | petroleum coefficients **real** (IIOA Hybrid Energy IO Table for India); VA/FD **derived** from MOSPI IOTT |
| `io/leontief_A.csv` | 8×8 technical-coefficient matrix A | **Aggregated/derived** from MOSPI Supply-Use Table 2015-16 structure. The petroleum row is grounded in energy-IO data; other coefficients are documented aggregates. **Validated**: spectral radius 0.485 (productive); output multipliers 1.77–2.35, matching published India range (1.3–2.5). |

> **Honest scope:** this is the *real Leontief model* (exact math) on an *aggregated 8-sector*
> matrix. The full 140-sector India table (MOSPI IOTT, linked below) is a drop-in — same math,
> bigger matrix. The reduced aggregation captures the demo-critical sectoral+GDP cascade with the
> petroleum linkages grounded in real energy-IO data.

**IO source links (the full static tables, for production swap-in):**
- MOSPI Input-Output Transactions Table — https://mospi.gov.in/publication/input-output-transactions-table-2006-07
- CSEP India 2015-16 IO table — https://csep.org/discussion-note/input-output-transactions-table-india-2015-16/
- IIOA Hybrid Energy IO Table for India — https://www.iioa.org/conferences/28th/papers/files/4459_AHybridEnergyInput-OutputTableforIndiawithEIOT.pdf
- OECD ICIO database — https://www.oecd.org/en/data/datasets/inter-country-input-output-tables.html

---

## 4. Source evidence — `sources/` + `sources_index.csv`

`sources_index.csv` lists 27 authoritative URLs (entity_id → url). `fetch_sources.py` caches the
fetched text into `sources/<entity_id>.md` — the **grounding evidence** the LLM summarises (RAG),
so narratives are sourced, not parametric memory. Currently cached: the 5 historical GeoEvents +
key entities.

## 5. Narratives — `narratives/` (per-entity prose)

Hand-authored or source-grounded markdown with `[[wikilinks]]`, routed through the synthesis
pipeline into the wiki store. Each carries `source_url` frontmatter.

## 6. Source registry — `manifest.yaml`

Every `source` key used in any CSV resolves to a labelled URL in `manifest.yaml:sources`, or a
documented method in `manifest.yaml:estimation_methods`. This is the machine-checked provenance
contract — the loader fails on any unresolved source.

---

## What is simulated / estimated (full honesty)

| Item | Status | Why |
|---|---|---|
| Per-refinery `inventory_days` | estimated | national avg ~22d; per-refinery not published |
| SPR per-site `current_fill_mmt` | estimated | only national total (~40%) is public |
| `Port.congestion`, `choke_severity` | estimated/analyst | derived live (AIS) / structural construct |
| `SUPPLIES` share weights | estimated | operator allocation not published |
| Crude assay yield curves | representative | refine from full assay PDFs |
| IO matrix `leontief_A` (non-petroleum cells) | derived/aggregated | from MOSPI structure; petroleum row grounded |
| Narrative prose (non-curated entities) | LLM/grounded | grounded on `sources/` where available |

Everything else (chokepoint throughput, refinery capacity, SPR/crude assay headline values, price
elasticity, GDP/inflation coefficients, sectoral consumption shares, IO multipliers) is **real or
derived from cited sources**. No value is unsourced — the loader guarantees it.
