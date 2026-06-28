"""
LangGraph state machine definition. Teammate D owns the graph wiring.
Tom owns the individual node implementations (sandbox.py, monitor.py).

Pipeline stages (maps to the UI pipeline bar):
  SENSE → TRIAGE → SAGE → SANDBOX → SCENARIO → PROCURE → RESERVE
"""
from __future__ import annotations

# TODO (Teammate D): wire LangGraph StateGraph with nodes:
#   sense_node      → reads from Redis signal queue
#   triage_node     → calls knowledge.triage.triage()
#   sage_node       → calls knowledge.api.write.ingest_signal()
#   sandbox_node    → calls orchestration.sandbox.maybe_fork() [parallel branch]
#   scenario_node   → triggers scenario_agent
#   procure_node    → triggers alt_procurement_agent
#   reserve_node    → triggers reserve_optim_agent
#
# Edges:
#   triage_node → sage_node (always)
#   triage_node → sandbox_node (parallel, HIGH priority only)
#   sage_node   → monitor check → scenario_node (on ACTION_THRESHOLD crossing)
#   scenario_node → procure_node → reserve_node (sequential)

def build_graph():
    """Returns a compiled LangGraph. Stub."""
    raise NotImplementedError
