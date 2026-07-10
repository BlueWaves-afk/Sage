"""
Volatile-tier override store.

The context bundle carries three tiers of data (see DATA_PROVENANCE.md §1b):
  - structural (annual)   — committed in the bundle, never overridden at runtime
  - volatile  (weekly–qtr) — cold-start SEEDS in the bundle; meant to be replaced
                             by fresh values at runtime
  - live      (sec–min)   — never static (RISK_STATE, positions) — System 1's job

This module is the runtime override layer for the *volatile* middle tier. Agents
read a volatile param through ``get_volatile(param, static_default)`` which returns
a fresh override if one has been written (by the refresh node / sensory agents),
otherwise the bundle's cold-start default. Precedence:

    live override  >  bundle cold-start seed

Provenance is preserved: the static CSV value remains the documented fallback; each
override carries its own ``as_of`` + ``source`` so the UI can show "Brent $103 · as of …".

Backend: a Redis hash (``sage:volatile``) so the refresh (sage-core) and the readers
(agents) share state across processes; falls back to an in-process dict when Redis is
unavailable (tests / single-process runs).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

log = logging.getLogger(__name__)

VOLATILE_KEY = "sage:volatile"
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

# In-process mirror — authoritative when Redis is down; also a read cache.
_local: dict[str, dict[str, Any]] = {}


def _redis():
    """Return a sync redis client, or None if unavailable."""
    try:
        import redis
        c = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=1)
        c.ping()
        return c
    except Exception:
        return None


def set_volatile(param: str, value: float, source: str = "runtime",
                 as_of: Optional[str] = None, unit: str = "") -> None:
    """Write a fresh override for a volatile param (used by the refresh adapters)."""
    entry = {
        "value": float(value),
        "source": source,
        "unit": unit,
        "as_of": as_of or datetime.now(timezone.utc).isoformat(),
    }
    _local[param] = entry
    c = _redis()
    if c is not None:
        try:
            c.hset(VOLATILE_KEY, param, json.dumps(entry))
        except Exception as exc:
            log.debug("volatile set redis failed for %s: %s", param, exc)


def _read_entry(param: str) -> Optional[dict[str, Any]]:
    if param in _local:
        return _local[param]
    c = _redis()
    if c is not None:
        try:
            raw = c.hget(VOLATILE_KEY, param)
            if raw:
                entry = json.loads(raw)
                _local[param] = entry  # cache
                return entry
        except Exception as exc:
            log.debug("volatile get redis failed for %s: %s", param, exc)
    return None


def get_volatile(param: str, static_default: float) -> float:
    """
    Return the fresh override for ``param`` if present, else the bundle cold-start
    ``static_default``. This is the single accessor every volatile-param reader uses.
    """
    entry = _read_entry(param)
    if entry is not None and entry.get("value") is not None:
        return float(entry["value"])
    return float(static_default)


def get_all_volatile() -> dict[str, dict[str, Any]]:
    """All current overrides (for the /api provenance readback + UI as_of display)."""
    out: dict[str, dict[str, Any]] = dict(_local)
    c = _redis()
    if c is not None:
        try:
            for k, v in (c.hgetall(VOLATILE_KEY) or {}).items():
                try:
                    out[k] = json.loads(v)
                except Exception:
                    pass
        except Exception:
            pass
    return out


def clear_volatile() -> None:
    """Drop all overrides — reverts every volatile param to its bundle seed."""
    _local.clear()
    c = _redis()
    if c is not None:
        try:
            c.delete(VOLATILE_KEY)
        except Exception:
            pass
