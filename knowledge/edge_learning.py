"""
Edge-weight learning — the "second brain grows".

Exposure weights (throughput_share_pct on the dependency edges) start from the
sourced .context bundle. This module lets the KB REFINE them from live System-1
signals: when an ingested signal implies a change in how much one entity depends
on another (a reroute, a sourcing shift, a corridor closure), the synthesis LLM
extracts the updated share and we write it BITEMPORALLY — the prior value is kept
with the time it was superseded, the new value is stamped with valid_at + the
episode that justifies it. So every weight traces to either .context (seed) or a
specific real signal (learned), and the cascade propagates risk using the latest
learned dependency.

The LLM RECONCILES evidence into a number; it never invents one unprompted — the
detector only fires when a signal actually describes a dependency change, and the
result is tagged tier="learned" with its source episode.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)

_EDGE_TYPES = {"FEEDS", "SUPPLIES", "EXPORTS_VIA", "EXPOSES"}


async def refine_edge_weight(src: str, dst: str, edge_type: str, new_share: float,
                             source: str, rationale: str, episode_ref: str | None = None) -> bool:
    """
    Bitemporally update a dependency edge's exposure weight. Keeps the prior value
    (+ when it was superseded) and stamps the new value with provenance. Returns
    True if an edge was updated.
    """
    if edge_type not in _EDGE_TYPES:
        return False
    new_share = max(0.0, min(1.0, float(new_share)))
    now = datetime.now(timezone.utc).isoformat()

    from knowledge.connection import _get_graphiti
    driver = _get_graphiti().driver
    try:
        res = await driver.execute_query(
            """
            MATCH (a:Entity {name:$src})-[r:RELATES_TO]->(b:Entity {name:$dst})
            WHERE r.name = $etype
            SET r.throughput_share_pct_prev  = r.throughput_share_pct,
                r.weight_superseded_at        = CASE WHEN r.throughput_share_pct IS NULL
                                                     THEN NULL ELSE $now END,
                r.throughput_share_pct        = $new,
                r.weight_valid_at             = $now,
                r.weight_tier                 = 'learned',
                r.weight_source               = $source,
                r.weight_rationale            = $rationale,
                r.weight_episode              = $episode
            RETURN count(r) AS n
            """,
            src=src, dst=dst, etype=edge_type, new=new_share, now=now,
            source=source, rationale=rationale, episode=(episode_ref or ""),
        )
        records = res[0] if isinstance(res, tuple) else res
        n = 0
        for rec in (records or []):
            n = rec.get("n") if isinstance(rec, dict) else rec["n"]
        if n:
            log.info("[learn] edge %s -%s-> %s exposure → %.2f (%s)",
                     src, edge_type, dst, new_share, source)
            return True
    except Exception as exc:
        log.warning("[learn] refine_edge_weight failed (%s -%s-> %s): %s",
                    src, edge_type, dst, exc)
    return False


_DETECT_PROMPT = """You maintain a supply-chain dependency graph for India's crude oil imports.
Entities include corridors (Strait of Hormuz, ...), ports, refineries, suppliers.
Dependency edges carry an exposure share in [0,1] = how much the dependent relies on the source.

A news/price/AIS signal just arrived:
"{summary}"

Does this signal describe a CHANGE in a dependency share between two tracked entities
(e.g. a refinery sourcing less crude via a corridor, a reroute, a new supply line)?

Respond with STRICT JSON only:
{{"change": true/false, "src": "<source entity canonical name>", "dst": "<dependent entity canonical name>",
  "edge_type": "FEEDS|SUPPLIES|EXPORTS_VIA|EXPOSES", "new_share": 0.0-1.0, "rationale": "<one sentence>"}}
If no dependency change is implied, return {{"change": false}}."""


async def learn_dependency_updates(signal) -> int:
    """
    Use the synthesis LLM to detect a dependency-share change in a signal and, if
    found, refine the edge weight bitemporally. Best-effort — never raises into the
    ingest path. Returns the number of edges updated.
    """
    summary = getattr(signal, "summary", "") or ""
    if not summary:
        return 0
    try:
        from knowledge.synthesis import _call_nova_pro
        raw = await _call_nova_pro(_DETECT_PROMPT.format(summary=summary.replace('"', "'")),
                                   entity="edge-learning")
        # tolerate prose around the JSON
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end < 0:
            return 0
        data = json.loads(raw[start:end + 1])
    except Exception as exc:
        log.debug("[learn] detector parse failed: %s", exc)
        return 0

    if not data.get("change"):
        return 0
    ok = await refine_edge_weight(
        src=_resolve(str(data.get("src", "")).strip()),
        dst=_resolve(str(data.get("dst", "")).strip()),
        edge_type=str(data.get("edge_type", "")).strip().upper(),
        new_share=float(data.get("new_share", 0.0)),
        source=f"learned from signal {getattr(signal, 'signal_id', '?')}",
        rationale=str(data.get("rationale", ""))[:200],
        episode_ref=getattr(signal, "signal_id", None),
    )
    return 1 if ok else 0


def _resolve(name: str) -> str:
    """Resolve an LLM-returned name to the canonical registry name (e.g. 'Vadinar
    port' → 'Vadinar'), so the edge match hits. Falls back to the raw name."""
    if not name:
        return name
    try:
        from knowledge.registry import resolve_name, canonical_name
        eid = resolve_name(name)
        if eid:
            return canonical_name(eid)
    except Exception:
        pass
    return name
