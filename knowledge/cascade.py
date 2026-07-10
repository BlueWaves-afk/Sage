"""
Risk cascade — propagate a computed RISK_STATE across the supply-chain graph.

Fusion assigns a *primary* risk score to an entity from its own direct signals.
But a crisis at a chokepoint (e.g. a CRITICAL Strait of Hormuz) should raise the
risk of everything that DEPENDS on it — refineries it exposes, ports it feeds,
suppliers that export through it. This module propagates that risk along the
dependency edges with per-hop decay, so one crisis lights up the whole affected
chain instead of a single isolated node.

Cascaded scores are written as RISK_STATE with a rationale that names the source
and path, so they trace back exactly like everything else. They only ever RAISE a
dependent's risk (max semantics) — never lower a signal-driven score.

Direction of dependency (risk flows FROM the risky entity TO its dependents):
  Corridor -EXPOSES->  Refinery      (refinery depends on the corridor)
  Port     -FEEDS->    Refinery      (refinery depends on the port)
  Supplier -SUPPLIES-> Refinery      (refinery depends on the supplier)
  Supplier -EXPORTS_VIA-> Corridor   (supplier depends on the corridor → reverse)
"""
from __future__ import annotations

import logging
import os
from collections import deque

log = logging.getLogger(__name__)

CASCADE_DECAY   = float(os.environ.get("RISK_CASCADE_DECAY", "0.6"))   # per hop
CASCADE_MAXHOPS = int(os.environ.get("RISK_CASCADE_MAXHOPS", "2"))
CASCADE_MIN     = float(os.environ.get("RISK_CASCADE_MIN", "0.15"))    # stop below this

# Forward edges: risk flows source → target. Reverse edges: target → source.
_FORWARD = {"EXPOSES", "FEEDS", "SUPPLIES"}
_REVERSE = {"EXPORTS_VIA"}


def _edge_weight(edge: str, share, vol) -> float:
    """
    Per-edge exposure weight in [0,1] — how much the dependent relies on the source.
    Uses the .context-sourced throughput_share_pct (FEEDS/SUPPLIES) where present;
    falls back to the flat CASCADE_DECAY when the edge has no learned weight yet.
    """
    try:
        if share is not None and str(share) != "":
            w = float(share)
            return max(0.0, min(1.0, w))
    except Exception:
        pass
    # EXPORTS_VIA carries volume, not a share — treat any real dependency as moderate
    # until a share is learned; still better than nothing but capped below a true share.
    if edge == "EXPORTS_VIA" and vol not in (None, ""):
        return CASCADE_DECAY
    return CASCADE_DECAY


async def _neighbours(driver, entity: str) -> list[tuple[str, str, float]]:
    """Return [(dependent_name, edge_type, exposure_weight)] that inherit risk."""
    out: list[tuple[str, str, float]] = []
    fwd = await driver.execute_query(
        "MATCH (a:Entity {name:$n})-[r:RELATES_TO]->(b:Entity) WHERE r.name IN $types "
        "RETURN b.name AS dep, r.name AS edge, r.throughput_share_pct AS share, r.volume_mbpd AS vol",
        n=entity, types=list(_FORWARD),
    )
    rev = await driver.execute_query(
        "MATCH (b:Entity)-[r:RELATES_TO]->(a:Entity {name:$n}) WHERE r.name IN $types "
        "RETURN b.name AS dep, r.name AS edge, r.throughput_share_pct AS share, r.volume_mbpd AS vol",
        n=entity, types=list(_REVERSE),
    )
    for rows in (fwd, rev):
        records = rows[0] if isinstance(rows, tuple) else rows
        for rec in (records or []):
            g = (lambda k: rec.get(k) if isinstance(rec, dict) else rec[k])
            dep = g("dep")
            if dep:
                out.append((str(dep), str(g("edge")), _edge_weight(str(g("edge")), g("share"), g("vol"))))
    return out


async def cascade_risk_from(source_entity: str, source_score: float) -> int:
    """
    Propagate `source_entity`'s risk to its dependents (BFS, decaying per hop).
    Writes cascaded RISK_STATE (max semantics). Returns the number of entities raised.
    """
    if source_score < CASCADE_MIN:
        return 0

    from knowledge.connection import _get_graphiti
    from knowledge.api.read import get_risk_scores
    from knowledge.api.write import write_risk_state

    driver = _get_graphiti().driver
    current = {r.entity: float(r.score) for r in await get_risk_scores()}

    raised = 0
    seen = {source_entity}
    # queue holds (entity, inherited_score, hop, path)
    q: deque = deque()
    for dep, edge, w in await _neighbours(driver, source_entity):
        q.append((dep, source_score * w, 1, f"{source_entity} -{edge}({w:.2f})->"))

    while q:
        entity, inherited, hop, path = q.popleft()
        if entity in seen or inherited < CASCADE_MIN:
            continue
        seen.add(entity)

        if inherited > current.get(entity, 0.0):
            try:
                await write_risk_state(
                    entity=entity,
                    score=round(inherited, 4),
                    factor_ais=0.0, factor_gdelt=0.0, factor_price=0.0, factor_sanctions=0.0,
                    rationale=(f"cascaded risk {inherited:.2f} from {source_entity} "
                               f"({hop} hop{'s' if hop > 1 else ''}, exposure-weighted: {path} {entity})"),
                    model_version="cascade-v1",
                )
                current[entity] = inherited
                raised += 1
            except Exception as exc:
                log.warning("cascade write failed for '%s': %s", entity, exc)

        if hop < CASCADE_MAXHOPS:
            for dep, edge, w in await _neighbours(driver, entity):
                q.append((dep, inherited * w, hop + 1, f"{path} {entity} -{edge}({w:.2f})->"))

    if raised:
        log.info("cascade: '%s' (%.2f) raised %d dependent entities", source_entity, source_score, raised)
    return raised
