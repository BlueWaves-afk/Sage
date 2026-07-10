# Simulation Lab Redesign — Surfacing System 2/3/4 as a Disruption Scenario Modeller

**Status:** Design spec — ready for implementation
**Author:** SAGE team
**Date:** 2026-07-10
**Screen:** `visualizer_agent/frontend/src/screens/SimulationLab.tsx` (route `/simulation`)

---

## 1. Problem Statement

SAGE's backend (Systems 2/3/4) is a genuinely sophisticated oil-supply disruption
modeller — ARIO cascade, 300-path Monte Carlo, agent-based refinery competition,
Leontief IO sector cascade, constrained-MDP SPR optimisation with real-options
valuation, and graph-driven per-node impact propagation. **Almost none of this
surfaces in the UI.**

The current Simulation Lab:
- Shows whatever scenario happens to be cached; the user cannot *choose* a scenario.
- Has a scrubber and "Execute Run" button that do nothing.
- Has decorative, non-functional map-layer checkboxes.
- Shows only the top-1 procurement option and a bullet list of sector impacts.
- Never shows Monte Carlo bands, node cascade, SPR schedule, or counterfactuals.

**Goal:** Turn Simulation Lab into an interactive disruption scenario modeller that
lets a user configure a scenario, run it, and read back the full model output in
the visual language industry tools use (fan charts, cascade tables, waterfalls,
SPR bar charts, ranked procurement, scenario comparison).

---

## 2. What Industry Tools Do (benchmark)

From research (IEA OMR, Everstream, Resilinc, Wood Mackenzie, Vortexa/Kpler,
Nature 2025 MILP+MC downstream oil paper, R-ARIO):

**Standard inputs a user sets** (kept minimal — presets + 3-5 knobs):
- Scenario preset (Hormuz Full Closure, Red Sea Tanker Ban, Supplier Sanction, …)
- Severity (% capacity lost), Duration (days), Escalation shape
- Recovery/SPR policy, demand elasticity

**Standard outputs shown:**
- Supply-gap timeline with Monte Carlo p10/p50/p90 fan chart
- Node cascade (which refineries hit, when, how badly)
- Sector impact cascade (transport → power → food …)
- Procurement alternatives comparison table
- SPR drawdown schedule + days-cover curve
- Scenario comparison (baseline vs disruption variants)
- Sensitivity / tornado (which input drives variance)
- Narrative explanation of *why*

**Key UX patterns:** presets + sensitivity knobs (not raw params); side-by-side
baseline vs disrupted; "re-run with mitigation" loop; geographic overlay;
layered complexity (basic → advanced → expert); narrative explanations.

SAGE already computes all the underlying quantities. This redesign is **90%
frontend surfacing + 10% a new POST run endpoint.**

---

## 3. Backend Additions

The scenario runner is directly callable:
`scenario_agent.runner.run(trigger_entity, status="confirmed", scenario=<dict>)`
returns `scenario_id`. Parameters accepted in `scenario`:
`disruption_fraction (0..1)`, `disruption_days (int)`,
`escalation_profile ("constant"|"escalating"|"resolving")`,
`bypass_compromised_frac (0..1)`, `spr_policy ("aggressive"|"moderate"|"none")`,
`demand_destruction_pct (0..0.3)`, `horizon_days (int)`.

Monte Carlo bands are already produced (`assumptions.monte_carlo`) with shape:
```json
{ "gap_mbpd": {"p10":_, "p50":_, "p90":_},
  "price_impact_usd": {"low":_, "high":_},
  "spr_depletion_days": {"p10":_, "p50":_, "p90":_}, "n": 300 }
```

### 3.1 New endpoints (`visualizer_agent/api_gateway/main.py`)

**`POST /api/scenario/run`**
Body:
```json
{
  "entity": "Strait of Hormuz",
  "disruption_fraction": 0.8,
  "disruption_days": 14,
  "escalation_profile": "constant",
  "bypass_compromised_frac": 0.0,
  "spr_policy": "aggressive",
  "demand_destruction_pct": 0.0,
  "run_downstream": true
}
```
Behaviour:
- Generates a `run_id` (uuid) immediately, stores status `{stage:"scenario", pct:0}`
  in an in-process dict `RUN_STATUS[run_id]` (and/or Redis key `sage:run:{run_id}`).
