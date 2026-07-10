# SAGE Build TODO — Post-Bundle-Parameterisation

Status as of 2026-07-02 (this pass). **UPDATE 2026-07-09:** System 1 (all four sensory
agents), the React frontend, and the voice interface are now **built and verified live** —
they were "out of scope"/"deferred" only for the pass this file documents. See
`docs/DEPLOY_EC2.md` for current deployment status.

This list reflects a **direct code audit**, correcting an earlier automated audit that was wrong on
several points:
- ✅ GNN checkpoint **already exists** (`scenario_agent/gnn/weights/cascade_surrogate.joblib`, 77 MB,
  trained). `predict_cascade()` already does load + ARIO fallback. Only the *callers* are unwired.
- ✅ Nova Pro rationale (System 3) and policy memo (System 4) **are implemented** — not stubs.
- ✅ Monitor, triggers, all KB read/write APIs, all three agent cores are complete.

The genuine remaining gaps, in build order:

---

## Phase 1 — Wire the surrogate + sandbox pre-staging  (quick, high-impact)

- [x] **1.1** `scenario_agent/runner.py:_run_gnn` — clarified: ARIO is the correct fast path for the
      fixed topology (surrogate is slower/less accurate per model.py); now passes refineries+sectors so
      speculative output carries full node attribution. predict_cascade seam documented for future ABM.
- [x] **1.2** `orchestration/sandbox.py:_run_gnn_surrogate` — builds `ARIOParams` from subgraph + SPR +
      forecast-projected severity, calls `predict_cascade()`, returns real cascade scalars (not zeros).
- [x] **1.3** `orchestration/sandbox.py:_prestage_systems` — calls procurement + reserve runners with
      `status="speculative"` in parallel, gap derived from `sandbox_state`, best-effort error handling.

## Phase 2 — Make the sandbox actually fork (forecast + crossing + counterfactuals)

- [x] **2.1** Added `get_risk_history(entity, hours)` + `RiskHistoryPoint` to `knowledge/api/read.py` —
      reads the bitemporal RISK_STATE series, time-windowed, oldest→newest.
- [x] **2.2** `_forecast_trajectories` — real drift + mean-reversion projection from risk history with
      volatility-scaled quantile bands; seeds from current fused factors when history is thin.
- [x] **2.3** `_counterfactual_fork` — 3 real perturbations, re-runs crossing estimate, reports delta.
- [x] **BONUS** Fixed a latent bug: the old crossing approximation (`0.35·ais + 0.25·price`) maxed at
      0.60 and could NEVER cross the 0.70 action threshold — the sandbox would never fork. Rewrote it to
      use the faithful fusion weights, holding gdelt+sanctions at current contribution. Verified: a real
      multi-factor escalation now forks at P≈0.93; pure AIS+price correctly stays capped at 0.60.

## Phase 3 — Autonomous loop

- [x] **3.1** `orchestration/graph.py:build_graph` — 7 shared node coroutines + routing predicates;
      real LangGraph `StateGraph` when installed, tested `_FallbackPipeline` (same `ainvoke` contract)
      otherwise. Parallel sandbox branch for HIGH signals, conditional scenario→procure→reserve on
      action-band crossing. `run_pipeline(signal)` convenience entry point. Verified end-to-end.

## Phase 4 — Tests

- [x] **4.1** `tests/test_scenario_agent.py` — ARIO cascade, Monte Carlo bands, IO, ABM invariants.
- [x] **4.2** `tests/test_procurement_agent.py` — grade compat, routing, TOPSIS ordering.
- [x] **4.3** `tests/test_reserve_agent.py` — SDP monotonicity, CMDP constraint, real-options sign.
- [x] **4.4** `tests/test_sandbox.py` — forecast shape, crossing probability, counterfactuals.
- [x] **4.5** `tests/test_bundle_params.py` — every agent reads bundle params, upgrade diff logic.
- **37 new tests, all passing; existing 31 smoke tests still green (no regressions).**

## Phase 5 — API gateway

- [x] **5.1** Added a Redis structured-output cache (`_cache_output` in write.py) written by
      write_scenario/procurement/spr_schedule, and `get_output(kind, id)` in read.py. Wired
      `/api/scenario`, `/api/procurement`, `/api/spr-schedule` (latest or by id) to return full-fidelity
      JSON. (WebSocket `/ws` pub/sub from `sage:events` was already functional; core read endpoints
      already existed — audit was wrong on those.)

## Deferred (not this pass)

- [x] React frontend (`visualizer_agent/frontend/`) — ✅ built (deck.gl map, copilot, radar, wiki drawer, voice).
- [ ] Chronos-2 real model — optional drop-in behind `_forecast_trajectories` (drift+mean-reversion in use).
- [ ] Random-Forest grade upgrade, 140-sector IO, GNN-MCTS multi-site SPR — post-hackathon.
