"""
System 1 — Sensory Agent. Owner: Teammate B.

Four always-on sub-agents. The ONLY system that writes raw signals.
Every sub-agent emits NormalizedSignal → Redis queue → SAGE ingest_signal().
No sub-agent writes to Graphiti directly.

Sub-agents:
  ais.py        — AIS websocket (aisstream.io), H3, dark-vessel detection
  news.py       — newsdata.io + GDELT, HuggingFace sentiment analysis
  sanctions.py  — OFAC/EU/UN XML diff, vessel registration
  prices.py     — yfinance + EIA API, BOCD changepoint detection

Shared scaffolding:
  _base.py      — emit(), new_signal_id(), utcnow()
  sentiment.py  — HuggingFace multilingual-sentiment-analysis wrapper
  fusion.py     — GBM/weighted-sum risk score fusion model

Runner:
  runner.py     — Launch all sub-agents: ``python -m sensory_agent.runner``
"""
# NOTE: do NOT eager-import the sub-agents here. Each runs in its own container
# with only its own deps (e.g. the news/sanctions/ais images don't ship yfinance).
# Eager-importing prices → yfinance would crash those containers. Import sub-agents
# lazily where needed (runner.py does this inside its functions).
