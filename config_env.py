"""
Lightweight .env loader (stdlib only — no python-dotenv dependency).

Loads key=value pairs from .env.local first, then .env, into os.environ
WITHOUT overriding variables already set in the real environment (so a
container's env_file / shell export always wins over the file).

Call load_local_env() at process entry BEFORE any module reads os.environ
for a key (e.g. the sensory sub-agents read their API keys at import time).
"""
from __future__ import annotations

import os
from pathlib import Path

# Repo root = this file's directory.
_ROOT = Path(__file__).resolve().parent
# .env.local (real secrets) takes precedence over .env (committed defaults/config).
_FILES = [".env.local", ".env"]


def _parse(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        # Strip optional surrounding quotes and inline export prefix.
        if key.startswith("export "):
            key = key[len("export "):].strip()
        val = val.strip().strip('"').strip("'")
        if key:
            out[key] = val
    return out


def load_local_env() -> None:
    """Merge .env.local then .env into os.environ (never overriding real env)."""
    merged: dict[str, str] = {}
    # Load in reverse precedence so earlier files win on merge.
    for name in reversed(_FILES):
        p = _ROOT / name
        if p.exists():
            merged.update(_parse(p))
    for key, val in merged.items():
        os.environ.setdefault(key, val)
