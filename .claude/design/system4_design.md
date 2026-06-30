# SAGE — System 4: Strategic Reserve Optimisation Agent (Build Spec)

> Build-ready spec grounded in the verified KB. System 4 answers: **"Given the supply gap and its
> duration, what is the optimal day-by-day SPR drawdown schedule that bridges the gap without
> breaching the emergency buffer?"**

## 1. Role

Triggered in parallel with System 3 by the same `ScenarioOutput`. System 4 computes the optimal
strategic-petroleum-reserve drawdown: when to draw, how much, when to hold/refill — maximising
expected utility subject to a chance constraint on the emergency buffer. Writes `SPRScheduleData`.

System 4 owns the SPR *policy* (drawdown) — System 2 only reports SPR *depletion* as a metric, and
the ARIO `spr_policy` knob is the scenario assumption; System 4 computes the actual optimal schedule.

## 2. KB interface — VERIFIED working

**Reads** (`knowledge/api/read.py`):
- `get_spr_state()` → 3 caverns: `capacity_mmt`, `current_fill_mmt`, `location`
  (Vizag 1.33 / Mangaluru 1.50 / Padur 2.50; ~40% filled). Verified exact (5.33 MMT total).
- **From System 2:** `ScenarioOutputData` — `gap_mbpd`, `gap_duration_days`, `confidence`,
  `feedstock_gap_timeline`. This scopes the drawdown problem.

**Writes:** `write_spr_schedule(SPRScheduleData)` → SPRSchedule episode.

## 3. The model (files to fill — currently stubs)

### 3.1 Stochastic dynamic program — `reserve_optim_agent/sdp.py`
**`solve(SDPParams) → SDPResult`** (day-by-day plan + P(buffer maintained))
- **State:** (reserve_level, market_regime, price, day_in_crisis) — low-dimensional → exact Bellman
  iteration is tractable (no GNN-MCTS needed; that's reserved for the networked multi-site variant).
- **CMDP:** maximise expected utility subject to `P(reserve < 3 days cover) ≤ 0.05`. Lagrangian
  relaxation of the chance constraint — auditable, validated in SPR economics literature.
- **Backward induction:** V[T] terminal, V[t] = max_action {reward + E[V[t+1]]}, penalise the buffer
  violation. Forward pass extracts the daily policy.
- India facts (bundle / SDPParams): total 5.33 MMT, ~9.5 days cover at full; daily consumption
  5.15 mbpd; 3-day emergency floor.

### 3.2 Real-options valuation — `reserve_optim_agent/options.py`
- Values the **option of waiting** before a major drawdown: if there's a chance the crisis resolves
  (System 2's `escalation_profile=resolving` / sandbox counterfactuals), holding has positive option
  value. Defers irreversible drawdown when uncertainty is high.

### 3.3 Runner — `reserve_optim_agent/runner.py`
```
run(scenario_id, gap_mbpd, gap_duration_days, status):
  caverns = get_spr_state()                       # live fill levels
  total_fill = sum(c.current_fill_mmt)
  params  = SDPParams(spr_initial_mmt=total_fill, gap_mbpd, gap_duration_days, price, ...)
  result  = sdp.solve(params)                     # optimal drawdown
  memo    = Nova Pro policy rationale             # why this rate/window
  write_spr_schedule(SPRScheduleData(scenario_id, daily_plan, prob_above_buffer, policy_memo))
```

## 4. Output contract — `SPRScheduleData` (contracts/outputs.py)
`daily_plan`: list of `SPRDay(day, action[draw|hold|refill], volume_mmt, reserve_after_mmt,
days_cover_after, decision_driver)`; `prob_above_buffer`; `constraint_satisfied`;
`lagrange_multiplier`; `option_value_of_waiting`; `policy_memo`.

## 5. Data sufficiency
✅ SPR cavern state verified exact in the KB. ✅ Gap + duration from System 2. ✅ Consumption/floor
constants in the bundle params. **System 4 can be built against the live KB now** — its only real
input beyond SPR state is System 2's gap, which is wired.

⚠️ Per-site SPR `current_fill_mmt` is an estimate (national 40% distributed) — flagged in `data/data.md`;
the SDP works on the total, so this doesn't block.

## 6. Build order
1. `sdp.py` Bellman iteration on the 4-D state grid (testable standalone with synthetic gap).
2. CMDP Lagrangian buffer constraint. 3. `options.py` value-of-waiting. 4. `runner.py` wiring +
Nova Pro memo. 5. (post-hackathon) GNN-MCTS for the networked multi-site variant.

## 7. Relationship to System 2's `spr_policy`
System 2's `spr_policy` (aggressive/moderate/none) is a *scenario assumption* for the cascade.
System 4 computes the *optimal* policy. In the full loop, System 4's output could feed back as the
realistic `spr_policy` for a refined System 2 re-run — but for the demo they run once, in parallel.
