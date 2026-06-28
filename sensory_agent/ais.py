"""
AIS sub-agent.

Persistent asyncio websocket to aisstream.io.
Converts lat/lon → H3 cell IDs, runs HABIT imputation on gaps,
detects dark vessels (AIS gap >4h in monitored H3 cells = HIGH priority).
SAR enhancement: Sentinel-1 lookup hourly on H3 cells with AIS gaps.
"""
from __future__ import annotations

import asyncio

from contracts.signal import AisPayload, NormalizedSignal


async def run() -> None:
    """Entry point. Connects to aisstream.io and processes messages indefinitely."""
    # TODO: open websocket to wss://stream.aisstream.io/v0/stream with AISSTREAM_API_KEY
    # TODO: subscribe to H3 cells for monitored corridors (loaded from knowledge at startup)
    # TODO: for each message → _process_position()
    raise NotImplementedError


async def _process_position(msg: dict) -> NormalizedSignal:
    """Convert raw AIS message to NormalizedSignal. Stub."""
    # TODO: extract MMSI, lat, lon, timestamp
    # TODO: convert lat/lon → H3 cell (res 5)
    # TODO: run HABIT imputation if gap detected
    # TODO: compute anomaly_score
    # TODO: check dark_vessel (gap >4h in monitored cell → force_synthesis=True)
    # TODO: push NormalizedSignal to Redis queue
    raise NotImplementedError


async def _sar_lookup(h3_cells: list[str]) -> bool:
    """Query Sentinel-1 SAR for vessel presence in H3 cells with AIS gaps. Stub."""
    # TODO: query ESA Copernicus Hub API for latest SAR pass over h3_cells
    return False
