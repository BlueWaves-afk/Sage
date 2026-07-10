"""
AIS sub-agent — aisstream.io WebSocket.

Persistent asyncio WebSocket connection to aisstream.io.
Converts lat/lon → H3 cell IDs (resolution 5), detects dark vessels
(AIS gap >4h in monitored H3 cells), clusters anomalies, and emits
ONE signal per anomaly cluster (never per ping).

Payload contract (fusion reads these exact keys):
    gap_hours     — float, duration of AIS gap
    dark_vessel   — bool, True if gap >4h in monitored cell
    anomaly_score — float 0–1, higher = more anomalous
    h3_cell       — str, H3 cell ID where anomaly detected
    velocity_std  — float, std dev of vessel speed (optional)
    dark_count    — int, number of dark vessels in cluster
    mmsi          — str, vessel MMSI identifier
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

from contracts.signal import NormalizedSignal
from knowledge.registry import resolve_h3, canonical_name, H3_TO_ENTITY
from sensory_agent._base import emit, new_signal_id, utcnow

log = logging.getLogger(__name__)

AISSTREAM_API_KEY = os.environ.get("AISSTREAM_API_KEY", "")  # set in .env.local (gitignored)
AISSTREAM_WS_URL = "wss://stream.aisstream.io/v0/stream"

# Gap threshold for dark vessel detection (hours)
DARK_VESSEL_GAP_H = 4.0

# Cluster emission interval: emit at most once per H3 cell per N seconds
CLUSTER_EMIT_INTERVAL_S = int(os.environ.get("AIS_CLUSTER_INTERVAL_S", "300"))  # 5 min

# H3 resolution for position indexing
H3_RESOLUTION = 5

# ── Vessel tracking state ────────────────────────────────────────────────────


@dataclass
class VesselState:
    """Per-vessel tracking state for gap and anomaly detection."""
    mmsi: str
    last_seen: float = 0.0          # monotonic timestamp
    last_lat: float = 0.0
    last_lon: float = 0.0
    last_speed: float = 0.0
    speeds: list[float] = field(default_factory=list)
    gap_hours: float = 0.0
    in_monitored_cell: bool = False
    h3_cell: str = ""


# Per-vessel state
_vessels: dict[str, VesselState] = {}

# Per H3 cell: last cluster emission time
_last_cluster_emit: dict[str, float] = defaultdict(float)

# Per H3 cell: accumulated anomaly events since last emission
_cell_anomalies: dict[str, list[dict]] = defaultdict(list)


# ── H3 conversion ───────────────────────────────────────────────────────────

def _lat_lon_to_h3(lat: float, lon: float) -> str:
    """Convert lat/lon to H3 cell ID at resolution 5."""
    try:
        import h3
        return h3.latlng_to_cell(lat, lon, H3_RESOLUTION)
    except ImportError:
        # Fallback: simple grid quantization if h3 not installed
        lat_q = round(lat * 10) / 10
        lon_q = round(lon * 10) / 10
        return f"fallback_{lat_q}_{lon_q}"
    except Exception:
        return ""


def _compute_anomaly_score(
    gap_hours: float,
    speed_std: float,
    in_monitored: bool,
) -> float:
    """
    Compute anomaly score (0–1) from gap duration, speed variability,
    and whether the vessel is in a monitored corridor.

    Weighting:
        0.45 × gap_hours / 24h (clamped)
        0.30 × speed_std / 5   (clamped)
        0.25 × monitored_bonus
    """
    gap_norm = min(gap_hours / 24.0, 1.0) if gap_hours > 0 else 0.0
    speed_norm = min(speed_std / 5.0, 1.0) if speed_std > 0 else 0.0
    monitored_bonus = 1.0 if in_monitored else 0.0

    score = 0.45 * gap_norm + 0.30 * speed_norm + 0.25 * monitored_bonus
    return round(min(1.0, score), 4)


# ── Bounding boxes for monitored regions ─────────────────────────────────────

# We subscribe to bounding boxes covering the monitored corridors
# These cover: Hormuz, Bab-el-Mandeb, Suez, Malacca, and Indian ports
MONITORED_BBOXES = [
    # Strait of Hormuz region
    [[24.0, 54.0], [28.0, 58.0]],
    # Bab-el-Mandeb / Red Sea
    [[11.0, 42.0], [14.0, 45.0]],
    # Suez Canal approach
    [[29.0, 31.0], [32.0, 34.0]],
    # Strait of Malacca
    [[1.0, 100.0], [4.0, 104.0]],
    # Indian west coast (ports: Vadinar, Sikka, Mundra, Kochi)
    [[8.0, 68.0], [24.0, 78.0]],
    # Indian east coast (Paradip, Chennai, Vizag)
    [[13.0, 78.0], [21.0, 87.0]],
    # Arabian Gulf (supplier routes)
    [[22.0, 46.0], [30.0, 56.0]],
    # East Africa coast (Cape route)
    [[-35.0, 20.0], [0.0, 45.0]],
]


def _build_subscription_message() -> str:
    """Build the aisstream.io WebSocket subscription message."""
    return json.dumps({
        "APIKey": AISSTREAM_API_KEY,
        "BoundingBoxes": MONITORED_BBOXES,
        "FilterMessageTypes": ["PositionReport"],
    })


# ── Message processing ──────────────────────────────────────────────────────

async def _process_position(msg: dict) -> None:
    """
    Process a single AIS position report.
    Updates vessel state, detects gaps, accumulates anomalies per cell.
    Does NOT emit signals directly — anomalies are clustered and emitted
    periodically by _emit_clusters().
    """
    try:
        meta = msg.get("MetaData", {})
        position = msg.get("Message", {}).get("PositionReport", {})

        mmsi = str(meta.get("MMSI", ""))
        if not mmsi:
            return

        lat = float(position.get("Latitude", meta.get("latitude", 0)))
        lon = float(position.get("Longitude", meta.get("longitude", 0)))
        speed = float(position.get("Sog", 0))  # Speed Over Ground
        timestamp_str = meta.get("time_utc", "")

        if lat == 0 and lon == 0:
            return  # invalid position

        # Convert to H3
        h3_cell = _lat_lon_to_h3(lat, lon)
        if not h3_cell:
            return

        # Check if in monitored cell
        entity_id = resolve_h3(h3_cell)
        in_monitored = entity_id is not None

        now = time.monotonic()

        # Get or create vessel state
        vs = _vessels.get(mmsi)
        if vs is None:
            vs = VesselState(mmsi=mmsi)
            _vessels[mmsi] = vs

        # Compute gap
        gap_hours = 0.0
        if vs.last_seen > 0:
            gap_seconds = now - vs.last_seen
            gap_hours = gap_seconds / 3600.0

        # Update vessel state
        vs.last_seen = now
        vs.last_lat = lat
        vs.last_lon = lon
        vs.last_speed = speed
        vs.speeds.append(speed)
        if len(vs.speeds) > 50:
            vs.speeds = vs.speeds[-50:]
        vs.gap_hours = gap_hours
        vs.in_monitored_cell = in_monitored
        vs.h3_cell = h3_cell

        # Dark vessel detection: gap >4h in a monitored cell
        is_dark = gap_hours >= DARK_VESSEL_GAP_H and in_monitored

        if is_dark or (in_monitored and gap_hours >= 2.0):
            # Speed std
            speed_std = 0.0
            if len(vs.speeds) >= 3:
                mean_speed = sum(vs.speeds) / len(vs.speeds)
                variance = sum((s - mean_speed) ** 2 for s in vs.speeds) / len(vs.speeds)
                speed_std = math.sqrt(variance)

            anomaly_score = _compute_anomaly_score(gap_hours, speed_std, in_monitored)

            # Accumulate anomaly for this cell
            _cell_anomalies[h3_cell].append({
                "mmsi": mmsi,
                "gap_hours": gap_hours,
                "dark_vessel": is_dark,
                "anomaly_score": anomaly_score,
                "speed_std": speed_std,
                "lat": lat,
                "lon": lon,
                "entity_id": entity_id,
            })

    except Exception as exc:
        log.debug("Position processing error: %s", exc)


async def _emit_clusters() -> None:
    """
    Periodically check accumulated anomalies per H3 cell and emit
    clustered signals. One signal per cell per interval.
    """
    now = time.monotonic()

    for h3_cell, anomalies in list(_cell_anomalies.items()):
        if not anomalies:
            continue

        # Rate limit: at most one signal per cell per CLUSTER_EMIT_INTERVAL_S
        last_emit = _last_cluster_emit.get(h3_cell, 0)
        if now - last_emit < CLUSTER_EMIT_INTERVAL_S:
            continue

        # Resolve entity
        entity_id = resolve_h3(h3_cell)
        if not entity_id:
            _cell_anomalies[h3_cell] = []
            continue

        # Aggregate cluster stats
        dark_count = sum(1 for a in anomalies if a["dark_vessel"])
        max_gap = max(a["gap_hours"] for a in anomalies)
        max_anomaly = max(a["anomaly_score"] for a in anomalies)
        mean_lat = sum(a["lat"] for a in anomalies) / len(anomalies)
        mean_lon = sum(a["lon"] for a in anomalies) / len(anomalies)

        # Best MMSI (longest gap)
        best = max(anomalies, key=lambda a: a["gap_hours"])
        mmsi = best["mmsi"]

        # Average speed std
        speed_stds = [a["speed_std"] for a in anomalies if a["speed_std"] > 0]
        avg_speed_std = sum(speed_stds) / len(speed_stds) if speed_stds else 0.0

        entity_name = canonical_name(entity_id)

        signal = NormalizedSignal(
            signal_id=new_signal_id("ais"),
            source="ais",
            observed_at=utcnow(),
            ingested_at=utcnow(),
            priority_hint="HIGH",
            force_synthesis=False,   # AIS NEVER force-synthesizes
            entity_refs=[entity_name],
            h3_cells=[h3_cell],
            lat=mean_lat,
            lon=mean_lon,
            summary=(
                f"AIS dark-vessel cluster: {dark_count} dark vessels "
                f"near {entity_name}, "
                f"max gap {max_gap:.0f}h, anomaly={max_anomaly:.2f}"
            ),
            payload={
                "mmsi": mmsi,
                "gap_hours": round(max_gap, 2),
                "dark_vessel": dark_count > 0,
                "anomaly_score": max_anomaly,
                "h3_cell": h3_cell,
                "velocity_std": round(avg_speed_std, 4),
                "dark_count": dark_count,
            },
        )

        await emit(signal)
        log.info("AIS cluster signal: %s", signal.summary)

        # Clear and update timestamps
        _cell_anomalies[h3_cell] = []
        _last_cluster_emit[h3_cell] = now


async def _cluster_emitter() -> None:
    """Background task: emit accumulated clusters every CLUSTER_EMIT_INTERVAL_S."""
    while True:
        try:
            await _emit_clusters()
        except Exception as exc:
            log.error("Cluster emitter error: %s", exc)
        await asyncio.sleep(CLUSTER_EMIT_INTERVAL_S)


async def run() -> None:
    """
    Entry point. Connects to aisstream.io via WebSocket and processes
    vessel position messages indefinitely. Emits signals per anomaly
    cluster, never per individual ping.
    """
    import websockets

    log.info(
        "AIS sub-agent started. Key=%s..., bboxes=%d, gap_threshold=%dh",
        AISSTREAM_API_KEY[:10] if AISSTREAM_API_KEY else "MISSING",
        len(MONITORED_BBOXES),
        DARK_VESSEL_GAP_H,
    )

    # Start cluster emitter background task
    emitter_task = asyncio.create_task(_cluster_emitter())

    reconnect_delay = 1  # exponential backoff

    while True:
        try:
            log.info("Connecting to aisstream.io WebSocket...")

            async with websockets.connect(
                AISSTREAM_WS_URL,
                ping_interval=20,
                ping_timeout=60,
                max_size=10 * 1024 * 1024,   # 10 MB max message
            ) as ws:
                # Subscribe
                sub_msg = _build_subscription_message()
                await ws.send(sub_msg)
                log.info("AIS WebSocket connected and subscribed")
                reconnect_delay = 1  # reset backoff

                msg_count = 0
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                        msg_type = msg.get("MessageType", "")

                        if msg_type == "PositionReport":
                            await _process_position(msg)
                            msg_count += 1

                            if msg_count % 1000 == 0:
                                log.info(
                                    "AIS: processed %d messages, tracking %d vessels, "
                                    "%d cells with anomalies",
                                    msg_count,
                                    len(_vessels),
                                    sum(1 for v in _cell_anomalies.values() if v),
                                )

                    except json.JSONDecodeError:
                        continue
                    except Exception as exc:
                        log.debug("AIS message processing error: %s", exc)

        except asyncio.CancelledError:
            log.info("AIS sub-agent cancelled")
            emitter_task.cancel()
            raise

        except Exception as exc:
            log.error(
                "AIS WebSocket error: %s — reconnecting in %ds",
                exc, reconnect_delay,
            )
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, 120)  # max 2min backoff

        # Prune stale vessel state (>24h without update)
        stale_threshold = time.monotonic() - 86400
        stale_keys = [k for k, v in _vessels.items() if v.last_seen < stale_threshold]
        for k in stale_keys:
            del _vessels[k]
