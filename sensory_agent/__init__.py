"""
System 1 — Sensory Agent. Owner: Teammate B.

Four always-on sub-agents. The ONLY system that writes raw signals.
Every sub-agent emits NormalizedSignal → Redis queue → SAGE ingest_signal().
No sub-agent writes to Graphiti directly.

Sub-agents:
  ais.py        — AIS websocket, H3, HABIT imputation, dark-vessel detection, SAR fusion
  news.py       — GDELT + NewsAPI, Nova Micro entity extraction
  sanctions.py  — OFAC/EU/UN diff, vessel ownership graph analytics
  prices.py     — EIA + yfinance, BOCD changepoint detection, regime-switching HMM
"""
