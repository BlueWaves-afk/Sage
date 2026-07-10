"""
Volatile-tier refresh — pulls fresh values for the middle tier and writes them
into the override store (knowledge/context/volatile.py).

Two modes, chosen by DEMO_MODE:
  - DEMO_MODE=true  → load data/demo_fixtures/volatile_feb2026.json (crisis values,
                      reproducible offline). This is what makes the demo show fresh,
                      crisis-accurate numbers instead of the calm bundle seeds.
  - DEMO_MODE=false → fetch live: Brent via yfinance BZ=F (EIA fallback). Other
                      volatile params reuse the last live value or bundle seed until
                      their own live adapters are wired (freight, spare, etc.).

Called by the refresh_volatile LangGraph node on the event-driven path (a threshold
crossing / high-priority signal), NOT on a continuous poll.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from knowledge.context.volatile import set_volatile, get_all_volatile

log = logging.getLogger(__name__)

_FIXTURE = Path(os.environ.get(
    "VOLATILE_FIXTURE",
    "data/demo_fixtures/volatile_feb2026.json",
))


def _demo_mode() -> bool:
    return os.environ.get("DEMO_MODE", "false").strip().lower() in ("1", "true", "yes")


def _refresh_from_fixture() -> dict[str, float]:
    """DEMO_MODE: load the pinned crisis fixture into the override store."""
    changed: dict[str, float] = {}
    try:
        data = json.loads(_FIXTURE.read_text())
    except Exception as exc:
        log.warning("volatile fixture unavailable (%s): %s", _FIXTURE, exc)
        return changed
    as_of = data.get("as_of")
    for param, row in (data.get("params") or {}).items():
        try:
            set_volatile(param, float(row["value"]), source=row.get("source", "fixture"),
                         as_of=as_of, unit=row.get("unit", ""))
            changed[param] = float(row["value"])
        except Exception as exc:
            log.debug("fixture param %s skipped: %s", param, exc)
    log.info("[volatile] DEMO_MODE fixture loaded: %s", changed)
    return changed


def _live_brent() -> float | None:
    """Fetch live Brent (yfinance BZ=F, EIA fallback)."""
    try:
        import yfinance as yf
        h = yf.Ticker("BZ=F").history(period="1d")
        if len(h):
            return round(float(h["Close"].iloc[-1]), 2)
    except Exception as exc:
        log.debug("yfinance Brent failed: %s", exc)
    try:
        import urllib.request
        key = os.environ.get("EIA_API_KEY", "")
        if key:
            u = (f"https://api.eia.gov/v2/petroleum/pri/spt/data/?api_key={key}"
                 "&frequency=daily&data[0]=value&facets[series][]=RBRTE"
                 "&sort[0][column]=period&sort[0][direction]=desc&length=1")
            d = json.loads(urllib.request.urlopen(u, timeout=15).read())
            return round(float(d["response"]["data"][0]["value"]), 2)
    except Exception as exc:
        log.debug("EIA Brent failed: %s", exc)
    return None


def _refresh_live() -> dict[str, float]:
    """Production: pull whatever live adapters we have. Brent today; others TBD."""
    changed: dict[str, float] = {}
    brent = _live_brent()
    if brent is not None:
        set_volatile("baseline_brent_usd_per_bbl", brent, source="yfinance/EIA (live)",
                     as_of=datetime.now(timezone.utc).isoformat(), unit="usd_per_bbl")
        changed["baseline_brent_usd_per_bbl"] = brent
    log.info("[volatile] live refresh: %s", changed)
    return changed


async def refresh_volatile() -> dict[str, float]:
    """
    Refresh the volatile tier and return the changed {param: value} set.
    Bust the scenario agent's param cache so Systems 2/3/4 recompute on fresh values.
    """
    changed = _refresh_from_fixture() if _demo_mode() else _refresh_live()

    # Bust caches so agents don't serve stale cached params (belt-and-suspenders;
    # the volatile params are also live-read via get_volatile()).
    try:
        import scenario_agent.runner as sr
        sr._PARAM_CACHE = None
        sr._SECTOR_CACHE = None
    except Exception:
        pass

    return changed


def current_provenance() -> dict:
    """All active overrides with their as_of/source — for the /api readback + UI."""
    return get_all_volatile()
