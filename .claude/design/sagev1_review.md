# SAGE v1 — Critical Review, Rubric Gap Analysis & Path to 100/100

**Status:** Review + remediation design — ready for implementation
**Author:** SAGE team (session audit, 2026-07-10/11)
**Grounding:** Every finding below was verified against the actual codebase and the
live EC2 deployment (`http://44.213.136.64/`) during this session — not inferred
from docs. File:line citations included where they matter.

---

## Part I — State of the System (verified)

### What is real and deployed
- Full stack live on EC2 t3.medium (trial acct `188149024315`), Bedrock routed to
  the main account. Only port 80 public; 22 IP-restricted; 8000/3000 blocked.
- All 4 System-1 sensory agents live: AIS (aisstream.io websocket), news
  (newsdata.io + GDELT), prices (yfinance + EIA), sanctions (**OFAC + UN + EU** —
  EU restored this session via the OpenSanctions free mirror of the official EU FSF
  dataset; 1089 relevant entries parsed).
- Autonomous trigger verified live: a critical-band entity fired the full
  System 2→3→4 pipeline with zero user action (observed end-to-end).
- Simulation Lab: presets, custom runs, 6 result tabs, Scenario Library
  (auto/user origins), Learning tab, outcome logging, bounded per-corridor
  calibration. All exercised against the live deployment.
- Agent Activity Trace: live per-agent narration feed (System 1 fusion, System 2/3/4
  stages) over the existing `/ws` channel + `GET /api/agent-trace/recent`.
- Feedback loops: crossing-level (confirmed/expired → `feedback_log.jsonl`) and
  scenario-level (predicted vs realized → `scenario_outcomes.jsonl`); retrain jobs
  now enqueue to `sage:jobs` and are drained + executed by the monitor loop
  (fixed this session — was print-only).
- **No fabricated data**: hardcoded RISK_STATE seeds, sample episodes, and the
  sample scenario/procurement/SPR outputs were stripped from `scripts/seed_kb.py`
  this session. Fresh deploy shows honest LOW/CALM; risk state comes only from
  live signals. `seed_kb.py` is now purely the `bundle.instantiate()` step
  (identical core to `scripts/sage_instantiate.py`).

### Critical finding #1 — the fusion risk model was never trained
- `contracts/bands.py:48-77` names five labeled crisis-replay datasets
  (`demo_cache/2019_gulf_tanker_attacks.json`, `2021_suez_blockage.json`,
  `2022_ukraine_energy_shock.json`, `2025_hormuz_standoff.json`,
  `2026_hormuz_closure.json`). **None exist.** No `sensory_agent/fusion_model.pkl`
  either.
- Therefore `fusion.py` always takes `_predict_weighted_sum` (`fusion.py:241`,
  `model_version="weighted-sum-fallback"`). The documented "GBM + Platt scaling +
  SHAP attributions, calibrated P(disruption)" is architecture-only.
- **Impact:** the #1 evaluation-focus phrase is "detection … accuracy". SAGE has
  no empirical accuracy — no AUC, no validation, no calibration. The score is a
  hand-weighted heuristic wearing a probability's clothes. A technical judge who
  greps for the model file catches this in one question.

### Critical finding #2 — port congestion is stored but never used
- `knowledge/schema/entities.py:60` defines `Port.congestion` (0..1) and the
  bundle loads it into the graph (`knowledge/context/loader.py:362`).
- `grep congestion alt_procurement_agent/` → **empty**. Procurement ranking never
  reads it. Tanker availability is not modeled anywhere at all.
- **Impact:** the brief's Area 3 names "tanker availability, port congestion" as
  explicit factors. Two of five named procurement factors are absent from the
  decision.

### The four spec deviations (with verdicts)

