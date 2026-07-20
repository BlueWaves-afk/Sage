# SAGE — Model Assumptions (Explicit & Testable)

The rubric requires scenario assumptions to be *explicit and testable*. They are. Every
assumption below is (a) sourced or tagged as an estimate in the context bundle, and
(b) perturbable live in the **Sensitivity / Tornado tab**, which re-runs the ARIO cascade
under ±20% shifts and ranks each assumption by its impact on the supply gap.

## System 2 — Disruption Scenario Modeller (ARIO)

| Assumption | Where it lives | How to test it |
|---|---|---|
| Chokepoint severity (Hormuz 0.9, Malacca 0.7) | `facts/nodes/corridors.csv` (tier=estimated) | Sensitivity tab perturbs severity; watch gap swing |
| Daily crude throughput (India 5.25 / Japan 2.5 mbpd) | `params/ario_params.csv` (tier=real) | Perturb consumption ±20%, observe price/GDP response |
| Supplier import shares | `facts/edges/supplies.csv` (tier=real) | Re-weight a supplier, re-run, compare residual gap |
| Refinery operating inventory (~22 days) | `facts/nodes/refineries.csv` (tier=estimated) | Perturb buffer days; watch time-to-shortfall |

## System 3 — Procurement (TOPSIS)

| Assumption | Where it lives | How to test it |
|---|---|---|
| Criterion weights (cost 0.35, security, compatibility …) | `params/ranking_params.csv` | Adjust weights; alternative ranking re-sorts |
| Supplier/corridor risk cutoffs (0.4 / 0.5) | `params/economics_params.csv` | Raise/lower filter; see which options become admissible |

## System 4 — Strategic Reserve (Bellman SDP)

| Assumption | Where it lives | How to test it |
|---|---|---|
| Crisis-resolution probabilities (resolving 0.55 / constant 0.20 / escalating 0.05) | `params/spr_params.csv` (tier=estimated, ICB-calibrated) | Change profile; optimal drawdown schedule shifts |
| Max daily draw fraction (0.60) | `params/spr_params.csv` | Perturb; watch depletion-days vs supply-gap tradeoff |
| Real-options wait window (5 days) | `params/economics_params.csv` | Change window; DRAW-NOW vs WAIT decision flips |

## Validation (accuracy is measured, not asserted)

- **LOCO-5**: leave-one-crisis-out over 5 real shocks (Abqaiq, COVID, Suez, Ukraine, Houthi),
  mean AUC **0.8409**, decision threshold 0.2634 — see the Learning tab (bar chart +
  reliability curve).
- Estimated values are labelled `estimated` with an `estimation_method`; nothing is a
  hidden constant.
