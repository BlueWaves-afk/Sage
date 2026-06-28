"""
System 3 — Adaptive Procurement Orchestrator. Owner: Teammate C.

Triggered automatically by LangGraph on new ScenarioOutput node in Graphiti.
Runs against BOTH sandbox state (speculative) and live state (confirmed).

Reads from knowledge:
  get_available_suppliers()  — risk < 0.4, not sanctioned
  get_grade_specs(refinery)  — CONFIGURED_FOR edges + crude specs
  get_routes(risk_max=0.5)   — open corridors

Core models:
  routing.py  — OR-Tools MILP + RRNCO heuristic (asymmetric cost matrix)
  grade.py    — RF + Peng-Robinson EOS crude compatibility (API gravity + sulfur)
  rank.py     — TOPSIS multi-objective ranking (cost, lead time, compatibility, risk)
  runner.py   — entry point
"""