| # | Spec says | Code does | Verdict |
|---|---|---|---|
| 1 | GraphSAGE/GAT GNN surrogate for the fast sandbox path (`system2_designspec.md`) | Analytic ARIO called directly (`scenario_agent/runner.py:324`); an unused sklearn RandomForest "surrogate" sits in `scenario_agent/gnn/` | **Current design wins.** For a fixed topology, analytic ARIO (~0.04 ms) is faster *and* more accurate than any surrogate (~13 ms, degrades near full closure). The spec's GNN would be strictly worse. Cleanup needed: the dead `gnn/` module and `CascadeSurrogate` name mislead readers into thinking a GNN runs. |
| 2 | RF on assay yield curves + Peng-Robinson EOS grade model (`system3_design.md` §3.1) | Deterministic Gaussian API/sulfur distance, 0.6/0.4 weights, EIA-calibrated (`alt_procurement_agent/grade.py:43-70`) | **Tie — spec better in principle, blocked on data.** RF/EOS needs per-refinery assay yield curves SAGE doesn't have. Current gives correct *ordering* for compatibility ranking. Documented in-code as a drop-in upgrade. |
| 3 | OR-Tools MILP maritime routing (`system3_design.md` §3.2) | Cost-matrix minimum over open corridors: Clarkson/Baltic base rates + bypass premiums + war-risk insurance + closure exclusion (`alt_procurement_agent/routing.py`) | **Current design wins at current scale.** MILP matters for multi-cargo fleet allocation under shared capacity constraints; for single-cargo-per-supplier the min over a small matrix is the same answer. Documented drop-in. |
| 4 | Bedrock Nova Micro entity extraction from news | Registry alias string-scan (`sensory_agent/news.py:81-95`) + local HuggingFace sentiment (`sensory_agent/sentiment.py`) | **Spec wins where it counts.** Alias-scan only sees entities already in the registry, on near-exact match. Novel entities/actors are invisible. Cheap+fast+deterministic (and avoids Bedrock quota burn — real constraint, observed this session), but it costs recall, which costs "accuracy". Fix as a hybrid (below), not a wholesale swap. |

### Other known gaps (from the full .md audit)
- Voice STT hard-mocked: `voicebridge/gnani.py:68-81` unconditionally sets
  `self._mode = "mock"`; real websocket call commented out. TTS attempts real calls.
- GDP impact is a point estimate (`gdp_proxy_impact_pct`), not a trajectory.
- No upstream (wellhead/production) or downstream (distribution) nodes — the twin
  is midstream-only (corridor→port→refinery→SPR).
- `GET /api/wiki` list-all endpoint speced but absent (only `/api/wiki/{entity}`).
- LiveKit/Porcupine wake-word voice (deferred v2 per its own doc). Chronos-2,
  140-sector IO, GNN-MCTS multi-site SPR (deferred per TODO.md). Simulation Lab
  stretch goals (tornado chart, PDF export, re-run-with-mitigation) — deferred
  per spec.
- One malformed legacy RISK_STATE row ("2022 Russia-Ukraine War", `band='.'`)
  spams warnings in gateway logs. Cosmetic; should be deleted.

---

## Part II — Word-for-word vs the brief's five areas

> The brief says teams "may explore areas such as" — five alternative directions.
> SAGE attempts **all five**. Integration is the differentiator; per-area depth is
> the exposure.

### Area 1 — Geopolitical Risk Intelligence Agent
> "Multi-source agent that ingests **news feeds** ✅, **shipping AIS data** ✅,
> **sanctions registries** ✅ (all three lists now), **and commodity price
> signals** ✅ to produce a **live supply disruption probability score** ⚠️ **by
> corridor and supplier** ✅ — **updated continuously, not weekly** ✅."

