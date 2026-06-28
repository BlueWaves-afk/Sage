"""
LangGraph autonomous orchestration layer.

Owns: state machine definition, threshold monitor, anticipatory sandbox manager,
and event triggers that activate scenario_agent / alt_procurement_agent / reserve_optim_agent.

Team boundary:
  sandbox.py, monitor.py  →  Tom (same owner as knowledge/)
  graph.py wiring         →  Teammate D
"""
