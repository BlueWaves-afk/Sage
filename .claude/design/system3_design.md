# SAGE — System 3: Adaptive Procurement Orchestrator (Build Spec)

> Build-ready spec grounded in the verified KB. System 3 answers: **"Given the supply gap
> System 2 just computed, what are the best alternative crude sources — ranked, executable?"**

## 1. Role

Triggered when a new `ScenarioOutput` appears (System 2 wrote a gap). System 3 finds and ranks
alternative crude procurement options: which supplier, which grade, via which route, at what cost,
lead time, and refinery-grade compatibility. Writes `ProcurementRecData`. System 5 renders it; the
sandbox pre-stages it speculatively.

System 3 does **not** compute the gap (System 2) or decide SPR drawdown (System 4). It turns a gap
into a **ranked, decision-ready procurement plan**.

## 2. KB interface — VERIFIED working

**Reads** (`knowledge/api/read.py`):
- `get_available_suppliers(risk_max=0.4)` → non-sanctioned suppliers with `daily_export_mbpd`,
  `country`, current risk. (A supplier sanctioned 30 min ago by System 1 is already excluded.)
- `get_grade_specs(refinery)` → `CONFIGURED_FOR` edges: grade `api_gravity`, `sulfur_pct`,
  `compatibility`, `yield_pct` per refinery.
- `get_routes(risk_max=0.5)` → corridors with `throughput_mbpd`, current risk, `h3_cells`.
- `BYPASS_ROUTE` edges (in the subgraph) → supplier→port alternatives with `cost_premium`,
  `added_days`.
- Crude assays + maritime cost matrix → bundle (`docs/data.md` §4a, §8a).

**Reads from System 2:** `ScenarioOutputData` (gap_mbpd, gap_duration_days) — scopes the volume to source.

**Writes:** `write_procurement(ProcurementRecData)` → ProcurementRec episode.

## 3. The three computation stages (files to fill — currently stubs)

### 3.1 Grade compatibility — `alt_procurement_agent/grade.py`
**`compatibility_score(supplier_grade_api, supplier_grade_sulfur, refinery_spec) → 0..1`**
- Semi-empirical: Random Forest (trained on assay yield curves) + Peng-Robinson EOS for the
  yield/processing penalty of running a grade outside a refinery's configured envelope.
- Inputs: the grade's API/sulfur (from `get_grade_specs` / crude_grades bundle), the refinery's
  configured grades. Output: a 0..1 fit score (1 = drop-in, <0.5 = needs blending).
- Honest path: start with a deterministic API/sulfur-distance score; add the RF (trained on the
  assay yield curves in the bundle) as the "domain depth" upgrade.

### 3.2 Maritime routing — `alt_procurement_agent/routing.py`
**`solve(suppliers, ports, corridors, volumes) → {supplier: [corridor, port]}`**
- OR-Tools MILP over an asymmetric cost matrix: great-circle distance (from the seeded coordinates)
  + canal/transit fees + war-risk premium (from corridor risk) + `BYPASS_ROUTE` premiums.
- Respects open corridors only (`get_routes(risk_max)` excludes blocked ones → Yanbu/Fujairah
  bypass surfaces automatically when Hormuz risk is high).
- Cost-matrix data: `docs/data.md` §8a (distances, Suez tolls, war-risk).

### 3.3 Multi-objective ranking — `alt_procurement_agent/rank.py`
**`rank(options) → ordered options with topsis_score`**
- TOPSIS over: landed cost, lead time, grade compatibility, corridor risk (weights in the spec /
  bundle). Produces the ranked list with a trade-off explanation.
- Nova Pro generates a one-paragraph rationale per top option, cited to graph sources.

## 4. Runner — `alt_procurement_agent/runner.py`

```
run(scenario_id, trigger_refinery, status):
  suppliers = get_available_suppliers(risk_max=0.4)      # non-sanctioned, low-risk
  grades    = get_grade_specs(trigger_refinery)          # what the refinery can run
  routes    = get_routes(risk_max=0.5)                   # open corridors + bypass
  for each supplier×grade×route:
      compat = grade.compatibility_score(...)
      route  = routing.solve(...)
      build ProcurementOption(cost, lead_time, compat, corridor_risk)
  ranked = rank.rank(options)                            # TOPSIS
  rationale via Nova Pro for top-3
  write_procurement(ProcurementRecData(scenario_id, ranked))
```

## 5. Output contract — `ProcurementRecData` (contracts/outputs.py)
Ranked `ProcurementOption`s: supplier, grade, route_via, landed_cost_usd_bbl, lead_time_days,
grade_compatibility, corridor_risk, topsis_score, score_breakdown, rationale.

## 6. Data sufficiency
✅ Suppliers, grades, routes, bypass edges, crude assays, maritime cost matrix all in the KB/bundle.
⚠️ The RF grade model wants full assay *yield curves* (representative in bundle §4a; refine from PDFs).
Routing distances are computable from seeded coordinates. **System 3 can be built against the live KB now.**

## 7. Build order
1. `grade.py` deterministic API/sulfur compatibility (testable standalone). 2. `routing.py` OR-Tools
MILP. 3. `rank.py` TOPSIS. 4. `runner.py` wiring + Nova Pro rationale. 5. RF grade upgrade.