**Match: ~90% textual, with one deep caveat.** The one word SAGE doesn't honestly
earn is **"probability"** — the score is an uncalibrated weighted sum (Finding #1),
not a validated P(disruption). Everything else matches word-for-word.

### Area 2 — Disruption Scenario Modeller
> "AI system that simulates specific events — **Hormuz partial closure** ✅,
> **OPEC+ emergency cut** ❌, **Red Sea shipping suspension** ✅ — and computes
> cascading impacts on **refinery run rates** ✅ (as feedstock gap per refinery),
> **domestic fuel prices** ✅, **power sector stress** ✅ (Leontief sector
> shortfall), **and GDP trajectory** ⚠️ (point estimate, not a trajectory) under
> each scenario."

**Match: ~75%.** Two misses: (a) ARIO models *transit* disruption
(`disruption_fraction` of a corridor); an OPEC+ cut is *production* disruption at
source — different physics, currently unrepresentable. (b) "GDP **trajectory**"
implies a time series; SAGE outputs a single percentage.

### Area 3 — Adaptive Procurement Orchestrator
> "Agentic system that **identifies and ranks alternative crude sources and
> logistics routes** ✅, factoring in **spot market pricing** ⚠️ (sourced rate
> norms + live Brent, not per-grade live spot), **tanker availability** ❌,
> **port congestion** ❌ (stored in graph, never read by the ranker — Finding #2),
> **and refinery grade compatibility** ✅ — generating **procurement
> recommendations that procurement teams can act on within hours** ✅."

**Match: ~65%.** Two of five named ranking factors absent, one partial.

### Area 4 — Strategic Reserve Optimisation Agent
> "AI layer that models **optimal SPR drawdown schedules** ✅ (Bellman SDP + CMDP
> Lagrangian + real-options value-of-waiting) against **supply gap forecasts** ✅,
> **refinery demand curves** ⚠️ (aggregate national consumption, not per-refinery
> curves), **and replenishment window estimates** ✅ — providing **decision
> support to policymakers under time pressure** ✅ (policy memo output)."

**Match: ~90%.** Strongest area. Only miss is per-refinery demand curves.

### Area 5 — Supply Chain Digital Twin
> "Geospatial simulation of India's **full energy supply network — from wellhead
> to refinery to distribution** ❌ (midstream-only) — that enables **continuous
> 'what-if' analysis** ✅ (Simulation Lab + counterfactuals) and serves as a
> **persistent intelligence platform** ✅ (bitemporal KG + wiki + persisted
> stores)."

**Match: ~60%.** "Wellhead" (upstream production) and "distribution" (downstream)
don't exist as node types. The persistent-platform half is genuinely strong.

---

## Part III — Evaluation Focus, every word

> *"Disruption signal detection lead time and accuracy, quality and executability
> of procurement alternatives generated, scenario model fidelity (assumptions must
> be explicit and testable), geospatial evidence depth, and demonstrated
> end-to-end response time from signal to recommendation."*

| Phrase | Where SAGE stands | Grade |
|---|---|---|
| **"detection lead time"** | Architecture is genuinely anticipatory: sandbox forks at ELEVATED before ACTION crossing; PendingScenario pre-stages System 2 output; `get_accuracy_summary()` tracks `mean_lead_time_error_hours`. But the lead-time metric currently reflects seeded/dev feedback records, not a validated backtest. | B |
| **"and accuracy"** | **The weakest word in the whole rubric for SAGE.** No trained model (Finding #1), no AUC, no precision/recall on historical events, no calibration curve. The claimed GBM/Platt/SHAP path exists as code but has never run. | D |
| **"quality … of procurement alternatives"** | Real TOPSIS over real graph state; sourced cost/lead/risk inputs; cited rationale prose; score breakdowns. Quality of what exists is high — but 2 of the brief's named input factors are missing (tanker, congestion), which bounds "quality" as judged against the brief. | B+ |
| **"executability of procurement alternatives"** | Genuinely strong: named supplier, named grade, named route with bypass, landed $/bbl, lead-time days, target refinery. An actual desk could act on it. | A |
| **"scenario model fidelity"** | Real ARIO + Monte Carlo (n=300, p10/50/90) + Leontief IO + ABM. Fidelity is honest about being reduced-form. | A− |
| **"assumptions must be explicit and testable"** | **SAGE's single best match — underexploited.** Every ARIO coefficient is provenance-tracked in the `.context` bundle (`value/unit/source` per row); assumptions ship inside every scenario output; the Learning loop makes predictions literally testable against realized outcomes (predicted-vs-realized MAPE + bounded visible calibration). Few teams will have anything like this. | A |
| **"geospatial evidence depth"** | H3 res-10 AIS indexing, geo-positioned KG map, blast-radius/heatmap/flow layers. But: no route geometries (routes are named strings, not polylines), no rendered vessel tracks, no per-cell evidence drill-down. Points-on-a-map, not evidence *depth*. | B− |
| **"demonstrated end-to-end response time from signal to recommendation"** | The pipeline demonstrably runs signal→scenario→procurement→SPR autonomously (observed live, ~60–90 s warm). But nothing **measures** it, nothing **displays** it, and "demonstrated" demands a number on screen. | B− (capability) / D (demonstration) |

### Judging criteria — current honest scores

| Criterion | Weight | Now | Why docked |
|---|---|---|---|
| Innovation | 25% | 20–22 | Bitemporal KG memory, anticipatory forking, self-calibration loop, 5-area integration — real novelty. Crowded space caps it. |
| Business Impact | 25% | 16–19 | High-value problem, executable outputs — but zero quantified impact: no backtest, no avoided-cost number, no validated accuracy. |
| Technical Excellence | 20% | 15–17 | Real OR models + provenance discipline; docked for the untrained fusion model, unused data fields, claim-vs-code gaps. |
| Scalability | 15% | 11–13 | Clean containers, ECR path, bundle-swappable worldview (great story); single-box deploy, Bedrock quota ceiling, no horizontal story shown. |
| User Experience | 15% | 12–13 | Polished dark-ops UI, live agent trace, copilot; docked for quiet fresh-deploy dashboard and mocked voice STT. |
| **Total** | | **74–84** | |

---

## Part IV — The Plan to 100/100

Ordered by rubric leverage. Each item names the files to touch, the mechanism, and
which rubric line it repairs. Items G1–G3 are the "claim honesty" tier — do them
first; they close the only gaps a judge can frame as *overclaiming* rather than
*scope*.

### G1 — Train the fusion model for real (fixes "accuracy" — the D)
**Problem:** five crisis datasets referenced, zero exist; GBM never trained.
**Plan:**
1. **Build the five labeled replay datasets** in `demo_cache/` from real history.
   For each crisis window in `contracts/bands.py` (2019 tanker attacks, 2021 Suez,
   2022 Ukraine shock, 2025 Hormuz standoff, 2026 Hormuz closure) generate hourly
   `FeatureVector` ticks:
   - `price_*` features from real Brent/WTI history (yfinance covers all five
     windows; BOCD run retroactively over the series).
   - `gdelt_tone_*` / `news_*` from GDELT 2.0 DOC API historical queries for the
     window (free, keyed by date + "Strait of Hormuz"/"Suez"/etc).
   - `sanctions_*` from dated OFAC/UN press releases in the window (sparse, few
     nonzero ticks — that is realistic).
   - `ais_*`: honest fallback — proxy from documented incident timelines (e.g.
     IMO/UKMTO incident reports for 2019) with a `source` note per tick; do NOT
     fabricate continuous AIS series. Mark provenance in each JSON.
   - Label: `within_24h_of_crossing = 1` for ticks inside 24 h before the
     documented disruption onset; 0 otherwise (labels already defined in
     `bands.py` per crisis).
   - New script: `scripts/build_calibration_data.py` (fetches, features, labels,
     writes the five JSONs with per-tick provenance).
2. **Train:** run the existing `python -m sensory_agent.fusion --calibrate`
   (already implements GBM + Platt + SHAP + Youden-J threshold). Persist
   `fusion_model.pkl` and commit the training report (AUC, per-crisis
   leave-one-out AUC, chosen thresholds) to `docs/CALIBRATION_REPORT.md`.
3. **Leave-one-crisis-out validation** is the credibility move: train on 4, test
   on the held-out 5th, report all five held-out AUCs. This converts "accuracy"
   from a claim into a table.
4. **Surface it:** `/api/accuracy` already exists — extend to return
   `{model_version, auc, loco_auc: {...}, trained_at}`; show "Model: GBM v1 ·
   AUC 0.9x (LOCO)" in the Command Center XAI panel. SHAP factor attributions then
   become real (fusion.py already wires them when a model is loaded).
**Rubric effect:** Eval-focus "accuracy" D→A−; Technical Excellence +2; Business
Impact +1 (validated detection is the product).

### G2 — Measure and display end-to-end response time (fixes "demonstrated")
**Problem:** capability exists; no measurement, no display.
**Plan:**
1. Stamp `t0` on every `NormalizedSignal` at emit (field exists: `observed_at` /
   `ingested_at`). When a pipeline run completes (auto or user), compute
   `signal→risk`, `risk→scenario`, `scenario→procurement`, `procurement→SPR`
   deltas from the agent-trace timestamps already being published — the data is
   ALREADY in `sage:agent_trace:recent`; this is pure aggregation.
2. New endpoint `GET /api/response-time` → last-run and rolling-median stage
   latencies. New Command Center strip: "Signal → Recommendation: 74 s (median,
   last 5 runs)" with per-stage breakdown on hover.
3. Add a `docs/METHODOLOGY.md` section defining the measurement (what starts the
   clock, what stops it) so the number is auditable.
**Rubric effect:** eval-focus "demonstrated end-to-end response time" D→A. ~Half a
day of work; highest ratio of rubric-points-per-effort in this plan.

### G3 — Truth-in-labeling cleanup (protects Technical Excellence from probes)
1. Delete or quarantine `scenario_agent/gnn/` (unused RandomForest surrogate) —
   or rename to `surrogate/` with a README explaining why analytic ARIO is the
   correct fast path (the `runner.py:313-319` argument is good; make it visible).
2. Fix `fusion.py` docstrings to say "GBM when trained; weighted-sum fallback
   otherwise" — after G1 this becomes moot, but the fallback path should never
   claim SHAP it can't produce.
3. Delete the malformed legacy RISK_STATE row (Cypher one-liner) to stop the
   log spam.
4. Update `SAGE_Knowledge_Base_Deployment.md` env-var names (`AWS_REGION`,
   `NEWSDATA_API_KEY`) and container names to match reality.

### G4 — OPEC+ production-cut scenario type (Area 2 word-for-word)
**Problem:** ARIO only models corridor transit loss.
**Plan:**
1. Extend `ARIOParams` with `supply_cut_mbpd: float = 0.0` and
   `cut_supplier: str | None` — a source-side reduction that lowers *available
   import supply* before corridor routing, rather than blocking transit. In the
   ARIO day-loop this enters as a reduction in deliverable feedstock with
   `global_spare_mbpd` (already a param, `ario.py:50`) absorbing the first
   tranche — spare capacity offsets production cuts but not chokepoint closures,
   which is exactly the real-world asymmetry.
2. New preset in `_SCENARIO_PRESETS` + `orchestration/scenario_presets.py`:
   `{"id":"opec_cut","label":"OPEC+ Emergency Cut","entity":"Saudi Aramco",
   "supply_cut_mbpd":2.0,...}` — trigger entity is a Supplier, not a Corridor.
3. Builder UI: a "Disruption type" segmented control (`transit | production`)
   that maps to the two parameter families; production mode swaps the severity
   slider label to "Cut (mbpd)".
4. `decide_scenario_params` heuristic: sanctions-dominant factor + Supplier
   entity → production-type scenario.
**Rubric effect:** Area 2 word-for-word complete; Innovation +1 (two disruption
physics, one model).

### G5 — Tanker availability + port congestion in procurement (Area 3 word-for-word)
**Plan:**
1. **Congestion (data already exists):** in `alt_procurement_agent/routing.py`,
   read destination-port `congestion` from the graph and add
   `congestion_delay_days = congestion * max_berth_wait_days` (bundle param,
   sourced from UNCTAD port-performance norms) to lead time, and a demurrage
   cost adder to landed cost. One new TOPSIS input via existing lead/cost dims —
   no schema change.
2. **Tanker availability (new, honest proxy):** the AIS agent already tracks
   vessels per monitored bbox. Maintain `sage:ais:vessel_density:{region}` in
   Redis (count of distinct tanker-class MMSIs seen in the last 24 h per load
   region). In routing, availability factor = density vs a sourced baseline;
   below-baseline regions get a lead-time penalty and a `tanker_availability`
   column in `ProcurementOption` + UI table. Label it in the UI as "AIS-derived
   availability proxy" — honest about what it is.
3. Add both to the rationale prose so the recommendation *narrates* them
   ("Fujairah congestion 0.3 → +1.2d berth wait; VLCC density in Gulf normal").
**Rubric effect:** Area 3 goes ~65%→~95%; eval-focus "quality of alternatives" B+→A.

### G6 — GDP *trajectory* (Area 2's last word)
**Plan:** the Leontief IO model already computes `gdp_loss_pct` from a shortfall
scalar. Call it per-day over `feedstock_gap_timeline` (30 values → 30 IO calls,
milliseconds each) and emit `gdp_trajectory_pct: list[float]` in assumptions.
Plot it as a small line under the Impact tab fan chart ("GDP impact over time").
**Effort:** ~2 hours. Word-for-word closure.

### G7 — Wellhead → distribution twin extension (Area 5)
**Plan (bundle-first, no code changes to the graph engine):**
1. Add two node types to the schema: `ProductionField` (wellhead: field name,
   country, output_mbpd, spare_mbpd) and `DistributionHub` (state-level demand
   node: region, demand_mbpd, product mix). Both are ordinary typed entities —
   `ENTITY_TYPES` pattern already supports adding types.
2. Extend the `.context` bundle: ~15 production fields (Ghawar, Basra fields,
   Upper Zakum, etc. — all public EIA/OPEC data) with `PRODUCES_AT` edges to
   suppliers; ~8 Indian distribution hubs (PPAC state consumption data) with
   `DISTRIBUTES_TO` edges from refineries. All provenance-tracked like existing
   rows.
3. Map layers: two new toggles in Global Intelligence (wellhead markers upstream,
   demand-hub choropleth downstream). ARIO node_impacts naturally extend down the
   new edges via the existing exposure traversal.
4. OPEC+ scenarios (G4) then ground physically: the cut applies at named
   ProductionFields.
**Rubric effect:** Area 5 ~60%→~90%; "full network" becomes literally true.

### G8 — Geospatial evidence depth
**Plan:**
1. **Route geometries:** add polyline coordinates per corridor route to the
   bundle (a dozen well-known shipping lanes; public data). Render as deck.gl
   `PathLayer` — routes become visible lines, bypasses visibly *bypass*.
2. **Vessel evidence trails:** the AIS agent already sees positions; keep a
   rolling 24 h track (downsampled, per monitored vessel) in Redis; on corridor
   click, render recent tracks + dark-gap markers at the H3 cells where gaps
   were detected. This turns "AIS said risk" into *visible evidence*.
3. **Evidence drill-down:** clicking an H3 anomaly cell opens the signals that
   fired there (reuse `get_evidence_for` + `h3_cells` already on signals).
**Rubric effect:** "geospatial evidence depth" B−→A. This is also the single most
demo-visible upgrade.

### G9 — Demo ignition (protects everything else during judging)
**Problem:** an honest fresh deploy is CALM and quiet — correct, but judges see a
static dashboard.
**Plan:** `scripts/demo_ignite.py` — replays a *real, labeled historical event*
(the 2026 Hormuz closure window from the G1 calibration data) through the REAL
ingest path (`push_signal`, marked `replay=true` in payload provenance):
1. Feeds ~20 minutes of compressed real signals → risk visibly climbs on the
   dashboard → threshold crossing fires the REAL autonomous pipeline → agent
   trace narrates every step → scenario/procurement/SPR populate → response-time
   strip (G2) shows the measured number.
2. UI shows a subtle "REPLAY: Hormuz 2026 (labeled historical data)" badge while
   active — honest, not staged; it is the same replay data the model was
   *validated* on, which is a feature, not a hack ("this is the held-out crisis;
   watch SAGE detect it live").
3. One command, self-cleaning (deletes replay-tagged episodes after).
**Rubric effect:** makes every other point *visible*. Also directly demonstrates
"lead time" (replay clock vs detection timestamp).

### G10 — News hybrid LLM extraction (deviation #4 fix)
**Plan:** keep alias-scan as the fast path. Add one conditional Nova Micro call:
`if not entities_found and severity >= 0.7:` → extract entities + a one-line
disruption assessment via `knowledge/bedrock.py`'s existing tool-use path; new
entities route through the registry's novel-entity promotion path. Budget-guarded:
max N calls/hour (env `NEWS_LLM_BUDGET_PER_H`, default 10), counter in Redis.
**Rubric effect:** closes the recall hole cheaply; Technical Excellence +1.

### G11 — Business impact quantification (the missing 25%-criterion evidence)
**Plan:** one page, three numbers, all derivable from work above:
1. **Detection lead:** from G1 LOCO validation — "detected the held-out 2026
   Hormuz closure N hours before the documented disruption onset."
2. **Avoided cost:** from a G9-style replay — compare SAGE's recommended
   procurement (executed at detection time) vs naive spot purchase at
   post-disruption prices: Δ$/bbl × volume = avoided cost per event. Every input
   is already sourced (price series, TOPSIS costs).
3. **Decision speed:** the G2 number (median signal→recommendation seconds) vs
   the manual baseline (procurement desk cycle, cite an industry norm).
Put them in `docs/IMPACT.md` + a "Why it matters" card on the Landing screen.
**Rubric effect:** Business Impact 16–19 → 22–24. Judges get numbers, not vibes.

### G12 — Scalability story (show, don't tell)
**Plan:**
1. Commit `docker-compose.prod.yml` with ECR `image:` refs + a GitHub Action that
   builds/pushes on tag (the deploy doc already describes it; make it exist).
2. One paragraph + diagram in README: horizontal path (sensory agents are
   stateless→N replicas; gateway behind ALB; FalkorDB read replicas), and the
   **bundle-swap demo**: `SAGE_CONTEXT_BUNDLE=data/japan-energy.context` — show a
   second minimal bundle (even 10 entities) actually booting a different
   country's worldview. That artifact makes "scales to any supply chain" a
   demonstrated claim.
3. Bedrock quota mitigation note: the hybrid budget guard (G10) + stub-degradation
   behavior are the honest answer to "what if the LLM is down".
**Rubric effect:** Scalability 11–13 → 13–14.

### G13 — Voice STT real implementation (UX completeness)
**Plan:** `voicebridge/gnani.py` — un-stub `_mode`: implement the real Gnani STT
websocket (the code skeleton is present and commented); env-gate it
(`GNANI_API_KEY` present → real, absent → mock with a visible "voice demo mode"
chip in the orb UI so mock is never silently presented as real). Test end-to-end
on the deployment once wired.
**Rubric effect:** UX 12–13 → 13–14; removes the last "mocked" component.

### G14 — Small word-for-word closures
- **Per-refinery demand curves (Area 4):** refinery nameplate × utilization from
  bundle → per-refinery daily demand vector consumed by SDP's gap input instead
  of the aggregate constant. Modest change in `reserve_optim_agent/runner.py`.
- **"Spot market pricing" (Area 3):** label current pricing honestly in the UI
  ("Clarkson norms + live Brent basis") and add per-grade OSP differentials to
  the bundle (public monthly Saudi/ADNOC OSPs) — closes the phrase without
  needing a paid spot feed.
- **`GET /api/wiki` list endpoint** (secondbrain spec): trivial; enables a wiki
  index page and the speced wiki-graph view later.

---

## Part V — Projected scores after the plan

| Criterion | Weight | Now | After | Delta driver |
|---|---|---|---|---|
| Innovation | 25% | 20–22 | 23–24 | Two-physics scenario model (G4), validated anticipatory detection (G1), evidence-grade geospatial (G8) |
| Business Impact | 25% | 16–19 | 22–24 | Quantified impact page (G11) backed by real validation (G1) and measured latency (G2) |
| Technical Excellence | 20% | 15–17 | 18–19 | Trained+validated model (G1), truth-in-labeling (G3), hybrid extraction (G10), congestion/tanker factors (G5) |
| Scalability | 15% | 11–13 | 13–14 | ECR/CI artifact + bundle-swap demo (G12) |
| User Experience | 15% | 12–13 | 13–14 | Demo ignition (G9), response-time strip (G2), real voice (G13), evidence drill-down (G8) |
| **Total** | | **74–84** | **89–95** | |

A literal 100/100 is not promised by any plan — the honest ceiling on a hackathon
rubric is set by judge subjectivity and field strength. This plan removes every
*findable* deficiency: after it, nothing in the brief's five areas or the
evaluation focus maps to a missing or overclaimed capability, and every judging
criterion has a concrete artifact behind it. That is what a 100-attempt looks
like from the inside.

### Recommended implementation order
1. **G2** (response time — half day, huge rubric leverage)
2. **G1** (fusion training — the accuracy fix; 1–2 days, mostly data building)
3. **G3** (truth-in-labeling — hours)
4. **G9** (demo ignition — depends on G1's replay data)
5. **G5 + G6** (procurement factors + GDP trajectory — word-for-word closures, ~1 day)
6. **G4** (OPEC+ physics — ~1 day)
7. **G11** (impact page — falls out of G1/G2/G9)
8. **G8** (geospatial depth — 1–2 days, most demo-visible)
9. **G7** (wellhead/distribution — 1 day, mostly bundle data)
10. **G10, G12, G13, G14** (as time allows)
