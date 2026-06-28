"""
System 2 — Scenario Agent (Disruption Scenario Modeller). Owner: Tom.

Triggered two ways (both automatic):
  Path A — Anticipatory: P(risk_score > 0.7 within 24h) > 0.5 (via sandbox)
  Path B — Confirmed: live risk_score crosses 0.7 in Graphiti (via monitor)

Reads supply-chain subgraph from knowledge.api.read.get_subgraph().
Writes cascade results via knowledge.api.write.write_scenario().
Never imports graphiti_core directly.

Core models:
  ario.py    — ARIO dynamic IO cascade (Hallegatte 2008) — economic propagation
  gnn/       — PyTorch GNN surrogate trained on ARIO outputs, <150ms on T4 GPU
  runner.py  — entry point, orchestrates read → model → write
"""
