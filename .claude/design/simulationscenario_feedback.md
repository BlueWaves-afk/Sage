# Simulation Lab — Self-Evolving Scenario Library & Continuous Learning Loop

**Status:** Design spec — ready for phased implementation
**Author:** SAGE team
**Date:** 2026-07-10
**Depends on:** `.claude/design/system2_ui_redesign.md` (the Simulation Lab rebuild — shipped)
**Screens:** `screens/SimulationLab.tsx`, new accuracy/feedback surfaces
**Backend:** `visualizer_agent/api_gateway/main.py`, `knowledge/feedback.py`,
`knowledge/api/write.py` + `read.py`, `orchestration/monitor.py`,
`orchestration/scenario_params.py`

---

## 0. The Two Questions This Spec Answers

The user asked, verbatim:

> **Q1.** Can my system simulate specific events, and compute cascading impacts on
> refinery run rates, domestic fuel prices, power sector stress, and GDP trajectory
> under each scenario?
>
> **Q2.** Can my system also continuously evolve and learn from new critical
> scenarios and add those scenarios to my simulation lab?

**Q1 — Yes, today (with one honesty caveat).** The backend already computes every
one of those axes per run. This spec does *not* re-build them; §2 documents exactly
where each lives and flags the two that are proxies rather than first-class models,
so the UI never over-claims.

**Q2 — Partially today; this spec closes the loop.** The *feedback* machinery and
the *auto-trigger* machinery both exist but are disconnected from the Simulation
Lab and from System 2's parameters. This spec is 80% wiring existing pieces
together + 20% new persistence, split into two independent features:

- **Feature A — Dynamic Scenario Library** (§4): surface auto-triggered *and*
  user-run scenarios as first-class, persisted, promotable presets in the lab.
- **Feature B — Continuous Learning Loop** (§5): capture realized outcomes for
  scenarios (not just risk crossings), compare predicted-vs-actual, and calibrate
  **System 2 scenario parameters** — not only the System 1 risk model that today's
  loop already touches.

---

## 1. What Exists Today (grounded in code, not aspiration)

### 1.1 The feedback loop (`knowledge/feedback.py`) — REAL, but narrow
- `record_confirmed_outcome(...)` / `record_expired_outcome(...)` append JSON-lines
  to `demo_cache/feedback_log.jsonl` and write a feedback **episode** back into
  Graphiti (so the copilot can cite accuracy history).
- `get_accuracy_summary()` returns `{total_predictions, confirmed,
  expired_false_positives, precision, mean_lead_time_error_hours,
  records_until_retrain}` — exposed at `GET /api/accuracy`.
- `_maybe_trigger_retrain()` fires at `RETRAIN_THRESHOLD = 50` records — but today
  it only **prints** `Run python -m sensory_agent.fusion --calibrate` (a TODO for a
  real job queue).
- **Scope limit:** every field is about the **risk-crossing prediction** (System 1
  fusion) — confidence calibration, lead-time error. Nothing about whether the
  **scenario's** predicted gap/price/GDP was right. The label
  `within_24h_of_crossing` re-trains the *fusion GBM*, not ARIO.

### 1.2 The auto-trigger (`orchestration/monitor.py`) — REAL
- Polls risk state; on `score >= ACTION_THRESHOLD` (band transition into action)
  calls `on_action(entity, score, scenario_ref)` → runs the response pipeline
  (scenario → procure → reserve), storing outputs.
- Tracks pending scenarios in `sage:pending:{entity}` (72h TTL); on expiry without
  a crossing, calls `record_expired_outcome(...)` → a false-positive feedback event.
- **So:** the system *already* generates new scenarios autonomously when reality
  crosses a threshold. They land in Redis. **Nothing surfaces them in the lab.**

### 1.3 Scenario persistence (`knowledge/api/write.py::_cache_output`) — REAL, thin
- Every run writes `sage:scenario:{id}` + `sage:scenario:latest`
  (also `procurement`, `spr`), **TTL 24h**, via `model_dump()`.
