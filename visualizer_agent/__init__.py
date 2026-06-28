"""
System 5 — Visualizer Agent (Supply Chain Digital Twin + UI). Owner: Teammate D.

Pure consumer — reads everything, writes nothing to the knowledge base.
Real-time rendering surface for SAGE's live state.

api_gateway/   — FastAPI + WebSocket server (Python)
frontend/      — React + deck.gl digital twin map (TypeScript)

Key features:
  - Geospatial knowledge graph: nodes at real coordinates, risk colour-coded
  - H3 hexagonal heatmap from AIS anomaly density
  - Staged Alert: PendingScenario confidence % + projected crossing time
  - Pipeline bar: SENSE → TRIAGE → SAGE → SANDBOX → SCENARIO → PROCURE → RESERVE
  - Copilot: EA-GraphRAG routed, <2s response, all answers cited
  - Wiki page on node click: retrieved from knowledge.api.read.get_wiki_page()
"""
