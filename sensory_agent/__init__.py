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
from sensory_agent import ais, news, prices, sanctions  # noqa: F401
from sensory_agent.runner import run_all  # noqa: F401
