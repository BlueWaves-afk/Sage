# SAGE Data Sourcing Sheet

> **Purpose.** Every node and edge property in the SAGE knowledge graph is currently mocked
> (`scripts/seed_kb.py` + the static fallbacks in the agents). This sheet maps **each schema
> field** to a **real, citable data source** and the **access method** to pull it. Use it to
> replace the mock seed with verifiable values before the demo.
>
> **Two data classes:**
> - **STATIC** — structural supply-chain facts that change yearly or slower. Pulled once,
>   hardcoded into `scripts/seed_kb.py`. (refinery capacity, crude assays, chokepoint geometry,
>   SPR capacity, port draft, supply-share edges.)
> - **DYNAMIC** — live signal values written at runtime by System 1. (risk scores, sanctions
>   flags, AIS gaps, price changepoints, SPR fill level.)
>
> All figures below are FY2024-25 / 2024-2026 vintage. Replace with the latest pull at build time.
>
> **STATUS (June 2026).** All static knowledge lives in a versioned, provenance-tracked **context
> bundle** at `data/india-energy-2026.context/` with three layers: **facts/** (sourced CSVs),
> **sources/** (real fetched evidence text), **narratives/** (prose). It now covers **61 entities**:
> 5 corridors, 13 suppliers, 8 refineries, 16 crude grades, 6 ports, 3 SPR caverns, 4 authorities,
> and **6 historical GeoEvents** (Tanker War, 2019 attacks, 2024 Red Sea, Ever Given, 2025
> Iran-Israel, 2022 Russia-Ukraine).
>
> **How it loads** (`scripts/sage_instantiate.py`): facts → graph attributes; narratives →
> synthesis → wiki + graph + vectors. Narratives are **source-grounded** — for an entity with cached
> evidence in `sources/`, Nova Pro writes the page from that real text + facts only (RAG,
> anti-hallucination), not parametric memory. A final **canonicalization** pass dedups edges and
> merges alias-variant nodes. Stores persist under `knowledge/` (`knowledge/wiki/`,
> `knowledge/graph_store/`).
>
> Every facts row carries a `tier` (`real`/`derived`/`estimated`) + `source`; the loader rejects any
> unsourced row — the machine-checked "no simulated data" guarantee. Format spec:
> [`data/CONTEXT_BUNDLE_SCHEMA.md`](CONTEXT_BUNDLE_SCHEMA.md). This sheet is the human-readable
> sourcing rationale; the bundle is the machine-readable artifact.

---

## 0. Master Data Portals (bookmark these)

| Portal | What it gives | Access | URL |
|---|---|---|---|
| **PPAC** (Petroleum Planning & Analysis Cell, GoI) | India crude imports by country, refinery installed capacity, product consumption, SPR cover | Free portal + monthly "Ready Reckoner" PDFs | https://ppac.gov.in |
| **EIA Open Data** | Brent/WTI prices, world chokepoint throughput, SPR stocks, refinery utilization | Free API key (APIv2) | https://www.eia.gov/opendata/documentation.php |
| **EIA World Oil Transit Chokepoints** | Hormuz / Bab-el-Mandeb / Suez / Malacca transit volumes | Free analysis page | https://www.eia.gov/international/analysis/special-topics/world_oil_transit_Chokepoints |
| **ISPRL** | India SPR site capacities & status | Free public site | https://isprlindia.com |
| **DGCIS Kolkata** | Official crude import value/volume by partner country | Free PDF reports | https://www.dgciskol.gov.in |
| **ExxonMobil / Aramco crude assays** | API gravity, sulfur, yield curves per grade | Free PDF downloads | https://corporate.exxonmobil.com/what-we-do/energy-supply/crude-trading/crude-oil-assays |
| **Aramco official assay** | Arab Light/Medium/Heavy/Extra-Light full assay | Free | https://china.aramco.com/en/news-media/global-news/2021/aramco-crude-oil-assay |

---

## 1. Corridor nodes — `knowledge/schema/entities.py:Corridor`

Fields: `throughput_mbpd`, `choke_severity`, `location_lat`, `location_lon`, `h3_cells`

| entity_id | throughput_mbpd (REAL) | choke_severity¹ | lat / lon² | Source for throughput |
|---|---|---|---|---|
| `corridor_hormuz` | **20.0** (2024 avg, crude+products) | 0.95 | 26.5 / 56.4 | EIA: ~20 Mbpd, ≈20% of global petroleum liquids |
| `corridor_bab_el_mandeb` | **4.2** (1H25; was ~8.8 in 2023 pre-Houthi) | 0.55 | 12.5 / 43.3 | EIA: 4.2 Mbpd transited 1H25 |
| `corridor_suez` | **4.9** (Suez Canal + SUMED, 1H25) | 0.60 | 30.7 / 32.3 | EIA: 4.9 Mbpd crude+products 1H25 |
| `corridor_malacca` | **~23–24** (crude+products) | 0.70 | 2.5 / 102.0 | EIA chokepoints (2nd-largest after Hormuz) |

¹ **`choke_severity` is an analyst-assigned 0..1 structural-importance constant, NOT external data.**
The design fixes Hormuz≈0.95, Suez≈0.6 (see `entities.py:Corridor` field doc). Keep these as
seed constants; they are not pulled from a feed.

² `location_lat/lon` and `h3_cells` are already correct in `knowledge/registry.py` — no change needed.

**Sources:**
- [EIA — Strait of Hormuz remains critical oil chokepoint](https://www.eia.gov/todayinenergy/detail.php?id=65504)
- [EIA — World Oil Transit Chokepoints](https://www.eia.gov/international/analysis/special-topics/world_oil_transit_Chokepoints)
- [Statista — Oil flows through Strait of Hormuz 2014–2024](https://www.statista.com/statistics/277157/key-figures-for-the-strait-of-hormuz/)

---

## 2. Supplier nodes — `knowledge/schema/entities.py:Supplier`

Fields: `country`, `daily_export_mbpd`, `sanctioned`

`daily_export_mbpd` here = the supplier's **total crude export capacity** (structural). The
**volume to India** is captured separately on the `EXPORTS_VIA` edge (§8). `sanctioned` is
DYNAMIC — set by System 1's sanctions sub-agent, not seeded.

| entity_id | country | daily_export_mbpd (total exports, REAL) | To-India FY24-25³ | sanctioned (seed) |
|---|---|---|---|---|
| `supplier_aramco` | Saudi Arabia | **~6.0** | ~0.69 Mbpd (≈34 MT/yr, ~14% share) | false |
| `supplier_iraqoil` (SOMO) | Iraq | **~3.4** | ~0.98 Mbpd (≈49 MT/yr, ~20% share) | false |
| `supplier_adnoc` | UAE | **~3.0** | ~0.47 Mbpd (≈23 MT/yr, ~9.5% share) | false |
| `supplier_rosneft` | Russia | **~4.5–5.0** seaborne | ~1.75 Mbpd (≈88 MT/yr, ~35.8% share)⁴ | false |
| `supplier_nioc` | Iran | **~1.3–1.5** | ~0 to India (US-sanctioned; flows to China) | true⁵ |

³ Derived from FY2024-25 total India crude imports of **244.5 MT** × per-country share. Convert:
MT/yr × 7.33 bbl/tonne ÷ 365 = Mbpd. (244.5 MT ≈ 4.9 Mbpd total India crude import.)

⁴ The 35.8% Russia share is **all Russian suppliers** (Rosneft, Lukoil, Surgutneftegas etc.),
not Rosneft alone. For the demo graph, attributing it to `supplier_rosneft` as the Russia proxy
is acceptable — flag it as a simplification.

⁵ NIOC `sanctioned=true` is a reasonable **seed default** (Iran is under standing OFAC sanctions),
but the authoritative value comes from System 1's OFAC/EU/UN diff at runtime.

**Sources:**
- [PPAC / Seair — India crude imports by country FY2024-25 (244.5 MT total)](https://www.seair.co.in/blog/oil-imports-in-india.aspx)
- [DGCIS — Insights into Import of Crude Oil (per-country value shares)](https://www.dgciskol.gov.in/writereaddata/Downloads/20251024153605Insights%20into%20Import%20of%20Crude%20Oil%20and%20International%20Crude%20Oil%20prices%20.pdf)
- [ORF — Diversification as India's Geoeconomic Cushion](https://www.orfonline.org/expert-speak/diversification-as-india-s-geoeconomic-cushion-in-a-volatile-oil-order)

---

## 3. Refinery nodes — `knowledge/schema/entities.py:Refinery`

Fields: `capacity_mbpd`, `inventory_days`, `location_lat`, `location_lon`

| entity_id | capacity_mbpd (REAL) | Operator | inventory_days⁶ | lat / lon |
|---|---|---|---|---|
| `refinery_jamnagar` | **1.24–1.40** (DTA 0.66 + SEZ 0.58; NCI 21.1) | Reliance | ~20–30 | 22.47 / 70.07 |
| `refinery_mangaluru` | **0.30** (15 MMTPA = ~0.30 Mbpd) | MRPL (ONGC) | ~20–30 | 12.91 / 74.84 |
| `refinery_paradip` | **0.30** (15 MMTPA = ~0.30 Mbpd) | IOCL | ~20–30 | 20.31 / 86.69 |

Conversion: MMTPA × 20,000 ≈ bpd (1 MMTPA crude ≈ 20,000 bpd). 15 MMTPA ≈ 300,000 bpd = 0.30 Mbpd.

⁶ **`inventory_days` is NOT published per-refinery.** India's *national* average crude inventory
is ~20–30 days (PPAC). Use ~22 days as a seed constant for all three; flag as an estimate. There is
no public live feed for per-refinery tank levels.

**Sources:**
- [PPAC — Installed Refinery Capacity](https://ppac.gov.in/infrastructure/installed-refinery-capacity)
- [Wikipedia — Jamnagar refinery (DTA 660k + SEZ 580k bpd, NCI 21.1)](https://en.wikipedia.org/wiki/Jamnagar_refinery)
- [FactoData — India refining capacity company-wise](https://factodata.com/india-refining-capacity/)

---

## 4. CrudeGrade nodes — `knowledge/schema/entities.py:CrudeGrade`

Fields: `api_gravity`, `sulfur_pct`, `origin`. **These nodes do not exist in the registry or seed
yet — they must be added** (this is the gap blocking System 3's `get_grade_specs()`).

| Suggested entity_id | Grade name | api_gravity (REAL) | sulfur_pct (REAL) | origin | Supplier link |
|---|---|---|---|---|---|
| `grade_arab_light` | Arab Light | **32.8** | **1.96** | Saudi Arabia (Ghawar) | Aramco |
| `grade_arab_medium` | Arab Medium | **30.4** | **2.59** | Saudi Arabia | Aramco |
| `grade_arab_heavy` | Arab Heavy | **27.4** | **2.89** | Saudi Arabia (Safaniya) | Aramco |
| `grade_arab_xlight` | Arab Extra Light | **40.9** | **1.15** | Saudi Arabia | Aramco |
| `grade_basrah_medium` | Basrah Medium | **27.9** | **3.00** | Iraq | SOMO |
| `grade_basrah_heavy` | Basrah Heavy | **24.0** | **4.05** | Iraq | SOMO |
| `grade_urals` | Urals | **31.3** | **1.25–1.7** | Russia | Rosneft |
| `grade_murban` | Murban | **40.2** | **0.79** | UAE (ADNOC) | ADNOC |
| `grade_bonny_light` | Bonny Light | **38.0** | **0.37** | Nigeria (alt source) | — |

### 4a. Assay yield curves — for System 3 grade-compatibility RF model

`alt_procurement_agent/grade.py` (RF + Peng-Robinson EOS) needs **atmospheric distillation cut
yields** per grade, not just API/sulfur. Representative vol-% yields below are consistent with each
grade's API gravity and published assays. **Lighter crude → more naphtha/distillate, less residue.**
Replace with exact figures from the BP/ExxonMobil/Aramco assay PDFs at model-training time.

| Grade | Light ends + Naphtha % | Kerosene/Jet % | Diesel/Gasoil % | VGO % | Atm. Residue % |
|---|---|---|---|---|---|
| Arab Extra Light (40.9°) | ~28 | ~15 | ~22 | ~20 | ~15 |
| Murban (40.2°) | ~28 | ~15 | ~22 | ~20 | ~15 |
| Bonny Light (38.0°) | ~26 | ~14 | ~23 | ~20 | ~17 |
| Arab Light (32.8°) | ~22 | ~13 | ~20 | ~22 | ~23 |
| Urals (31.3°) | ~19 | ~12 | ~20 | ~22 | ~27 |
| Arab Medium (30.4°) | ~19 | ~12 | ~19 | ~22 | ~28 |
| Basrah Medium (27.9°) | ~17 | ~11 | ~18 | ~21 | ~33 |
| Arab Heavy (27.4°) | ~16 | ~11 | ~18 | ~22 | ~33 |
| Basrah Heavy (24.0°) | ~13 | ~10 | ~16 | ~21 | ~40 |

Bonny Light's total distillate yield (~61%) is the highest of these grades — consistent with the
comparative-assay literature. These are **seed/training values**; the authoritative cut tables are
the downloadable assay PDFs below.

**Sources:**
- [Aramco crude oil assay (Arab Light/Medium/Heavy/Extra-Light — full 13-cut fractions)](https://china.aramco.com/en/news-media/global-news/2021/aramco-crude-oil-assay)
- [BP crude assays — downloadable yield tables](https://www.bp.com/en/global/bp-supply-trading-and-shipping/documents-and-downloads/technical-downloads/crudes-assays.html)
- [ExxonMobil downloadable assays (by API & sulfur)](https://corporate.exxonmobil.com/what-we-do/energy-supply/crude-trading/crude-oil-assays)
- [DOE SPR Crude Oil Assay Manual (reference yield methodology)](https://www.spr.doe.gov/reports/docs/CrudeOilAssayManual.pdf)
- [S&P Global — Iraq export grade specs (Basrah Medium/Heavy)](https://www.spglobal.com/commodityinsights/en/market-insights/latest-news/oil/111820-iraq-outlines-new-specs-of-crude-export-grades)
- [Comparative assay — Bonny Light total cut yield 61.22%](https://www.ripublication.com/ijaer17/ijaerv12n18_40.pdf)
- [Urals assay — thepetrosolutions.com](https://thepetrosolutions.com/specifications-of-russian-crude-oil-urals/)

---

## 5. Port nodes — `knowledge/schema/entities.py:Port`

Fields: `location_lat`, `location_lon`, `draft_m`, `congestion`

| entity_id | draft_m (REAL) | Max vessel | congestion⁷ | lat / lon |
|---|---|---|---|---|
| `port_vadinar` | **23.0** (SBM, up to 33 at LPO; 300k+ DWT VLCC) | VLCC 315k DWT | DYNAMIC | 22.47 / 69.77 |
| `port_sikka` (Jamnagar) | **23.0** (VLCC 350k DWT, LOA 345m) | VLCC 350k DWT | DYNAMIC | 22.60 / 69.87 |
| `port_yanbu` | **~24** (VLCC; Petroline terminal) | VLCC | DYNAMIC | 24.09 / 38.05 |
| `port_fujairah` | **~23** (VLCC bunkering hub) | VLCC | DYNAMIC | 25.11 / 56.34 |

⁷ **`congestion` (0..1) is DYNAMIC** — derive at runtime from AIS vessel density / queue length
in the port's H3 cells (System 1 AIS sub-agent). Seed to 0.0. No static value.

**Sources:**
- [Deendayal Port Authority — Vadinar Offshore Oil Terminal](https://www.deendayalport.gov.in/en/about-us/off-shore-oil-terminal-oot-vadinar/)
- [Shipnext — Vadinar port (SBM 23m draft, 315k DWT, 14 Mt/yr)](https://shipnext.com/port/vadinar-invad-ind/633c1be1a8d5ebc3910f310e)
- [Shipnext — Jamnagar/Sikka terminal (VLCC 350k DWT)](https://shipnext.com/port/jamnagar-terminal-injga-iot)

---

## 6. SPRCavern nodes — `knowledge/schema/entities.py:SPRCavern`

Fields: `capacity_mmt`, `current_fill_mmt`, `location`

| entity_id | capacity_mmt (REAL, STATIC) | current_fill_mmt⁸ (DYNAMIC) | location |
|---|---|---|---|
| `spr_vizag` | **1.33** | ~0.53 (est. 40%) | Visakhapatnam, Andhra Pradesh |
| `spr_mangaluru` | **1.50** | ~0.60 (est. 40%) | Mangaluru, Karnataka |
| `spr_padur` | **2.50** | ~1.00 (est. 40%) | Padur (Udupi), Karnataka |
| **Total** | **5.33 MMT (= 36.92 Mbbl, ~9.5 days cover)** | **~21.4 Mbbl (≈40%, Mar 2025)** | — |

⁸ **`current_fill_mmt` is DYNAMIC but has no live per-site feed.** ISPRL reports total stored at
**21.4 million barrels as of March 2025** (~40% of capacity). Per-site fill is not published —
distribute the 40% proportionally as a seed, then update total from EIA/ISPRL periodic releases.
There is no real-time SPR fill API; treat as quasi-static.

**Sources:**
- [Wikipedia — Strategic Petroleum Reserve (India), site capacities](https://en.wikipedia.org/wiki/Strategic_Petroleum_Reserve_(India))
- [Deccan Chronicle — India 21.4 Mbbl SPR (Mar 2025)](https://www.deccanchronicle.com/nation/world/china-has-14-billion-barrels-strategic-oil-inventory-india-214-million-1952282)
- [ISPRL official](https://isprlindia.com/)

---

## 7. Authority nodes — `knowledge/schema/entities.py:Authority`

Fields: `jurisdiction`. Static identity nodes — no external data beyond jurisdiction string.

| entity_id | jurisdiction | Live list feed (for SANCTIONED_BY edges) |
|---|---|---|
| `authority_ofac` | US | `https://www.treasury.gov/ofac/downloads/sdn.xml` |
| `authority_eu` | EU | EU consolidated CFSP list (XML/JSON, daily) via data.europa.eu |
| `authority_un` | UN | UN Security Council consolidated list (XML) |

**Sources:**
- [OFAC SDN list XML download](https://www.treasury.gov/ofac/downloads/sdn.xml)
- [OFAC Sanctions List Service](https://ofac.treasury.gov/sanctions-list-service)
- [EU Consolidated financial sanctions list](https://data.europa.eu/data/datasets/consolidated-list-of-persons-groups-and-entities-subject-to-eu-financial-sanctions)

---

## 8. Edge data — `knowledge/schema/edges.py`

| Edge | Fields | Source for REAL values |
|---|---|---|
| **EXPORTS_VIA** (Supplier→Corridor) | `volume_mbpd` | Per-supplier India volume from §2 routed onto its corridor. Aramco/SOMO/ADNOC/NIOC → Hormuz; Rosneft → Suez/Malacca (not Hormuz). |
| **FEEDS** (Corridor→Port) | `throughput_share_pct` | Fraction of a port's inbound crude transiting that corridor. For Indian west-coast ports (Vadinar, Sikka): **~0.42–0.45 via Hormuz** (matches India's ~42% Hormuz-dependence figure). Derive from PPAC import-by-source × geography. |
| **SUPPLIES** (Port→Refinery) | `throughput_share_pct` | Vadinar→Jamnagar ≈ **0.70**; Sikka→Jamnagar SEZ ≈ 0.30. Estimated from terminal-refinery pairing (co-located). No single public table — derive from operator filings. |
| **CONFIGURED_FOR** (Refinery→CrudeGrade) | `yield_pct`, `compatibility` | From crude assay yield curves (§4 ExxonMobil/Aramco assays) matched to refinery NCI. Jamnagar (NCI 21.1) → compatibility ~0.9 for nearly all grades incl. heavy/sour. Compute via Peng-Robinson EOS + RF model (`alt_procurement_agent/grade.py`). |
| **BYPASS_ROUTE** (Supplier→Port) | `cost_premium`, `added_days` | Yanbu (Petroline) bypass: **+$2–3/bbl freight, +7–12 days** via Suez/Cape. ADCOP→Fujairah: smaller premium. See bypass capacity below. |
| **SANCTIONED_BY** (Vessel/Supplier→Authority) | `list_name`, `effective_date` | DYNAMIC — System 1 OFAC/EU/UN diff. Not seeded. |
| **RISK_STATE** (any→self) | `score`, `band`, `factor_*` | DYNAMIC — System 1 fusion model. Not seeded (seed to calm/0.1). |
| **FEEDS_RESERVE** (Refinery→SPRCavern) | — | Structural pairing: caverns co-located with refineries (Vizag→east-coast, Mangaluru/Padur→west-coast). |

**Bypass capacity facts (for BYPASS_ROUTE seeding):**
- **Saudi Petroline (East-West):** 5 Mbpd normal, **7 Mbpd max** (2026, after NGL-line conversion); Yanbu loading constrained to ~3–4 Mbpd in practice. Terminal: Yanbu.
- **UAE ADCOP:** **1.5 Mbpd** to Fujairah, bypassing Hormuz.
- **IEA estimate:** 3.5–5.5 Mbpd total alternative export capacity available vs 20 Mbpd Hormuz flow.

**Sources:**
- [Wikipedia — East–West Crude Oil Pipeline (Petroline)](https://en.wikipedia.org/wiki/East%E2%80%93West_Crude_Oil_Pipeline)
- [Fortune — Saudi pipeline hits 7M bbl Hormuz-bypass goal](https://fortune.com/2026/03/28/saudi-arabia-east-west-oil-pipeline-strait-hormuz-bypass-7-million-barrels-yanbu-red-sea/)
- [India-Briefing — India's Hormuz dependence (~42%) & diversification](https://www.india-briefing.com/news/indias-oil-supply-hormuz-diversification-strategy-43381.html/)

---

## 8a. Maritime routing cost matrix — for System 3 OR-Tools router

`alt_procurement_agent/routing.py` (OR-Tools MILP) needs an **asymmetric cost matrix**: distance +
canal/transit fees + war-risk premium per supplier→port lane. Components and real values:

**Sea distances & transit time (laden VLCC ~13 kn):**

| Lane | Distance (nm) | Laden days | Route |
|---|---|---|---|
| Ras Tanura → Vadinar (via Hormuz) | ~1,500 | ~5 | Gulf → Hormuz → Arabian Sea |
| Fujairah → Vadinar (Hormuz-bypassed) | ~1,000 | ~3 | already outside Hormuz |
| Yanbu → Vadinar (via Bab-el-Mandeb) | ~3,300 | ~10–11 | Red Sea → Bab-el-Mandeb → Arabian Sea |
| Ceyhan → Vadinar (via Suez) | ~4,800 | ~15–18 | Med → Suez → Red Sea → Arabian Sea |
| (reference) Ras Tanura → Japan | ~6,500 | ~20–25 | via Malacca |

Yanbu routing ties up each VLCC an **extra 12–15 days** vs Hormuz-direct — the basis for the
`BYPASS_ROUTE.added_days` values in §8. Pull exact port-pairs from sea-distances.org at build time.

**Transit / canal fees:**

| Fee | Value | Per-barrel (2M-bbl VLCC) |
|---|---|---|
| Suez Canal — laden VLCC transit | ~$800,000 | ~$0.40/bbl |
| Hormuz transit cost stack (incl. war-risk) | $6–10M (2026 wartime) | ~$3–5/bbl |
| Petroline pipeline tariff (to Yanbu) | included in bypass premium | ~$2.50/bbl (see §8) |

**War-risk insurance premium** (the "piracy/conflict" term in the cost matrix): a percentage of hull
value per transit, spiking during crises (Red Sea/Hormuz). Use the corridor `risk_score` (System 1)
as the live multiplier; baseline ~0.1–0.5% of hull value, rising to 1%+ in wartime. No single free
API — derive from Lloyd's/insurer war-risk listings or proxy from GDELT shipping-sector tone.

**Great-circle distances** between any two nodes are computable for free from the seeded lat/lon
coordinates (haversine) — no external feed needed for the base distance term.

**Sources:**
- [sea-distances.org — port-to-port nautical distances](https://sea-distances.org/)
- [SeaRates — distance & transit time calculator](https://www.searates.com/distance-time/)
- [Suez Canal Authority — official tolls table](https://www.suezcanal.gov.eg/English/Navigation/Tolls/Pages/TollsTable.aspx)
- [Leth Agencies — Suez toll calculator (VLCC)](https://lethagencies.com/suez-calculator)
- [House of Saud — Yanbu bypass +12–15 days, 11,500 nm to Japan](https://houseofsaud.com/aramco-east-west-pipeline-red-sea-yanbu-hormuz-bypass/)
- [Hormuz transit cost stack $6–10M (2026)](https://hormuztoll.com/news/2026/04/23/the-cost-stack-on-a-single-hormuz-transit-today-six-to-ten-million-dollars-funding-nothing/)

---

## 9. DYNAMIC live feeds — System 1 sensory inputs

These are NOT seeded — they are pulled live (or replayed from `demo_cache/`) by System 1.

| Sub-agent | Feed | Access | Endpoint / Library | Writes to graph |
|---|---|---|---|---|
| **AIS** (`sensory_agent/ais.py`) | aisstream.io | Free API key (GitHub login) | `wss://stream.aisstream.io/v0/stream` | `factor_ais`, `Corridor.choke_severity`, `Port.congestion`, dark-vessel `Vessel` nodes |
| **News** (`sensory_agent/news.py`) | GDELT 2.0 + NewsAPI | Free (GDELT) / free tier (NewsAPI) | GDELT DOC 2.0 API, 15-min updates; GKG themes | `factor_gdelt`, `GeoEvent` nodes |
| **Sanctions** (`sensory_agent/sanctions.py`) | OFAC SDN + EU + UN | Free XML | `treasury.gov/ofac/downloads/sdn.xml` (+ EU/UN) | `Supplier.sanctioned`, `Vessel.sanctioned`, `SANCTIONED_BY` edges |
| **Prices** (`sensory_agent/prices.py`) | EIA + yfinance | Free API key (EIA) / free lib | yfinance `BZ=F`, `CL=F`; EIA APIv2 | `factor_price`, RISK_STATE |
| **SAR (enhancement)** | ESA Sentinel-1 (Copernicus) | Free (Copernicus Hub) | Copernicus Data Space API | dark-vessel confirmation |

**Sources:**
- [aisstream.io API documentation](https://aisstream.io/documentation)
- [GDELT DOC 2.0 API](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/)
- [EIA API technical documentation](https://www.eia.gov/opendata/documentation.php)
- [OFAC list file formats & downloads](https://ofac.treasury.gov/faqs/topic/1641)

---

## 10. What's still mocked / has no real feed (be honest in the demo)

| Property | Why no clean source | Recommended handling |
|---|---|---|
| `Refinery.inventory_days` | Not published per-refinery | Seed ~22 days national avg (PPAC); label as estimate |
| `SPRCavern.current_fill_mmt` per-site | Only national total (21.4 Mbbl) is public | Distribute 40% proportionally; update total periodically |
| `Port.congestion` | No public index | Derive live from AIS density; seed 0.0 |
| `SUPPLIES.throughput_share_pct` | Operator-internal | Estimate from co-location; label as estimate |
| `Corridor.choke_severity` | Analyst construct, not a measurement | Keep as fixed seed constant (Hormuz 0.95 etc.) |
| `CONFIGURED_FOR.compatibility` | Computed, not measured | Output of `grade.py` RF + Peng-Robinson model, not external data |

---

## 11. Build action items (data layer)

1. ✅ **DONE — `CrudeGrade` nodes + `CONFIGURED_FOR` edges added to `scripts/seed_kb.py`**
   (`structural-crude-grades-v1`, `structural-grade-config-v1`).
2. ✅ **DONE — Real supplier/refinery/corridor/port/SPR values seeded** via the `STRUCTURAL_EPISODES`
   block (§1–§6 values).
3. ✅ **DONE — `EXPORTS_VIA`, `FEEDS`, `SUPPLIES`, `BYPASS_ROUTE` edges added**
   (`structural-export-topology-v1`, `structural-bypass-routes-v1`).
4. ✅ **DONE — 9 CrudeGrade entities registered** in `knowledge/registry.py` (31 entities total now).
5. ⏳ **PENDING — Wire the live feeds** (§9) once System 1 sub-agents are implemented; until then
   `demo_cache/` replays the Feb 23–28 2026 Hormuz golden-path values.
6. ⏳ **VERIFY at build time** — run `seed_kb.py` against a live FalkorDB with `LLM_PROVIDER=bedrock`
   (NOT `stub` — the stub LLM does not extract typed fields) and confirm the verification block prints
   non-zero counts for suppliers, grades, corridors, caverns, and subgraph nodes/edges. Extraction
   quality depends on Nova Pro; if any typed field is missed, make the prose in that episode more
   explicit (one fact per sentence).
7. ⏳ **Extract exact assay yield curves** (§4a) from the BP/Aramco PDFs into a training table for
   `alt_procurement_agent/grade.py`. Representative values are seeded; exact values improve RF accuracy.

---

## 12. Comprehensive status — what is REAL vs what is still SIMULATED

After this update, here is the complete state of every data input in the system.

### ✅ REAL & seeded (static structural graph)

| Data | Where | Source |
|---|---|---|
| Corridor throughput / choke_severity / coords | `seed_kb.py` structural episodes | EIA chokepoints (§1) |
| Supplier country / export volume | `seed_kb.py` | PPAC FY24-25 (§2) |
| Refinery capacity / coords | `seed_kb.py` | PPAC (§3) |
| CrudeGrade API / sulfur / origin (9 grades) | `seed_kb.py` + registry | Aramco/Exxon/S&P assays (§4) |
| Port draft / coords | `seed_kb.py` | Port authorities (§5) |
| SPR capacity per site | `seed_kb.py` | ISPRL (§6) |
| EXPORTS_VIA / FEEDS / SUPPLIES / CONFIGURED_FOR / BYPASS_ROUTE edges | `seed_kb.py` | §8 |
| Assay yield curves (representative) | docs only → grade.py | BP/Aramco assays (§4a) |
| Maritime distances / canal fees | docs only → routing.py | sea-distances.org, SCA (§8a) |

### ✅ REAL but LIVE (pulled at runtime by System 1 — feeds identified, free, not yet wired)

| Data | Feed | Status |
|---|---|---|
| AIS positions / dark vessels | aisstream.io (free websocket) | feed ready; `ais.py` is a stub |
| News / GDELT events | GDELT 2.0 + NewsAPI (free) | feed ready; `news.py` is a stub |
| Sanctions adds/removals | OFAC/EU/UN XML (free) | feed ready; `sanctions.py` is a stub |
| Brent/WTI prices + changepoints | yfinance + EIA (free) | feed ready; `prices.py` is a stub |

### ⚠️ STILL SIMULATED — no clean public source, must stay estimated or hand-built

| # | Data | Why no real source | Current handling |
|---|---|---|---|
| 1 | `RISK_STATE.score` + factor breakdown | Computed by System 1 fusion, not a feed | Demo values in `seed_kb.py` until System 1 runs |
| 2 | `Refinery.inventory_days` | Not published per-refinery | Seeded ~22 d (national avg, PPAC); labelled estimate |
| 3 | `SPRCavern.current_fill_mmt` per site | Only national total (21.4 Mbbl) is public | 40% distributed proportionally; labelled estimate |
| 4 | `Port.congestion` | No public congestion index | Seed 0.0; derive live from AIS density |
| 5 | `SUPPLIES`/`FEEDS` `throughput_share_pct` | Operator-internal allocation | Estimated from co-location/geography (§8) |
| 6 | **Fusion model calibration set** | The "5 labelled crisis timelines" (`fusion.py`) | **Must be hand-built** from historical events (2019 tanker attacks, 2024 Red Sea, Feb 2026 Hormuz) — labelled training data |
| 7 | **GNN surrogate training set** | Learns ARIO mapping | **Synthetic** — Monte Carlo ARIO sweep (`gnn/train.py`); needs ARIO implemented first, no external data |
| 8 | War-risk insurance premium series | No free real-time API | Proxy from corridor risk_score / GDELT shipping tone (§8a) |
| 9 | Exact assay yield cuts | Behind assay-PDF extraction | Representative values seeded (§4a); refine from PDFs |
| 10 | **`demo_cache/` golden path (Feb 23–28 2026)** | The demo crisis replay | **Must be recorded/scripted** — the timed AIS+GDELT+price+sanctions sequence for `DEMO_MODE=true`. Currently empty (`.gitkeep` only). |
| 11 | `Vessel` / `GeoEvent` nodes | Created at runtime from sanctions + news | None static; appear live (or in demo cache) |

### ❌ NOT data — computed outputs (no sourcing needed, produced by the systems)

`ScenarioOutput` (System 2 ARIO), `ProcurementRec` (System 3), `SPRSchedule` (System 4),
`PendingScenario` (sandbox). The `seed_kb.py` examples are illustrative; real ones are computed
at runtime.

### The three things that still need human work before demo

1. **`demo_cache/` golden-path replay** (#10) — highest priority; the demo cannot run offline without it.
2. **Fusion calibration timelines** (#6) — needed for System 1 to produce credible risk scores.
3. **Assay-PDF yield extraction** (#9) — needed only for full System 3 RF-model accuracy; representative values work for the demo.

Everything else is either seeded-real, a wired-free-feed, or an honestly-labelled estimate.

---

*Compiled June 2026. All values FY2024-25 / 2024-2026 vintage — re-pull from §0 portals at build time.*