- Launches an `asyncio.create_task` that:
  1. `scenario_id = await scenario_agent.runner.run(entity, "confirmed", scenario_dict)`
     → update status `stage:"procurement", pct:40`
  2. If `run_downstream`: resolve most-exposed refinery (via EXPOSES edges — reuse
     the logic in `orchestration/graph.py` procure_node), then
     `await alt_procurement_agent.runner.run(scenario_id, refinery)`
     → status `stage:"reserve", pct:70`
  3. If `run_downstream`: read the scenario back for `gap_mbpd`/`gap_duration_days`/
     `escalation_profile`, then
     `await reserve_optim_agent.runner.run(scenario_id, gap_mbpd, gap_duration_days, escalation_profile)`
     → status `stage:"done", pct:100, scenario_id`
  - On exception: status `stage:"error", error:str`.
- Returns `{ "run_id": "...", "scenario_id": null }` (scenario_id filled once done).

Reuse the exact downstream wiring already in `orchestration/graph.py`
(`run_response_pipeline`) rather than re-deriving it. If that function can accept an
explicit scenario-param dict, prefer calling a thin wrapper over it; otherwise call
the three runners directly as above. **Do not fabricate the refinery-resolution
logic — copy it from graph.py's procure_node.**

**`GET /api/scenario/status/{run_id}`**
Returns `{ stage, pct, scenario_id, error }`. Frontend polls every ~1.2s until
`stage === "done"` or `"error"`, then fetches `/api/scenario?scenario_id=…`,
`/api/procurement?scenario_id=…`, `/api/spr-schedule?scenario_id=…`.

**`GET /api/scenario/presets`** (static, from a small module constant)
Returns an array of scenario presets so the UI and backend agree:
```json
[
  {"id":"hormuz_full","label":"Strait of Hormuz — Full Closure","entity":"Strait of Hormuz",
   "disruption_fraction":1.0,"disruption_days":21,"escalation_profile":"constant",
   "bypass_compromised_frac":0.0,"spr_policy":"aggressive","demand_destruction_pct":0.05,
   "blurb":"Complete Hormuz blockage; ~20% of global seaborne crude halted."},
  {"id":"hormuz_partial","label":"Hormuz — Contained Confrontation","entity":"Strait of Hormuz",
   "disruption_fraction":0.4,"disruption_days":10,"escalation_profile":"escalating",
   "bypass_compromised_frac":0.0,"spr_policy":"moderate","demand_destruction_pct":0.0,
   "blurb":"Partial closure / harassment; insurance + rerouting friction."},
  {"id":"redsea_hormuz","label":"Red Sea + Hormuz — Bypass Compromised","entity":"Strait of Hormuz",
   "disruption_fraction":0.7,"disruption_days":18,"escalation_profile":"constant",
   "bypass_compromised_frac":1.0,"spr_policy":"aggressive","demand_destruction_pct":0.05,
   "blurb":"Simultaneous chokepoint stress removes the Petroline/ADCOP bypass relief."},
  {"id":"supplier_sanction","label":"Major Supplier Sanctioned","entity":"Strait of Hormuz",
   "disruption_fraction":0.3,"disruption_days":45,"escalation_profile":"constant",
   "bypass_compromised_frac":0.0,"spr_policy":"moderate","demand_destruction_pct":0.0,
   "blurb":"Long-duration sourcing loss; procurement substitution dominates."}
]
```
Keep the preset list in a new module `orchestration/scenario_presets.py` so the
POST endpoint can validate `entity` against known corridors.

> Note: presets all trigger on a corridor entity that exists in the graph. Verify
> the entity names against `get_risk_scores()` / graph node names before shipping —
> if "Strait of Hormuz" is stored differently, use the stored name.

### 3.2 Files touched (backend)
- `visualizer_agent/api_gateway/main.py` — 3 endpoints + `RUN_STATUS` dict + run task.
- `orchestration/scenario_presets.py` — NEW, preset constants + validation helper.
- Reuse (no change): `scenario_agent/runner.py`, `alt_procurement_agent/runner.py`,
  `reserve_optim_agent/runner.py`, `orchestration/graph.py` (copy refinery-resolution).

---

## 4. Frontend Data Layer

### 4.1 `api/client.ts` additions
```ts
runScenario: (body: ScenarioRunRequest) =>
  post<{ run_id: string; scenario_id: string | null }>("/api/scenario/run", body),
scenarioStatus: (runId: string) =>
  get<ScenarioRunStatus>(`/api/scenario/status/${encodeURIComponent(runId)}`),
scenarioPresets: () => get<ScenarioPreset[]>("/api/scenario/presets"),
scenarioById: (id: string) => get<ScenarioOutput>(`/api/scenario?scenario_id=${encodeURIComponent(id)}`),
procurementById: (id: string) => get<ProcurementRecData>(`/api/procurement?scenario_id=${encodeURIComponent(id)}`),
sprScheduleById: (id: string) => get<SprSchedule>(`/api/spr-schedule?scenario_id=${encodeURIComponent(id)}`),
```
Add a small `post<T>()` helper mirroring the existing `get<T>()` envelope pattern
(the copilot call already POSTs — factor a shared `post`).

