# SAGE — System 2: Disruption Scenario Modeller (Build Spec)

> Build-ready spec grounded in the **verified** KB state (edge weights reconciled,
> `get_subgraph`/`get_spr_state`/`write_scenario`/`write_pending` all confirmed working).
> Companion: `.claude/design/system2_designspec.md` (architecture narrative).

## 1. What System 2 does

Answers: **"If a corridor is blocked right now, what is the day-by-day impact on India's crude
supply, refinery feedstocks, SPR cover, and import price?"**

It runs the **ARIO** (Adaptive Regional Input-Output, Hallegatte 2008) cascade over the supply-chain
subgraph and writes a `ScenarioOutputData` to the KB. System 3 (procurement) and System 4 (SPR)
consume that output. System 2 does **not** compute risk scores (System 1) or rank routes (System 3).

## 2. Three execution paths

| Path | Trigger | Engine | Latency |
|---|---|---|---|
| **Cold / confirmed** | risk band ≥ `action` (≥0.70), no pre-staged scenario | full ARIO (NumPy) | ~ seconds |
| **Sandbox / anticipatory** | HIGH signal, P(cross 24h) > 0.5 | GNN surrogate on speculative state | < 150 ms |
| **Promotion** | crossing confirmed, sandbox already ran | reload PendingScenario, refresh params | ~ 50 ms |

The GNN surrogate is trained to imitate ARIO (so the sandbox is fast); ARIO is ground truth.

## 3. KB interface — VERIFIED working

**Reads** (`knowledge/api/read.py`):
- `get_subgraph(entity, hops=2)` → `SubgraphView(nodes, edges)`; nodes carry `throughput_mbpd`,
  `capacity_mbpd`, `inventory_days`, `choke_severity`; edges carry `throughput_share_pct`,
  `volume_mbpd` (now **exact** after edge reconciliation). `relation_type` is the edge name.
- `get_spr_state()` → `[SPRCavernView(capacity_mmt, current_fill_mmt, location)]`.
- `get_risk_scores()` → current `RISK_STATE` (for `disruption_fraction` calibration).

**Writes** (`knowledge/api/write.py`):
- `write_scenario(ScenarioOutputData)` → ScenarioOutput episode + `AFFECTS_SCENARIO` edge.
- `write_pending(...)` → PendingScenario (sandbox path, `orchestration/sandbox.py`).

## 4. The ARIO model (what to implement in `scenario_agent/ario.py`)

Day-by-day cascade. **Every parameter labelled + sourced** (judging criterion). State iterates over
`horizon_days`.

### 4.1 Inputs (`ARIOParams`)

| Param | Default | Source |
|---|---|---|
| `daily_consumption_mbpd` | 5.15 | PPAC (India crude processing) |
| `import_dependence_pct` | 88.2 | PPAC 2025 |
| `hormuz_share_pct` | 42.5 | PPAC / IEA |
| `spr_total_mmt` | 5.33 | ISPRL |
| `spr_fill_frac` | 0.40 | ISPRL (Mar 2025) |
| `spr_max_draw_mbpd` | 0.40 | ISPRL drawdown rate est. |
| `bypass_capacity_mbpd` | 4.0 | IEA (Petroline+ADCOP available 3.5–5.5) |
| `bypass_ramp_days` | 5 | Aramco ops est. |
| `refinery_inventory_days` | 22 | PPAC national avg |
| `indirect_multiplier` | 10.6 | Inoue & Todo 2019 |
| `price_elasticity_low/high` | 8 / 22 | $/bbl per mbpd global shortfall band |
| `disruption_fraction` | 1.0 | scenario input (0=none, 1=full closure) |
| `disruption_days` | 30 | scenario input |

`MMT → mbbl`: ×7.33. `MMT/yr → mbpd`: ÷365×7.33.

### 4.2 Daily iteration (the cascade)

```
hormuz_dependent = daily_consumption_mbpd × hormuz_share_pct/100
for t in 0..horizon:
    lost(t)    = hormuz_dependent × disruption_fraction        if t < disruption_days else 0
    ramp(t)    = clamp((t - bypass_ramp_days)/bypass_ramp_days, 0, 1)   # bypass ramps in
    relief(t)  = min(bypass_capacity_mbpd, lost(t)) × ramp(t)
    net(t)     = max(0, lost(t) - relief(t))                   # unmet by bypass
    spr_draw(t)= min(spr_max_draw_mbpd, net(t), spr_remaining_mbbl)     # SPR offsets
    spr_remaining_mbbl -= spr_draw(t)
    feedstock_gap(t) = max(0, net(t) - spr_draw(t))            # refineries short this much
    price(t)   = elasticity × (hormuz_GLOBAL_mbpd × disruption_fraction / global_supply)
```

Outputs (`ARIOResult` → `ScenarioOutputData`):
- `feedstock_gap_timeline` = [feedstock_gap(t) for t in horizon]
- `gap_mbpd` = peak feedstock gap; `gap_duration_days` = days with gap > 0
- `spr_depletion_days` = first t where spr_remaining hits the 3-day-cover floor
- `price_impact_low/high` = elasticity band × global shortfall
- `gdp_proxy_impact_pct` = direct × indirect_multiplier
- `assumptions` = every param as {value, unit, source}

### 4.3 Per-refinery attribution (uses the reconciled edge weights)

The feedstock gap is allocated to refineries via the `SUPPLIES`/`FEEDS` `throughput_share_pct` chain
(Hormuz → port → refinery). e.g. 70% of Jamnagar's crude via Vadinar, 42% of Vadinar via Hormuz →
Jamnagar's Hormuz exposure ≈ 0.70 × 0.42. This is why the edge reconciliation mattered.

### 4.4 Monte Carlo (output ranges, not false-precision points)

Run N=200–500 iterations sampling `disruption_fraction`, `elasticity`, `bypass_ramp_days` from
ranges → report p10/p50/p90 bands on price and gap. Powers the "uncertainty bands" demo requirement.

## 5. `_extract_ario_params(subgraph)` — wire KB → params

Read from the subgraph (now reliable):
- corridor `throughput_mbpd`, `choke_severity` → calibrate `disruption_fraction` from current risk
- refinery `capacity_mbpd`, `inventory_days`
- `SUPPLIES`/`FEEDS` `throughput_share_pct` → per-refinery exposure
- `get_spr_state()` sum → `spr_total_mmt × fill`

## 6. Build order

1. **`ario.py::run()`** — implement §4.2 cascade (NumPy). Fully testable standalone. ← start here
2. **`runner.py::_extract_ario_params()`** — map subgraph → `ARIOParams`.
3. **`runner.py::run()`** — populate `gap_mbpd`, `gap_duration_days`, `confidence` from result.
4. **Monte Carlo** wrapper (§4.4) for bands.
5. **GNN surrogate** (`gnn/train.py`): Monte-Carlo ARIO sweep → training set; `gnn/model.py`: GAT;
   wired into `sandbox._run_gnn_surrogate`. (After 1–4; needs no external data.)
6. **Sandbox forecast** (`sandbox._forecast_trajectories`): Chronos-2 over signal history.
   (Sequenced after System 1 produces history.)

## 7. Validation targets

- Full Hormuz closure (`disruption_fraction=1.0`): feedstock gap appears after refinery inventory +
  SPR buffer (~days), price band ~ +$8–22/bbl, SPR depletes in days. Sanity-check vs the demo's
  golden-path numbers (gap ~1.8 mbpd, SPR depletion ~7 days).
- All assumptions present in `ScenarioOutputData.assumptions` with source tags.
- `write_scenario()` round-trips; System 3/4 can read the output.
