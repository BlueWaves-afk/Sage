"""
Demo sandbox control.

`scripts/demo_ignite.py` runs a labeled historical crisis (2026 Hormuz closure)
through the REAL ingest path so judges can watch the autonomous pipeline fire.
To keep the live system uncorrupted, the demo operates as a SANDBOX:

  1. The demo snapshots the whole graph (GRAPH.COPY) before it starts.
  2. It raises the `sage:demo:active` flag. While the flag is up, sage-core:
       - clears its in-process risk caches (so risk climbs from a clean baseline),
       - DROPS live (non-replay) signals so real data can't interleave,
       - polls/flushes faster so the ~3-min replay shows a visible climb.
  3. After the replay, the demo restores the pre-demo graph snapshot and lowers
     the flag. Live signals resume against the exact pre-demo state.

Replay signals are tagged by a `raw_ref` that starts with REPLAY_PREFIX; every
other signal that arrives while the flag is up is treated as live and dropped.

This module is the single source of truth for those conventions so the ingest
consumer, the monitor, and the demo script agree.
"""
from __future__ import annotations

DEMO_FLAG_KEY   = "sage:demo:active"    # "1" while a demo is running
DEMO_STATUS_KEY = "sage:demo:status"    # JSON blob surfaced at GET /api/demo/status
REPLAY_PREFIX   = "REPLAY:"             # raw_ref prefix that marks a replay signal

# Faster cadence while a demo is active (seconds).
DEMO_FLUSH_INTERVAL_S = 3
DEMO_POLL_INTERVAL_S  = 3


async def is_demo_active(client) -> bool:
    """True when a demo sandbox is currently running. Never raises."""
    try:
        return (await client.get(DEMO_FLAG_KEY)) == "1"
    except Exception:
        return False


def is_replay_signal(signal) -> bool:
    """True for signals emitted by the demo replay (raw_ref starts with REPLAY:)."""
    raw_ref = getattr(signal, "raw_ref", None)
    return bool(raw_ref and raw_ref.startswith(REPLAY_PREFIX))
