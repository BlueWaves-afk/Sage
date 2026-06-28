"""
System 4 — Strategic Reserve Optimisation Agent. Owner: Teammate C.

Triggered in parallel with alt_procurement_agent by the same ScenarioOutput node.
Also runs pre-emptively against Anticipatory Sandbox state.

Reads from knowledge:
  get_spr_state()  — Vizag (1.33 MMT), Mangaluru (1.5 MMT), Padur (2.5 MMT) = 5.33 MMT total

Core models:
  sdp.py     — Stochastic Dynamic Programming (Bellman iteration) + CMDP Lagrangian relaxation
  options.py — Real-options valuation (value of waiting before major drawdown)
  runner.py  — entry point
"""