### 4.2 `api/types.ts` additions
```ts
export interface ScenarioRunRequest {
  entity: string;
  disruption_fraction: number;
  disruption_days: number;
  escalation_profile: "constant" | "escalating" | "resolving";
  bypass_compromised_frac: number;
  spr_policy: "aggressive" | "moderate" | "none";
  demand_destruction_pct: number;
  run_downstream: boolean;
}
export interface ScenarioRunStatus {
  stage: "scenario" | "procurement" | "reserve" | "done" | "error";
  pct: number;
  scenario_id: string | null;
  error?: string | null;
}
export interface ScenarioPreset {
  id: string; label: string; entity: string;
  disruption_fraction: number; disruption_days: number;
  escalation_profile: "constant" | "escalating" | "resolving";
  bypass_compromised_frac: number; spr_policy: "aggressive" | "moderate" | "none";
  demand_destruction_pct: number; blurb: string;
}
// Monte Carlo band accessor (lives inside ScenarioOutput.assumptions.monte_carlo)
export interface MonteCarloBands {
  gap_mbpd: { p10: number; p50: number; p90: number };
  price_impact_usd: { low: number; high: number };
  spr_depletion_days: { p10: number; p50: number; p90: number };
  n: number;
}
```
`ScenarioOutput`, `ProcurementRecData`, `SprSchedule`, `ScoreBreakdown` already
exist in types.ts — reuse them. `assumptions` is `Record<string, AssumptionEntry>`;
`monte_carlo`, `io_cascade`, `abm_emergent` are nested dicts under it, so read them
defensively with `as unknown as MonteCarloBands`.

---

## 5. Screen Layout

Replace the current Simulation Lab body. Grid (desktop):

```
┌───────────────────────────────────────────────────────────────────────────┐
│ CONTROL BAR: env badge · active scenario name · status badge · Reset       │
├──────────────────────┬────────────────────────────────────────────────────┤
│  SCENARIO BUILDER     │  RESULTS TABS: [Impact] [Cascade] [Procurement]     │
│  (left rail, ~300px)  │               [Reserve] [Compare]                   │
│                       │                                                     │
│  • Preset cards       │  ── tab content fills the rest ──                   │
│  • Entity (locked to  │                                                     │
│    preset / picker)   │                                                     │
│  • Severity slider    │                                                     │
│  • Duration slider    │                                                     │
│  • Escalation segmented│                                                     │
│  • Bypass toggle      │                                                     │
│  • SPR policy segmented│                                                     │
│  • Demand destruction │                                                     │
│  • [Run Simulation]   │                                                     │
│    (progress bar when │                                                     │
│     running)          │                                                     │
└──────────────────────┴────────────────────────────────────────────────────┘
```

Mobile / <1200px: builder stacks above results.

### 5.1 Scenario Builder (left rail) — component `ScenarioBuilder`
- **Preset cards**: fetched from `/api/scenario/presets`. Clicking a preset loads
  its params into the builder state (and sets `entity`). Selected card highlighted.
- **Controls** (all controlled React state, seeded from preset, user-overridable):
  - Severity: slider 0–100% → `disruption_fraction` (÷100).
  - Duration: slider 1–90 days → `disruption_days`.
  - Escalation: segmented `constant | escalating | resolving`.
  - Bypass compromised: toggle → `bypass_compromised_frac` 0 or 1.
  - SPR policy: segmented `aggressive | moderate | none`.
  - Demand destruction: slider 0–30% → `demand_destruction_pct` (÷100).
  - `run_downstream`: checkbox "Also run procurement + reserve" (default on).
- **Run Simulation** button → `api.runScenario(body)`; on `run_id`, begin polling
  `api.scenarioStatus`. Show an inline progress bar labelled by `stage`
  (Scenario → Procurement → Reserve → Done). Disable the button while running.
- On `done`: fetch scenario/procurement/spr by `scenario_id`, store in screen state.
- On `error`: show inline error; re-enable button.

**Fallback:** on mount, also load the latest cached scenario/procurement/spr
(existing `api.scenario`/`api.procurement`/`api.sprSchedule`) so the screen is never
empty before the first run. A run replaces them.

