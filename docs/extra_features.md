# SAGE — Extra Features & Roadmap

> Status of every remaining gap and proposed feature, with implementation path and
> rubric impact. Items are marked **✅ Done**, **🔷 Backend-ready** (works via API,
> needs a UI panel), or **⬜ Planned**. Ordered by rubric-points-per-effort.

---

## Shipped this session

| Item | Status | Evidence |
|------|--------|----------|
| End-to-end response time on autonomous runs (G2) | ✅ Done | Command Center "Signal → Recommendation" strip; `GET /api/response-time` |
| Wellhead → distribution twin (G7) | ✅ Done | 18 ProductionField/DistributionHub nodes on the map; `GET /api/graph` |
| Pipeline entity allowlist + fire cooldown | ✅ Done | `orchestration/monitor.py` — only supply-chain types fire; 600s cooldown |
| Bundle validation repair | ✅ Done | `load_bundle()` was failing (36 issues); manifest now declares all G7 sources |
| Per-refinery demand curves (Area 4 / G14) | ✅ Done | `refineries.csv` utilization_pct → 0.43 MMT/day per-refinery, not aggregate |
| Business-impact card + claims ledger | ✅ Done | Landing impact card; `docs/EVALUATION.md`, `docs/IMPACT.md` |
| Durable image (agents baked) | ✅ Done | `docker/sage_core.Dockerfile`; reproducible `--profile sensory --profile agents up -d` |

---

## Features worth adding (highest rubric leverage)

### 1. Geospatial evidence drill-down — 🔷 Backend-ready
**What:** Click a node / H3 cell on the map → the actual signals that fired there
(the AIS dark-vessel gap, the news item, the sanction), with timestamps and source.
Turns "points on a map" into *evidence depth* — the review's B+ → A move, and the
single most demo-visible upgrade.
**State:** Backend already serves it — `GET /api/evidence/{entity}` (`get_evidence_for`,
returns `IntelSignal` with `h3_cells`). The map already has an `onNodeClick` handler
(`KnowledgeGraphMap.tsx:399`). **Remaining:** a right-rail "Evidence" panel that, on
node select, fetches `/api/evidence/{name}` and renders the signal list + a
"jump to cell" on the map; and routing demo signals through the real ingest path so
the panel is populated during a replay (the inline-fusion demo currently writes risk
state directly and doesn't create per-signal evidence records).
**Effort:** ~1 day (frontend panel + demo signal-path). **Rubric:** Geospatial depth
B+ → A; UX +1.

### 2. Tornado / sensitivity chart in the Simulation Lab — ⬜ Planned
**What:** For a scenario, vary each assumption ±1σ and rank the swing in the outcome
(gap_mbpd / price_impact). Shows *which assumption matters most*.
**Why:** SAGE's strongest evaluation phrase is "assumptions must be explicit and
testable" — this is its showpiece. Every ARIO coefficient is already provenance-typed
(`value/unit/source`), so the inputs exist.
**Path:** New `POST /api/scenario/sensitivity` that re-runs ARIO holding all-but-one
assumption fixed (ARIO is ~0.04 ms/run, so 15 vars × 2 = 30 runs = trivial); render
as a horizontal tornado bar in `ImpactTab`.
**Effort:** ~1 day. **Rubric:** Technical Excellence +1, scenario-fidelity showpiece.

### 3. Re-run-with-mitigation — ⬜ Planned
**What:** After a scenario, one click applies SAGE's own top procurement + SPR draw
and re-simulates the *residual* gap — demonstrating the value loop end to end
("here's the disruption; here's SAGE's fix; here's the gap after the fix").
**Path:** Reuse the counterfactual sandbox fork; seed it with the procurement
reallocation + SPR schedule as inputs; diff the two ARIO node-impact vectors.
**Effort:** ~1 day. **Rubric:** Business Impact +1 (value made tangible).

### 4. Confusion-matrix / calibration-curve panel — ⬜ Planned
**What:** Make the 0.8409 LOCO AUC *visual*: a reliability curve (predicted vs
observed crossing rate) and a per-crisis LOCO bar chart, fed by `GET /api/accuracy`
and `docs/CALIBRATION_REPORT.md`.
**Path:** Static data already exists in the model `meta` + accuracy endpoint; a small
XAI card in the Command Center. No backend work.
**Effort:** ~half day. **Rubric:** Technical Excellence +1; makes "accuracy" concrete.

### 5. Alert → recommendation timeline ribbon — ⬜ Planned
**What:** A horizontal ribbon: signal → risk → scenario → procurement → SPR with the
measured per-stage deltas already computed in `/api/response-time`. Reinforces the
"demonstrated response time" story visually beyond the single number.
**Effort:** ~half day (pure frontend; data exists). **Rubric:** UX +1.

### 6. Bundle-swap live demo (scalability proof) — ⬜ Planned
**What:** Boot `data/japan-energy.context` on a second port to show a different
country's worldview from the same engine — converts "scales to any supply chain"
from claim to demonstrated artifact.
**Path:** `SAGE_CONTEXT_BUNDLE=data/japan-energy.context docker compose up` a second
gateway; the bundle already exists (10-entity minimal).
**Effort:** ~half day. **Rubric:** Scalability +1–2.

---

## Remaining gaps (lower priority / external dependency)

| Gap | Status | Note |
|-----|--------|------|
| Voice STT real | ⬜ Needs `GNANI_API_KEY` | Code is env-gated (real when key present, mock otherwise, honest "VOICE DEMO MODE" chip). Set the key to activate. |
| OPEC+ production physics (Area 2) | ✅ Done | `supply_cut_mbpd` in ARIO; `opec_cut` preset. |
| GDP trajectory (Area 2) | ✅ Done | `gdp_trajectory_pct` per-day in scenario output. |
| Tanker availability + port congestion (Area 3) | ✅ Done | AIS-density proxy + berth-wait/demurrage in TOPSIS. |
| Power-sector = grid model, not Leontief scalar | ⬜ Planned (low) | Defensible as a reduced-form IO shortfall; full grid model is out of scope. |
| Last-mile distribution nodes (Area 5) | ⬜ Planned (low) | Twin reaches state-hub level; retail last-mile is a bundle-data extension. |
| Horizontal-scale live demo | ⬜ Planned (medium) | Single-box deploy; ECR/CI artifact + bundle-swap (item 6) are the scalability story. |

---

## Suggested build order (from here to the 92–95 ceiling)

1. **#1 Evidence drill-down** — biggest demo-visible lever (geospatial depth → A).
2. **#4 Calibration panel** — half-day, makes accuracy visual.
3. **#2 Tornado chart** — showpiece for the strongest eval phrase.
4. **#5 Timeline ribbon** + **#6 bundle-swap** — half-day each, UX + scalability.
5. **#3 Re-run-with-mitigation** — the value-loop closer.

A literal 100/100 is bounded by judge subjectivity; this roadmap removes every
*findable* deficiency and gives each rubric criterion a concrete, demo-able artifact.
