"""
Graph canonicalization / de-duplication.

LLM extraction (graphiti) sometimes creates:
  • duplicate edges  — the same (source, target, edge-type) extracted from several
    sentences (e.g. EXPORTS_VIA Aramco→Hormuz stated three ways);
  • alias-variant nodes — "Abu Dhabi National Oil Company" as a separate node from
    the canonical "ADNOC", because the prose used the long form.

canonicalize_graph() cleans both, deterministically, against the registry:
  1. EDGE DEDUP    — keep one RELATES_TO per (src, dst, name), delete the rest.
  2. NODE MERGE    — for any node whose name is a registry ALIAS of a canonical
                     entity that also exists as a node, re-point its edges onto the
                     canonical node and delete the alias node.

Distinct concepts (e.g. the country "Saudi Arabia" vs the company "Saudi Aramco")
are left alone — only names that resolve to a canonical entity via the registry
alias table are merged.

Run after instantiate():  await canonicalize_graph(graphiti)
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


async def _cy(query: str, params: dict | None = None) -> list[dict]:
    from knowledge.api.read import _cypher
    return await _cypher(query, params or {})


async def _dedup_edges() -> int:
    """Keep one RELATES_TO per (source, target, name); delete duplicates."""
    # Count first (for reporting), then delete all-but-one in each group.
    before = await _cy("MATCH ()-[r:RELATES_TO]->() RETURN count(r) AS c")
    n0 = before[0]["c"] if before else 0
    await _cy(
        """
        MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity)
        WITH a, b, r.name AS nm, collect(r) AS rels
        WHERE size(rels) > 1
        FOREACH (x IN rels[1..] | DELETE x)
        """
    )
    after = await _cy("MATCH ()-[r:RELATES_TO]->() RETURN count(r) AS c")
    n1 = after[0]["c"] if after else 0
    return max(0, n0 - n1)


async def _merge_alias_nodes() -> int:
    """
    Merge alias-variant nodes into their canonical node.
    Returns the number of nodes merged away.
    """
    from knowledge.registry import REGISTRY, ALIAS_TO_ENTITY

    # All distinct entity names currently in the graph.
    rows = await _cy("MATCH (n:Entity) RETURN collect(DISTINCT n.name) AS names")
    names = set(rows[0]["names"]) if rows and rows[0].get("names") else set()
    canon_present = {REGISTRY[e].canonical_name for e in REGISTRY if REGISTRY[e].canonical_name in names}

    merged = 0
    for name in names:
        eid = ALIAS_TO_ENTITY.get(name.strip().lower())
        if not eid or eid not in REGISTRY:
            continue
        canonical = REGISTRY[eid].canonical_name
        if name == canonical or canonical not in canon_present:
            continue  # already canonical, or no canonical node to merge into

        try:
            # Re-point outgoing edges, then incoming edges, then delete the dup node.
            await _cy(
                """
                MATCH (dup:Entity {name:$a})-[r:RELATES_TO]->(t:Entity)
                MATCH (canon:Entity {name:$c})
                WHERE dup <> canon
                CREATE (canon)-[nr:RELATES_TO]->(t) SET nr = properties(r)
                DELETE r
                """,
                {"a": name, "c": canonical},
            )
            await _cy(
                """
                MATCH (s:Entity)-[r:RELATES_TO]->(dup:Entity {name:$a})
                MATCH (canon:Entity {name:$c})
                WHERE dup <> canon
                CREATE (s)-[nr:RELATES_TO]->(canon) SET nr = properties(r)
                DELETE r
                """,
                {"a": name, "c": canonical},
            )
            await _cy("MATCH (dup:Entity {name:$a}) DETACH DELETE dup", {"a": name})
            merged += 1
            log.info("  merged alias node '%s' → '%s'", name, canonical)
        except Exception as exc:
            log.warning("  merge failed for '%s' → '%s': %s", name, canonical, exc)

    # Edge dedup again — merging can create new duplicates.
    await _dedup_edges()
    return merged


# Edge type → the numeric attribute columns that must be exact (not LLM-extracted).
_EDGE_ATTR_COLS = {
    "EXPORTS_VIA":    ["volume_mbpd"],
    "FEEDS":          ["throughput_share_pct"],
    "SUPPLIES":       ["throughput_share_pct"],
    "CONFIGURED_FOR": ["compatibility", "yield_pct"],
    "BYPASS_ROUTE":   ["cost_premium", "added_days"],
}


async def reconcile_edge_attributes(bundle) -> int:
    """
    Overwrite LLM-extracted edge attributes with the bundle's EXACT facts values.

    Graphiti's extractor populates edge numerics (throughput_share_pct, volume_mbpd, …)
    unreliably — values come out missing, 0, or wrong. ARIO (System 2) depends on
    these. So we deterministically SET them from the facts CSVs, matching the
    RELATES_TO edge by canonical src/dst names + edge type. Returns edges updated.
    """
    from knowledge.registry import REGISTRY

    def _cn(eid: str) -> str:
        e = REGISTRY.get(eid)
        return e.canonical_name if e else eid

    updated = 0
    for etype, rows in bundle.edge_rows.items():
        cols = _EDGE_ATTR_COLS.get(etype, [])
        if not cols:
            continue
        for r in rows:
            src, dst = _cn(r["src_entity_id"]), _cn(r["dst_entity_id"])
            attrs = {}
            for c in cols:
                v = r.get(c)
                if v not in (None, ""):
                    try:
                        attrs[c] = float(v)
                    except ValueError:
                        attrs[c] = v
            if not attrs:
                continue
            # SET exact values on every matching edge (covers any residual duplicates).
            set_clause = ", ".join(f"r.{k} = ${k}" for k in attrs)
            await _cy(
                f"MATCH (a:Entity {{name:$src}})-[r:RELATES_TO]->(b:Entity {{name:$dst}}) "
                f"WHERE r.name = $etype SET {set_clause}",
                {"src": src, "dst": dst, "etype": etype, **attrs},
            )
            updated += 1
    log.info("reconcile_edge_attributes: set exact values on %d edge specs", updated)
    return updated


async def derive_exposures() -> int:
    """
    Materialise per-refinery corridor exposure at ingestion (a derived-attributes pass).

    exposure(corridor, refinery) = Σ_port  FEEDS(corridor→port).share × SUPPLIES(port→refinery).share

    Written as a derived  (Corridor)-[RELATES_TO {name:'EXPOSES', exposure_pct}]->(Refinery)
    edge so System 2 reads each refinery's exposure to the disrupted corridor directly
    (no query-time traversal). Recompute by calling this again whenever the share edges
    change (e.g. System 1 mutates topology). Returns edges written.
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    # Fresh recompute: drop the old derived layer.
    await _cy("MATCH ()-[r:RELATES_TO]->() WHERE r.name='EXPOSES' DELETE r")

    # Aggregate the two-hop share product, then create one EXPOSES edge per (corridor, refinery).
    await _cy(
        """
        MATCH (c:Entity)-[f:RELATES_TO]->(p:Entity)-[s:RELATES_TO]->(r:Entity)
        WHERE f.name='FEEDS' AND s.name='SUPPLIES'
          AND 'Corridor' IN c.labels AND 'Refinery' IN r.labels
        WITH c, r, sum(coalesce(f.throughput_share_pct,0.0) * coalesce(s.throughput_share_pct,0.0)) AS exposure
        WHERE exposure > 0.0001
        CREATE (c)-[:RELATES_TO {name:'EXPOSES', exposure_pct: exposure, valid_at: $now}]->(r)
        """,
        {"now": now},
    )
    rows = await _cy("MATCH ()-[r:RELATES_TO]->() WHERE r.name='EXPOSES' RETURN count(r) AS c")
    n = rows[0]["c"] if rows else 0
    log.info("derive_exposures: wrote %d corridor→refinery EXPOSES edges", n)
    return n


async def canonicalize_graph(graphiti=None) -> dict[str, int]:
    """
    Full canonicalization pass. Safe to run repeatedly (idempotent).
    Returns {edges_removed, nodes_merged}.
    """
    edges_removed = await _dedup_edges()
    nodes_merged = await _merge_alias_nodes()
    log.info("canonicalize_graph: removed %d duplicate edges, merged %d alias nodes",
             edges_removed, nodes_merged)
    return {"edges_removed": edges_removed, "nodes_merged": nodes_merged}