### 5.2 Results — Tab 1: **Impact** (headline)
- **KPI strip** (from ScenarioOutput): Peak Gap (`gap_mbpd`) mbpd · Gap Duration
  (`gap_duration_days`) d · Price Impact (`price_impact_low`–`price_impact_high`)
  $/bbl · GDP hit (`gdp_proxy_impact_pct`) % · Inflation (`inflation_impact_pct`) %
  · SPR depletion (`spr_depletion_days`) d · Confidence (`confidence`).
  Each KPI shows the p50 with p10/p90 subscript where a MC band exists.
- **Fan chart** (recharts `ComposedChart` / `AreaChart`): x = day index of
  `feedstock_gap_timeline`; render the deterministic `feedstock_gap_timeline` as the
  solid p50 line, and a shaded band scaled by the MC ratio
  (`monte_carlo.gap_mbpd.p10/p50` and `.p90/p50`) applied to the timeline so the
  band is visually consistent with the headline gap. Label the band
  "Monte Carlo p10–p90 (n=300)". If `monte_carlo` missing, show the line only.
- **Narrative**: render the scenario rationale (from
  `assumptions.scenario_rationale` if present, else the trigger + params) via the
  existing `RichText` component with wikilink support. Include one auto-generated
  sentence: "Gap peaks at X mbpd on day D; SPR covers Y days; Brent +$L–$H/bbl."

### 5.3 Results — Tab 2: **Cascade** (node + sector)
- **Node cascade table** (`node_impacts`, sorted by `peak_gap_mbpd` desc):
  columns Node · Type · Exposure (bar 0–1) · Peak Gap (mbpd) · Onset (day).
  Row click → opens `WikiDrawer` for that node. Onset rendered on a mini timeline.
- **Sector waterfall** (`sector_impacts`): horizontal bar chart, one bar per sector,
  length = `shortfall_mbpd`, colour intensity = `criticality`, label shows
  `petroleum_share`. Sort by `shortfall_mbpd` desc. This is the IO Leontief cascade.
- If `assumptions.abm_emergent` present, a small callout: "N refineries rationing ·
  bypass utilisation X% · stabilises in D days" (ABM emergent block).

### 5.4 Results — Tab 3: **Procurement** (`ProcurementRecData`)
- **Ranked table** of `ranked[]`: Rank · Supplier · Grade · Route · Landed $/bbl ·
  Lead (d) · Grade fit · Corridor risk · **TOPSIS score** (bar). Top row emphasised.
- **Score-breakdown radar / bars** for the selected row using
  `score_breakdown` (cost/lead_time/grade_compatibility/corridor_risk/carbon/
  reliability/political_stability/insurance) — recharts `RadarChart` if available,
  else stacked mini-bars. Show `weights_used` in a tooltip.
- **Rationale** for the selected option via `RichText` (Nova Pro prose, cited).
- Target refinery shown from `target_refinery`.

### 5.5 Results — Tab 4: **Reserve** (`SprSchedule`)
- **SPR drawdown bar chart** (`daily_plan`): x = day; bar = `volume_mmt`; colour by
  `action` (draw = amber, hold = grey, refill = green). Overlay a line for
  `days_cover_after`, and a dashed horizontal line at the 3-day buffer.
- **Constraint strip**: `prob_above_buffer` (%) · `constraint_satisfied` (badge) ·
  `lagrange_multiplier` (constraint tightness) · `option_value_of_waiting` ($/bbl).
- **Policy memo** via `RichText` (Nova Pro memo).

### 5.6 Results — Tab 5: **Compare** (scenario comparison)
- Keep a client-side list of the last up-to-3 runs (id, label, key metrics).
- Side-by-side cards comparing Peak Gap · Price Impact · GDP hit · SPR depletion ·
  Days rationing. Include the current baseline (cached scenario) as the reference
  column. This is the industry "baseline vs disruption variants" view.
- **Sensitivity note** (light version): if two runs differ by one knob, show the
  delta ("+7 days duration → +0.4 mbpd peak gap"). Full tornado is a stretch goal.

### 5.7 Keep from current screen
- The dual current/projected map is still valuable — move it to the **Impact** tab
  header (current vs projected node colours) OR keep it as a compact strip above the
  tabs. Wire the projected map to the *active run's* `node_impacts` (it already uses
  `projectNodes(nodes, node_impacts)`), not just the cached scenario.
- The Impact Horizon Timeline (existing `horizonPoints`) belongs in the Impact tab.

---

## 6. Component / File Plan (frontend)

