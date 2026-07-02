# SAGE Context Bundle — Data Provenance & Sources

**Bundle:** `india-energy-2026` · **version 1.1.0** · vintage 2026
**Last provenance review:** July 2026

This document catalogs **every value** in the bundle, where it came from, and whether it is
**real**, **derived**, or **estimated**. It exists so judges and users can audit exactly what data
SAGE runs on — nothing here is invented or simulated without being labelled as such.

## Provenance legend

| Tier | Meaning |
|---|---|
| **real** | Exact published value from an authoritative source (EIA, PPAC, ISPRL, Aramco/BP assays, OFAC…). |
| **derived** | Computed from real aggregates via a documented method (e.g. import share × national total ÷ conversion). |
| **estimated** | No public per-item source exists; a documented estimate. These are the values flagged below for future sourcing. |

Every row in every CSV carries a `tier` and a `source` column. The loader (`knowledge/context/loader.py`)
**rejects any row with a missing/unknown source** — the machine-checked "no unsourced data" guarantee.

---

## 1. July 2026 verification pass — values corrected against live sources

During this review we re-checked the highest-impact values against current public data and **updated the
bundle** where the live figure differed materially. All changes below are real, cited corrections.

| Value | Was | Now | Source |
|---|---|---|---|
| **Baseline Brent** (`economics_params`) | $75/bbl (estimated) | **$95/bbl (real)** | [EIA STEO Jun 2026](https://www.eia.gov/outlooks/steo/) — 2026 annual avg $95/bbl (Q2 $114.6, Q3 $99.8, Q4 $88). [Rigzone](https://www.rigzone.com/news/eia_boosts_2026_brent_oil_price_projection_to_96-15-apr-2026-183451-article/) |
| **SPR fill** (`spr_caverns`) | ~40% (2.13 MMT) | **~57% (3.05 MMT)** | ISPRL held **21.4 M bbl** as of Mar 2025 = 57% of 36.9 M bbl capacity. [Deccan Chronicle](https://www.deccanchronicle.com/nation/world/china-has-14-billion-barrels-strategic-oil-inventory-india-214-million-1952282) · [EIA strategic inventories 2025](https://www.eia.gov/todayinenergy/detail.php?id=67504) · [Wikipedia India SPR](https://en.wikipedia.org/wiki/Strategic_Petroleum_Reserve_(India)) |
| **Import dependence** (`ario_params`) | 88.2% | **88.6%** (89.4% provisional full-yr) | PPAC FY24-25 first-10-mo. [OilPrice](https://oilprice.com/Latest-Energy-News/World-News/Indias-Oil-Import-Dependence-Climbs-to-Nearly-89-as-Domestic-Output-Lags.html) |
| **Daily crude throughput** (`ario_params`) | 5.15 mbpd | **5.25 mbpd** | PPAC refinery throughput 261.55 MMT FY23-24 ÷ 7.33 ÷ 365. [PPAC](https://ppac.gov.in/infrastructure/installed-refinery-capacity) |

### Values reviewed and documented but kept (structural baselines, not crisis snapshots)

- **Hormuz share `42.5%`** — This is the *structural, pre-crisis* dependence (~45% via Hormuz).
  As of mid-2026 India routes **~70% of crude *outside* Hormuz** (i.e. only ~30% via Hormuz), up from
  ~55% outside the prior year — a **dynamic, crisis-driven** diversification, not a structural constant.
  SAGE treats the live share as System 1's job; the static baseline stays at a defensible ~42.5%.
  Source: [MoPNG / All India Radio, Jun 2025](https://newsonair.gov.in/india-secures-70-of-crude-oil-imports-outside-strait-of-hormuz-petroleum-ministry/) · [Autocar India](https://www.autocarindia.com/car-news/india-reroutes-70-of-crude-imports-away-from-strait-of-hormuz-439199)
- **OPEC spare capacity `3.5 mbpd`** — Real value was **~5 M bbl/d in Apr 2026**, projected to narrow to
  ~3 M by year-end as voluntary cuts unwind. 3.5 is a defensible year-end structural figure; documented
  for transparency. Source: [EIA capacity definitions](https://www.eia.gov/todayinenergy/detail.php?id=66904) · [EIA STEO](https://www.eia.gov/outlooks/steo/report/global_oil.php)
- **VLCC voyage costs `routing_params`** (Saudi $1.80/bbl … US $5.20/bbl) — These are **normal-market**
  estimates from Baltic/Clarkson norms. During the Feb–Jun 2026 Hormuz closure, AG-India VLCC rates spiked
  to WS 897 / **$400k+/day** — but that is a **dynamic crisis premium** (System 1 / war-risk layer), not the
  structural baseline. Source: [EIA tanker rates late-2025](https://www.eia.gov/todayinenergy/detail.php?id=67064)

---

## 1b. Refresh contract — annual vs sub-annual vs live

Not every value refreshes on the same clock. The bundle is designed as an **annual** artifact, and
~80% of it genuinely is — but a handful of embedded values drift faster and are only safe as static
defaults because **System 1 overrides them live**. To make this explicit rather than buried in note
fields, [`params/volatile_defaults.csv`](params/volatile_defaults.csv) enumerates every sub-annual value:
what it is, which file it lives in, its cadence, its staleness risk, and what live signal should override it.

**A yearly commit is sufficient for everything EXCEPT the rows in that registry.**

| Tier | Cadence | Examples | Home |
|---|---|---|---|
| **Structural** | annual / never | corridor throughput & coords, refinery capacity, crude assays, SPR *capacity*, port drafts, IO tables, ARIO elasticity & GDP/inflation coefficients, TOPSIS weights, SDP params | the bundle — commit once/year |
| **Volatile** | weekly–quarterly | baseline Brent, VLCC freight, Hormuz share, SPR *fill*, OPEC spare, refinery inventory days | in the bundle as **cold-start fallbacks**; `volatile_defaults.csv` flags them; System 1 overrides live |
| **Live** | seconds–minutes | risk scores (RISK_STATE), port congestion, vessel positions, sanctions changes, war-risk premium | **never** static — System 1's exclusive job |

Each param file now also carries an inline `update_freq` column so the cadence travels with the value.
The single fastest-drifting embedded value is **baseline Brent** — oil moves daily, so the static $95 is a
cold-start seed; without a live price feed it needs a manual mid-year refresh, not a yearly one.

---

## 2. Facts layer — nodes

### Corridors (`facts/nodes/corridors.csv`)
| Field | Tier | Source |
|---|---|---|
| `throughput_mbpd` (Hormuz 20.0, Malacca 23.0, Suez 4.9, Bab-el-Mandeb 4.2, Cape 7.0) | **real** | [EIA World Oil Transit Chokepoints](https://www.eia.gov/international/analysis/special-topics/world_oil_transit_Chokepoints) |
| `location_lat/lon` | **real** | Geographic coordinates (fixed) |
| `choke_severity` (0.15–0.95) | **estimated** | Analyst-assigned structural criticality weight — no single published index; encodes strategic substitutability. |

### Suppliers (`facts/nodes/suppliers.csv`)
| Field | Tier | Source |
|---|---|---|
| `daily_export_mbpd` (Aramco 6.0, Iraq 3.4, ADNOC 3.0, Rosneft 4.5 …) | **real** | [PPAC import-by-country](https://ppac.gov.in) — national export capacity/proxy |
| `sanctioned` (NIOC, PDVSA = true) | **real** | [OFAC SDN list](https://www.treasury.gov/ofac/downloads/sdn.xml) |

### Refineries (`facts/nodes/refineries.csv`)
| Field | Tier | Source |
|---|---|---|
| `capacity_mbpd` (Jamnagar 1.40, others 0.21–0.40) | **real** | [PPAC Installed Refinery Capacity](https://ppac.gov.in/infrastructure/installed-refinery-capacity) |
| `location_lat/lon` | **real** | Geographic |
| `inventory_days` (22 uniform) | **estimated** | `EST-inventory` — India national avg crude inventory ~22 days (PPAC) applied uniformly; per-refinery figures not published. |

### Crude grades (`facts/nodes/crude_grades.csv`)
| Field | Tier | Source |
|---|---|---|
| `api_gravity`, `sulfur_pct` (all 16 grades) | **real** | [Aramco assay](https://china.aramco.com/en/news-media/global-news/2021/aramco-crude-oil-assay), [BP crude assays](https://www.bp.com/en/global/bp-supply-trading-and-shipping/documents-and-downloads/technical-downloads/crudes-assays.html), [S&P Global (Basrah)](https://www.spglobal.com/commodityinsights/en/market-insights/latest-news/oil/111820-iraq-outlines-new-specs-of-crude-export-grades), [Urals assay](https://thepetrosolutions.com/specifications-of-russian-crude-oil-urals/) |
| `yield_*_pct` (naphtha/kero/diesel/vgo/residue) | **real (representative)** | Representative distillation cuts from the same assay PDFs — directional, refine from full assay tables for exact LP modelling. |

### Ports (`facts/nodes/ports.csv`)
| Field | Tier | Source |
|---|---|---|
| `draft_m` (18–30 m) | **real** | [Deendayal Port](https://www.deendayalport.gov.in/en/about-us/off-shore-oil-terminal-oot-vadinar/), [Shipnext](https://shipnext.com/), [Petroline (Yanbu)](https://en.wikipedia.org/wiki/East%E2%80%93West_Crude_Oil_Pipeline) |
| `congestion` (0.0 baseline) | **estimated** | `EST-congestion` — static baseline; live value derived from AIS vessel density at runtime (System 1). |

### SPR caverns (`facts/nodes/spr_caverns.csv`)
| Field | Tier | Source |
|---|---|---|
| `capacity_mmt` (Vizag 1.33, Mangaluru 1.50, Padur 2.50; total 5.33) | **real** | [ISPRL](https://isprlindia.com) — 5.33 MMT / 36.92 M bbl at 3 sites |
| `current_fill_mmt` (~57% distributed) | **derived** | `EST-spr` — national **21.4 M bbl (~57%)** as of Mar 2025, distributed by cavern capacity. *(Updated July 2026 from prior 40% estimate — see §1.)* |

### Authorities (`facts/nodes/authorities.csv`) — all **real**
OFAC, EU, UN, G7 Price Cap Coalition — sourced to their respective sanctions-list issuers.

### Geo-events (`facts/nodes/geo_events.csv`)
| Field | Tier | Source |
|---|---|---|
| Event identity, actor, action, date | **real** | [Wikipedia event articles](https://en.wikipedia.org/wiki/Strait_of_Hormuz) — Tanker War, 2019 Gulf of Oman, 2021 Ever Given, 2022 Russia-Ukraine, 2024 Red Sea, 2025 Iran-Israel |
| `severity` (0.5–0.9) | **estimated** | Analyst-assigned historical severity weight for graph seeding. |

---

## 3. Facts layer — edges

| Edge file | Field | Tier | Source / method |
|---|---|---|---|
| `exports_via.csv` | `volume_mbpd` | **derived** | `DERIVED-import-volume`: PPAC national import share × 244.5 MT ÷ 7.33 bbl/t ÷ 365 |
| `feeds.csv` | `throughput_share_pct` | **derived** | `DERIVED-share`: India ~42% Hormuz dependence applied to west-coast ports |
| `supplies.csv` | `throughput_share_pct` | **estimated** | `EST-allocation`: port→refinery split from co-location; operator allocation not published |
| `configured_for.csv` | `compatibility`, `yield_pct` | **derived** | `DERIVED-compat`: refinery Nelson Complexity × assay API/sulfur match |
| `bypass_routes.csv` | `cost_premium`, `added_days` | **real** | [Petroline/East-West pipeline](https://en.wikipedia.org/wiki/East%E2%80%93West_Crude_Oil_Pipeline), [IEA Hormuz](https://www.iea.org/about/oil-security-and-emergency-response/strait-of-hormuz) |

---

## 4. IO / economic cascade (`io/` + `params/sectors.csv`)

| File | Tier | Source |
|---|---|---|
| `io/io_sectors.csv` (va_share, petroleum_input_coeff) | **real / derived** | [MOSPI Input-Output Transactions Table](https://mospi.gov.in/publication/input-output-transactions-table-2006-07), [IIOA Hybrid Energy IO for India](https://www.iioa.org/conferences/28th/papers/files/4459_AHybridEnergyInput-OutputTableforIndiawithEIOT.pdf) |
| `io/leontief_A.csv` (8×8 technical-coefficient matrix) | **real / derived** | Aggregated from MOSPI/CSEP IO tables |
| `params/sectors.csv` (petroleum_share_pct, gdp_weight) | **real** | [PPAC/Nielsen sectoral demand study](https://www.pib.gov.in/newsite/printrelease.aspx?relid=102799); `other` row = `EST-sector-other` (residual) |

---

## 5. Model parameters — `params/`

### `ario_params.csv` (System 2 — disruption cascade)
| Param | Value | Tier | Source |
|---|---|---|---|
| `daily_consumption_mbpd` | 5.25 | **real** | PPAC throughput 261.55 MMT FY23-24 |
| `import_dependence_pct` | 88.6 | **real** | PPAC FY24-25 |
| `hormuz_share_pct` | 42.5 | **real** | PPAC (structural baseline — see §1) |
| `bypass_capacity_mbpd` | 4.0 | **real** | [IEA Hormuz](https://www.iea.org/about/oil-security-and-emergency-response/strait-of-hormuz) (Petroline + ADCOP) |
| `global_spare_mbpd` | 3.5 | **real** | [EIA OPEC spare capacity](https://www.eia.gov/outlooks/steo/report/global_oil.php) (see §1) |
| `indirect_multiplier` | 10.6 | **real** | [Inoue & Todo 2019, Nature Sustainability](https://www.nature.com/articles/s41893-019-0351-x) |
| `price_per_mbpd_low/high` | 3.5 / 6.0 | **derived** | `DERIVED-price-elasticity`: historical elasticity (~10% global loss → Brent ~$120); Fed IFDP 1173, IMF WP/17-15 |
| `gdp_pct_per_usd_bbl` | −0.04 | **derived** | [NIPFP: $10/bbl → −40 bps GDP](https://www.nipfp.org.in/media/documents/wp_2012_99.pdf) |
| `inflation_pct_per_usd_bbl` | 0.035 | **derived** | NIPFP: ~$10/bbl → +0.35 pp CPI |
| `spr_max_draw_mbpd` | 2.5 | **estimated** | `EST-spr-draw`: ISPRL emergency pumping-rate estimate (no published per-cavern rate) |
| `bypass_ramp_days` | 5.0 | **estimated** | `EST-bypass-ramp`: time to ramp Petroline/ADCOP to capacity |
| `refinery_inventory_days` | 22.0 | **estimated** | `EST-inventory`: national avg (PPAC) |

### `routing_params.csv` (System 3 — maritime routing)
| Param | Tier | Source |
|---|---|---|
| `vlcc_cost_usd_bbl` (per country) | **estimated** | [Baltic Dirty Tanker Index](https://www.balticexchange.com/en/data-services/market-information/tankers.html) / Clarkson VLCC norms — normal-market (see §1) |
| `lead_time_days` (per country) | **derived** | [Clarkson](https://www.clarksons.net/) voyage durations from great-circle distance |
| `war_risk_premium_per_half_unit` | **estimated** | [Lloyd's Joint War Committee](https://www.lmalloyds.com/) listed-areas premium |

### `ranking_params.csv` (System 3 — TOPSIS weights)
All 4 weights (cost 0.35, lead-time 0.25, compat 0.25, corridor-risk 0.15) — **estimated**, sourced to
[IEA Oil Supply Security](https://www.iea.org/reports/oil-supply-security) scoring framework. These encode a
public-procurement policy preference (cost-dominant); tune per user mandate.

### `grade_params.csv` (System 3 — compatibility tolerances)
API/sulfur sigma (8.0 / 0.5), floors (0.25 / 0.30), weights (0.6 / 0.4) — **estimated**, from
[IEA refinery-complexity](https://www.iea.org/reports/the-future-of-petrochemicals) and
[EIA crude-assay economics](https://www.eia.gov/todayinenergy/detail.php?id=9731). Physically-motivated
Gaussian tolerance windows; upgrade path is an LP/Peng-Robinson yield model.

### `spr_params.csv` (System 4 — SDP/CMDP)
| Param | Tier | Source |
|---|---|---|
| `buffer_threshold_days` (3.0), `spr_horizon_days` (90) | **real** | PNGRB refinery operating norms / 90-day cover obligation |
| `sdp_discount_rate` (0.97) | **derived** | Standard finance: 10.5% annual → daily factor |
| `refill_cost_premium_pct` (0.12) | **estimated** | IEA coordinated-release episodes (2005/2011/2022) showed 8–15% refill premium |
| `p_resolve_*` (0.55/0.20/0.05) | **estimated** | [ICB crisis dataset](https://sites.duke.edu/icbdata/) resolution rates by regime |
| `sdp_max_draw_fraction` (0.60) | **estimated** | ISPRL emergency pumping-rate estimate |

### `economics_params.csv` (shared)
| Param | Tier | Source |
|---|---|---|
| `baseline_brent_usd_per_bbl` (95.0) | **real** | [EIA STEO Jun 2026](https://www.eia.gov/outlooks/steo/) (see §1) |
| `daily_consumption_mmt` (0.57) | **derived** | 5.25 mbpd × 0.109 t/bbl |
| `supplier_risk_max_filter` (0.4), `corridor_risk_max_filter` (0.5) | **estimated** | IEA supply-security policy thresholds |
| `option_resolution_window_days` (5.0) | **estimated** | IEA 5-day diplomatic/military resolution window |
| `option_demand_destruction_during_wait` (0.30) | **estimated** | NIPFP demand-elasticity bound |

### `heuristic_params.csv` (orchestration fallback)
All 10 thresholds — **estimated**, sourced to [ICB dataset](https://sites.duke.edu/icbdata/) and
[NIPFP](https://www.nipfp.org.in/media/documents/wp_2012_99.pdf). These only run when the LLM scenario-param
decider is unavailable; they are deliberately conservative guardrails, not primary model inputs.

---

## 6. Summary — what is real vs estimated

| Category | Real | Derived | Estimated |
|---|---|---|---|
| Corridor throughput, coords | ✅ | | choke_severity |
| Supplier exports, sanctions | ✅ | | |
| Refinery capacity, coords | ✅ | | inventory_days |
| Crude assays (API/sulfur) | ✅ | | (yields representative) |
| Port drafts | ✅ | | congestion (live) |
| SPR capacity | ✅ | current_fill (57%) | |
| Import volumes, corridor shares | | ✅ | port→refinery split |
| Grade compatibility | | ✅ | |
| Brent, import-dep, consumption, spare capacity | ✅ | | |
| Price elasticity, GDP/inflation multipliers | | ✅ | |
| Routing costs / lead times | | lead times | VLCC costs, war-risk |
| TOPSIS weights, grade tolerances, SDP p_resolve, heuristics | | discount rate | ✅ (policy/behavioural) |

**The estimated values fall into three honest buckets:**
1. **Analyst-assigned structural weights** (choke_severity, event severity) — encode expert judgment, no public index exists.
2. **Live-at-runtime placeholders** (congestion, per-refinery inventory/SPR split) — System 1 refines these from AIS/operations.
3. **Policy / behavioural parameters** (TOPSIS weights, p_resolve, heuristic thresholds) — calibration choices, tunable per user mandate; sourced to the best available public framework (IEA, ICB, NIPFP).

No value is fabricated: every estimate names its method in `manifest.yaml → estimation_methods`, and every
real/derived value names its source in `manifest.yaml → sources`. Swap any value by editing the CSV and running
`python3.11 -m knowledge.context.upgrade <bundle>` (see main README).