- Stored fields include `trigger_entity`, `status`
  (`speculative|confirmed|counterfactual`), `confidence`, `gap_mbpd`, etc.
- **Gaps for a library:** (a) **no `created_at`** on the payload; (b) **no index** —
  you can only fetch by known id or `latest`; listing requires `SCAN sage:scenario:*`,
  which is unordered and racy; (c) **24h TTL** means history evaporates daily.

### 1.4 Scenario parameterisation (`orchestration/scenario_params.py`) — REAL
- `decide_scenario_params(entity)` → LLM (Nova Pro) translates live risk + factor
  breakdown into `{disruption_fraction, disruption_days, escalation_profile,
  bypass_compromised_frac, spr_policy, demand_destruction_pct, rationale}`;
  deterministic `_heuristic(...)` fallback driven by `_HEURISTIC_DEFAULTS` (which can
  be overridden from the context bundle's `heuristic_params`).
- **This is the natural calibration target for Feature B** — the heuristic
  coefficients and the sanity bounds are exactly what realized outcomes should tune.

### 1.5 Simulation Lab presets — HARDCODED
- `_SCENARIO_PRESETS` is a literal list in `main.py`; `GET /api/scenario/presets`
  returns it. There is no mechanism to add, persist, or learn a preset.

**Summary:** SAGE already *predicts*, *auto-generates*, *stores*, and *scores its own
accuracy*. The missing wiring is: **(A)** promote stored scenarios into the lab, and
**(B)** feed realized scenario outcomes back into System 2's parameters.

---

## 2. Q1 — Cascading Impact Coverage (documentation, not new work)

Per completed run, the model produces, and the rebuilt lab already surfaces:

| Requested axis | Backend field (`ScenarioOutput`) | System | UI location | Fidelity |
|---|---|---|---|---|
| Refinery run rates | `node_impacts[].exposure`, `.peak_gap_mbpd`, `.onset_day` | S2 ARIO node cascade | Cascade tab — node table | **Direct** (per-node gap; expose as % of nameplate — see below) |
| Domestic fuel prices | `price_impact_low/high` + `assumptions.monte_carlo.price_impact_usd` | S2 + MC | Impact KPI strip | **Direct** (Brent Δ + MC band) |
| Power / sector stress | `sector_impacts[]` (petroleum_share, shortfall_mbpd, criticality) | S2 Leontief IO | Cascade waterfall | **Direct** for shortfall; not yet MW/load-shed |
| GDP trajectory | `gdp_proxy_impact_pct` | S2 | Impact KPI strip | **Proxy** (petroleum-share weighted, not a macro model) |

**Two honesty caveats to encode in the UI (guardrail G3):**
1. **GDP is a proxy.** Label it "GDP proxy (petroleum-intensity weighted)", not
   "GDP impact". Do not imply a DSGE/CGE macro model.
2. **Refinery "run rate" is expressed as a feedstock gap**, not a throughput %. Add a
   derived `run_rate_pct = clamp(1 − peak_gap_mbpd / nameplate_mbpd)` in the Cascade
   tab **only if** nameplate capacity exists for that node in the graph; otherwise
   show the raw gap and omit the %. Never fabricate a nameplate.

No backend change required for Q1 beyond the optional derived run-rate (§6.4).

---

## 3. Architecture of the Two Features

```
                        ┌─────────────────────────────────────────┐
   live signals ───────▶│ monitor.py  (ACTION crossing)            │
                        │  → run_response_pipeline (S2→S3→S4)       │
                        └───────────────┬─────────────────────────-┘
                                        │ writes sage:scenario:{id}
                                        ▼
   user "Run Simulation" ──▶ POST /api/scenario/run ──▶ same outputs
                                        │
                 ┌──────────────────────┼──────────────────────┐
                 ▼ (Feature A)          │                      ▼ (Feature B)
        ScenarioLibrary index    (both paths tagged      OutcomeLedger
        sage:scenario:index      origin=auto|user|preset)  realized vs predicted
        + promoted presets                                  → calibrate params
        sage:preset:custom:*                                → scenario_params.py
                 │                                                 │
                 ▼                                                 ▼
        Simulation Lab                                     accuracy panel +
        "Library" section                                 updated heuristics
```

Both features are **independently shippable**. Feature A has zero ML and is pure
plumbing + UI; Feature B is the harder, longer-horizon piece.

---

## 4. Feature A — Dynamic Scenario Library

**Goal:** every scenario the system runs (auto-triggered, user-run, or preset) is
recorded in a durable, ordered index and can be re-opened or **promoted to a named
preset** that appears alongside the four static ones in the builder.

### 4.1 Persistence changes (`knowledge/api/write.py`)
Extend `_cache_output` (scenario kind only) to also:
- Stamp `created_at` (UTC iso) and `origin` (`auto` | `user` | `preset`) into the
  payload **before** `model_dump` caching. Add both to a new
  `write_scenario_index(scenario_id, meta)` helper.
- Maintain a Redis **sorted set** `sage:scenario:index`, score = epoch seconds,
  member = `scenario_id`. This survives the per-key 24h TTL problem only if the
  index entries themselves carry the summary — so also store a compact
  `sage:scenario:meta:{id}` hash `{trigger_entity, origin, gap_mbpd, price_high,
  gdp_proxy, spr_depletion_days, created_at, label}` with a **longer TTL (30d)** than
  the full payload. The full payload can lapse; the library card survives on meta.

> Rationale: keeps full outputs cheap/ephemeral while the *library* (small cards)
> persists a month. Re-running a lapsed scenario is one click (params are in meta).

Threading `origin`: `POST /api/scenario/run` passes `origin="user"`; the monitor's
`on_action` path passes `origin="auto"`; a preset-launched run passes
`origin="preset"` + the preset id. Plumb a single optional `origin`/`label` kwarg
down `scenario_agent.runner.run(...)` → `_cache_output`.

### 4.2 Promoted (custom) presets
- `POST /api/scenario/promote` body `{scenario_id, label, blurb}` → writes
  `sage:preset:custom:{slug}` (hash of the same shape as a static preset, plus
  `source_scenario_id`, `promoted_at`). No TTL (curated).
- `DELETE /api/scenario/promote/{slug}` → remove a custom preset.
- `GET /api/scenario/presets` returns **static ∪ custom**, custom flagged
  `"custom": true` so the UI can badge + allow delete.

### 4.3 New/changed endpoints (`main.py`)
```
GET  /api/scenario/library?limit=20&origin=all|auto|user   → [ScenarioCard]
GET  /api/scenario/presets                                 → [ScenarioPreset]  (now merged)
POST /api/scenario/promote        {scenario_id,label,blurb}→ {slug}
DELETE /api/scenario/promote/{slug}                        → {ok}
```
`ScenarioCard = {scenario_id, label, origin, trigger_entity, gap_mbpd,
price_impact_high, gdp_proxy_impact_pct, spr_depletion_days, created_at,
payload_available: bool}` (read from `sage:scenario:index` + meta hashes).

### 4.4 Frontend (Simulation Lab builder rail)
- New **"Scenario Library"** section below the static preset cards:
  - Tabs/filter chips: `All · Auto-detected · My runs`.
  - Each card: label, origin badge (🛰 auto / 👤 user / ★ preset), trigger entity,
    headline gap + price, relative time ("2h ago"). Click → if `payload_available`,
    load results straight into the tabs; else re-run from meta params.
  - `⋯` menu → **Promote to preset** (opens a small label/blurb dialog → POST) or
    **Delete** (custom presets only).
- **Auto-detected** cards are the literal answer to "add those scenarios to my
  simulation lab": when reality crosses a threshold, the monitor runs a scenario and
  it appears here within one poll cycle — no user action.
- Poll `/api/scenario/library?origin=auto` on a slow interval (e.g. 30s) so freshly
  auto-triggered scenarios surface live; a small "N new" pip when the count grows.

### 4.5 Types (frontend `api/types.ts`)
```ts
export interface ScenarioCard {
  scenario_id: string; label: string; origin: "auto" | "user" | "preset";
  trigger_entity: string; gap_mbpd: number; price_impact_high: number;
  gdp_proxy_impact_pct: number | null; spr_depletion_days: number;
  created_at: string; payload_available: boolean;
}
// ScenarioPreset gains: custom?: boolean; source_scenario_id?: string;
```

### 4.6 Feature A acceptance
- Trigger an ACTION crossing (or curl the monitor path) → within one poll, a card
  with `origin:"auto"` appears under **Auto-detected**.
- Run a user sim → card under **My runs**; promote it → appears as a ★ preset with a
  **custom** badge, survives reload, deletable.
- No fabricated cards: every card maps to a real `sage:scenario:*` entry.

---

## 5. Feature B — Continuous Learning Loop (scenario-level)

**Goal:** move beyond "was the risk crossing real?" to "was the scenario's predicted
*impact* right?", and use that to **calibrate System 2 parameters** — so the lab's
future predictions and auto-scenarios get measurably better.

### 5.1 What's missing vs. §1.1
Today's loop scores the **crossing** (System 1). It never records:
- the **predicted** scenario impact (gap/price/spr) at run time, nor
- the **realized** impact once the event plays out, nor
- any calibration of `scenario_params.py` / ARIO coefficients from that error.

### 5.2 The Outcome Ledger (`knowledge/feedback.py` extension)
Add a parallel ledger `demo_cache/scenario_outcomes.jsonl` and two functions:

```python
async def record_scenario_prediction(scenario_id, entity, params, predicted) -> None
# predicted = {gap_mbpd, price_impact_high, spr_depletion_days, gdp_proxy_pct}
# called automatically right after a scenario run stores output (both auto + user).

async def record_scenario_realized(scenario_id, realized, source) -> None
# realized = subset of the same keys, from real data once the window elapses
# (e.g. actual Brent move from EIA, actual corridor throughput drop from AIS).
# source ∈ {"eia","ais","analyst"}; analyst = manual entry in the UI.
```

Each realized record computes per-axis error (`realized − predicted`) and appends;
`get_scenario_accuracy()` aggregates MAPE per axis + counts. Reuse the existing
Graphiti feedback-episode writer so the copilot can answer
"how accurate have our Hormuz scenarios been?".

**Realized-data capture** has two tiers:
- **Automatic (best-effort):** a slow background task (extend `monitor.py`) that, for
  scenarios older than their `disruption_days` window, pulls the realized Brent delta
  (already in the volatile tier / EIA feed) and realized corridor throughput (AIS
  risk history) and calls `record_scenario_realized(..., source="eia"/"ais")`.
- **Manual (always available):** an **"Log actual outcome"** control on a completed
  scenario (analyst enters what really happened). This guarantees the loop can close
  even when an automatic proxy is unavailable — and is honest about provenance.

### 5.3 Parameter calibration (`orchestration/scenario_params.py`)
Add `calibrate_from_outcomes()`:
- Reads `scenario_outcomes.jsonl`; if `>= CALIB_THRESHOLD` (start at 20) realized
  records exist, fit a **simple, auditable** correction — **not** a black box:
  - a scalar **gap multiplier** and **price multiplier** per corridor that minimize
    MAPE (bounded, e.g. 0.5–1.5), persisted to `sage:calib:params` (hash).
- `decide_scenario_params(...)` and the ARIO gap computation multiply their raw
  output by the learned per-corridor factor (default 1.0 when unlearned).
- **Interpretability guardrail (G4):** learned factors are bounded, per-corridor,
  and shown in the UI ("Hormuz gap est. ×1.12 from 23 realized outcomes"). No opaque
  weights silently altering physics. This keeps the model defensible to a judge.

> We deliberately do **not** auto-retrain ARIO's structural coefficients — those are
> physically meaningful and bundle-sourced. We learn a thin, visible correction layer
> on top, plus continue the existing System-1 fusion recalibration.

### 5.4 Close the existing System-1 TODO too
Replace `_maybe_trigger_retrain()`'s bare print with an actual enqueue: publish
`{"job":"calibrate"}` to a Redis list `sage:jobs`; a tiny worker (or, minimally, the
monitor loop) drains it and runs both `sensory_agent.fusion --calibrate` (System 1)
and `scenario_params.calibrate_from_outcomes()` (System 2). Still logs loudly.

### 5.5 Endpoints (`main.py`)
```
GET  /api/scenario/accuracy                 → {crossing: {...from get_accuracy_summary},
                                               scenario: {mape_gap, mape_price, n, per_corridor}}
POST /api/scenario/{id}/outcome  {gap_mbpd?, price_impact_high?, spr_depletion_days?,
                                   gdp_proxy_pct?, note?}  → {ok}   (analyst path)
GET  /api/scenario/calibration              → {per_corridor: {entity: {gap_x, price_x, n}}}
```

### 5.6 Frontend
- **Model Accuracy panel** (new, on the Compare tab or a 6th "Learning" tab):
  - Crossing precision + mean lead-time error (from existing summary).
  - Scenario MAPE per axis (gap / price / SPR), sample counts, and the learned
    per-corridor correction factors with their `n`.
  - "Records until next recalibration" progress bars for both loops.
- **"Log actual outcome"** button on a completed scenario (Impact tab header) →
  dialog with the four numeric fields + note → `POST /api/scenario/{id}/outcome`.
- Copy that frames it honestly: "SAGE compares its predictions against what actually
  happened and adjusts. Corrections are bounded and shown here."

### 5.7 Feature B acceptance
- Run a scenario → a prediction record is written automatically.
- Log an actual outcome (or let the auto proxy fire) → an error is recorded; accuracy
  panel updates; after ≥20 realized records the per-corridor factor moves off 1.0 and
  is visible in `/api/scenario/calibration`.
- New runs for that corridor visibly apply the factor (shown in assumptions).

---

## 6. Files Touched

**Feature A**
- `knowledge/api/write.py` — `_cache_output` stamps `created_at`/`origin`; new
  `write_scenario_index` + `sage:scenario:index` + `sage:scenario:meta:{id}`.
- `knowledge/api/read.py` — `list_scenarios(limit, origin)`, `get_custom_presets()`.
- `scenario_agent/runner.py` — thread `origin`/`label` kwargs to the cache.
- `orchestration/monitor.py` — `on_action` passes `origin="auto"`.
- `visualizer_agent/api_gateway/main.py` — library/promote endpoints; merge presets.
- Frontend: `components/sim/ScenarioLibrary.tsx` (new), `ScenarioBuilder.tsx`
  (embed it), `api/client.ts` + `api/types.ts`.

**Feature B**
- `knowledge/feedback.py` — outcome ledger fns + `get_scenario_accuracy`.
- `orchestration/scenario_params.py` — `calibrate_from_outcomes` + apply factors.
- `orchestration/monitor.py` — realized-outcome background sweep + job drain.
- `visualizer_agent/api_gateway/main.py` — accuracy/outcome/calibration endpoints;
  auto-write prediction record after each run.
- Frontend: `components/sim/LearningTab.tsx` (or Compare-tab panel), outcome dialog,
  `api/client.ts` + `api/types.ts`.

**Docker note:** these live in `knowledge/` and `orchestration/`. `knowledge/` is
bind-mounted (restart picks it up). **`orchestration/` is baked into the gateway
image** (per the Dockerfile) — changes there need `docker compose build api-gateway`,
not just restart. `main.py` is bind-mounted (restart only).

---

## 7. Guardrails / Non-negotiables

- **G1 — No fabricated data.** Library cards, accuracy numbers, and realized outcomes
  each map to a real stored record. Missing → "—" or "not yet observed", never a
  placeholder. (Matches the STRICT client contract.)
- **G2 — Realized ≠ predicted provenance is explicit.** Every realized outcome carries
  `source ∈ {eia, ais, analyst}` and is labelled in the UI. Auto proxies are marked
  "estimated from EIA/AIS", analyst entries "manually logged".
- **G3 — No over-claiming impact.** GDP stays "proxy"; refinery run-rate % only shown
  when a real nameplate exists. (§2.)
- **G4 — Interpretable learning only.** Calibration is a bounded, per-corridor, visible
  scalar. No hidden weights mutate the physics; the correction and its sample size are
  always inspectable via `/api/scenario/calibration`.
- **G5 — Learning never blocks a run.** Prediction/outcome logging and calibration are
  best-effort and off the request path (same discipline as `_cache_output`).
- **G6 — Bounded persistence.** Index/meta carry a 30d TTL; custom presets are
  untimed; full payloads keep their 24h TTL. No unbounded Redis growth.

---

## 8. Phasing (each phase independently shippable & demoable)

1. **A1 — Index + library read.** Stamp `created_at`/`origin`, write index+meta,
   `GET /api/scenario/library`, builder "Scenario Library" section (My runs + Auto).
   *Demo:* auto-triggered scenarios appear in the lab with zero user action.
2. **A2 — Promote/delete presets.** `promote`/`DELETE` endpoints, merged
   `/presets`, promote dialog + custom badge.
   *Demo:* turn a real run into a reusable named preset.
3. **B1 — Prediction ledger + accuracy read.** Auto-write prediction on each run,
   `record_scenario_prediction`, `get_scenario_accuracy`, `/api/scenario/accuracy`,
   Learning panel (read-only).
   *Demo:* the lab shows its own scenario-accuracy history.
4. **B2 — Manual outcome logging + calibration.** Outcome endpoint + dialog,
   `calibrate_from_outcomes`, apply per-corridor factor, `/calibration` surface,
   close the System-1 retrain TODO via the job list.
   *Demo:* log an outcome, watch the correction factor move, see it applied to the
   next Hormuz run.
5. **B3 (stretch) — Automatic realized capture.** Monitor sweep that pulls EIA/AIS
   realized deltas for elapsed scenarios.
   *Demo:* the loop closes with no analyst in the loop.

Ship A1→A2 first (pure plumbing, high visible payoff, directly answers "add
scenarios to my lab"). B1→B2 delivers the "evolve and learn" claim with an
honest, interpretable mechanism. B3 is the fully-autonomous flourish.

---

## 9. Direct Answers (for the user, restated)

- **"Simulate specific events + cascading impacts on refinery run rates, fuel
  prices, power/sector stress, GDP?"** — Yes, already; all four axes are computed per
  run and shown in the rebuilt lab. Caveat: GDP is an honest *proxy* and refinery
  impact is a feedstock gap (convertible to run-rate % only where a real nameplate
  exists). No new modelling needed — §2 just labels them truthfully.
- **"Continuously evolve/learn from new critical scenarios and add them to the
  lab?"** — The pieces exist (auto-trigger + feedback loop) but are disconnected.
  Feature A makes every auto-detected and user scenario a first-class, promotable
  library entry (that *is* "adding scenarios to the lab", automatically). Feature B
  adds the missing scenario-level outcome ledger and a bounded, interpretable
  calibration of System 2's parameters — so the predictions and the auto-generated
  scenarios measurably improve over time, with every correction visible and
  provenance-tagged.