New components under `visualizer_agent/frontend/src/components/sim/`:
- `ScenarioBuilder.tsx` — left rail, presets + controls + run/poll logic.
- `ImpactTab.tsx` — KPI strip + fan chart + narrative + horizon timeline.
- `CascadeTab.tsx` — node table + sector waterfall + ABM callout.
- `ProcurementTab.tsx` — ranked table + score breakdown + rationale.
- `ReserveTab.tsx` — SPR bar chart + constraint strip + memo.
- `CompareTab.tsx` — multi-run comparison.
- `GapFanChart.tsx`, `SectorWaterfall.tsx`, `SprBarChart.tsx`,
  `ScoreBreakdown.tsx` — small chart building blocks (recharts).

Rewrite:
- `screens/SimulationLab.tsx` — orchestrates builder + tabs + shared run state.
- `screens/simulation.css` — new grid + tab styling (reuse existing tokens/vars).

Data:
- `api/client.ts`, `api/types.ts` — endpoints + types above.
- `api/hooks.ts` — no change needed if using the existing `useApi`/manual fetch.

Charts library: **recharts** (already installed). Reuse the chart styling from the
Global Intelligence timeline/SPR charts for visual consistency (dark grid, cyan/
amber palette, small fonts).

---

## 7. State Model (SimulationLab)

```ts
type RunState = {
  runId: string | null;
  running: boolean;
  stage: ScenarioRunStatus["stage"] | null;
  pct: number;
  error: string | null;
  scenarioId: string | null;
};
// active results
const [scenario, setScenario]   = useState<ScenarioOutput | null>(cachedScenario);
const [procurement, setProc]    = useState<ProcurementRecData | null>(cachedProc);
const [spr, setSpr]             = useState<SprSchedule | null>(cachedSpr);
const [runs, setRuns]           = useState<RunSummary[]>([]); // for Compare tab
const [tab, setTab]             = useState<"impact"|"cascade"|"procurement"|"reserve"|"compare">("impact");
```
Polling: `setInterval` (or recursive `setTimeout`) at 1200ms while `running`; clear
on `done`/`error`/unmount. On `done`, fetch the three outputs by id, push a
`RunSummary` into `runs` (cap 3), switch to Impact tab.

---

## 8. Guardrails / Non-negotiables

1. **No fabricated data.** Every number rendered comes from a real API response.
   If a field is missing, show "—" or an explicit "not computed" note — never a
   placeholder value. This matches the existing STRICT client contract.
2. **Verify entity names** against the graph before shipping presets. If
   "Strait of Hormuz" is stored under a different display name, use the stored one.
3. **Reuse downstream wiring** from `orchestration/graph.py` for refinery
   resolution — do not re-invent EXPOSES traversal.
4. **Long runs:** cold pipeline can take ~8s. The progress bar + stage labels are
   mandatory so the UI never looks frozen. Poll, don't block.
5. **Cache-first mount:** screen must render the latest cached run instantly, then
   let the user launch a fresh one.
6. **Backend bind-mounts** already hot-reload gateway + knowledge; a
   `docker compose restart api-gateway` picks up the new endpoints without rebuild.
   Frontend needs `docker compose build frontend && up -d frontend`.

---

## 9. Implementation Order (for the Sonnet pass)

1. **Backend first** (verifiable via curl before any UI):
   a. `orchestration/scenario_presets.py` (constants + entity validation).
   b. `POST /api/scenario/run`, `GET /api/scenario/status/{id}`,
      `GET /api/scenario/presets` in `main.py` (+ `RUN_STATUS` dict + run task).
   c. Restart gateway; `curl` a run end-to-end; confirm status transitions and that
      `/api/scenario?scenario_id=…` returns the produced output.
2. **Data layer:** `post` helper + client methods + types.
3. **Shell:** rewrite SimulationLab layout (builder rail + tab bar + cache-first
   mount). Ship with just the Impact tab wired.
4. **Charts, tab by tab:** GapFanChart → Impact; node table + SectorWaterfall →
   Cascade; ranked table + ScoreBreakdown → Procurement; SprBarChart → Reserve;
   CompareTab last.
5. **Build + deploy**, verify each tab against a real run, screenshot proof.

Each step is independently shippable; do not batch all charts before verifying the
run pipeline works end-to-end.

---

## 10. Stretch Goals (only if time remains)

- Full **tornado/sensitivity** chart: run the scenario N times perturbing one knob,
  plot each knob's swing on peak gap.
- **Export to PDF** of the active scenario dashboard.
- **"Re-run with mitigation"** shortcut: from Reserve tab, bump SPR policy and
  re-run to show the delta on the Impact tab.
- Surface `counterfactual_type` runs as first-class Compare columns.
