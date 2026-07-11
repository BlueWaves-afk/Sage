#!/usr/bin/env python3
"""
G7 — load wellhead (ProductionField) + distribution (DistributionHub) nodes and
their PRODUCES_AT / DISTRIBUTES_TO edges DIRECTLY into the live graph via cypher.

Why direct cypher, not sage_instantiate: the supported instantiate path runs
add_episode (Nova entity extraction) for every fact in the whole bundle — costly
and slow on the demo host, and redundant when we only need to add ~18 new nodes.
These nodes carry deterministic ground-truth attributes; the LLM adds nothing.
The frontend map positions them from the registry (resolve_coordinates), so the
node just needs the :Entity label, a `labels` property, and a name that matches
the registry canonical_name — no name_embedding required for the structural map.

Idempotent: MERGE on name, so re-running updates in place.

    docker exec sage-sage-core-1 python3 /app/scripts/load_g7_nodes.py
"""
from __future__ import annotations

import asyncio
import csv
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

BUNDLE = ROOT / "data" / "india-energy-2026.context" / "facts"
FALKOR_URL = f"redis://{os.environ.get('FALKORDB_HOST', 'falkordb')}:{os.environ.get('FALKORDB_PORT', '6379')}"
GRAPH = os.environ.get("FALKOR_GRAPH", "sage")


def _rows(path: Path) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


async def main() -> None:
    import redis.asyncio as aioredis
    from knowledge.registry import REGISTRY

    falkor = aioredis.from_url(FALKOR_URL, decode_responses=True)

    def lit(v) -> str:
        """Format a Python value as a cypher literal (FalkorDB GRAPH.QUERY has no
        param binding over the raw redis protocol, so inline safely-escaped values)."""
        if isinstance(v, (int, float)):
            return repr(v)
        s = str(v).replace("\\", "\\\\").replace("'", "\\'")
        return f"'{s}'"

    async def q(cypher: str):
        return await falkor.execute_command("GRAPH.QUERY", GRAPH, cypher)

    def name_of(entity_id: str) -> str | None:
        e = REGISTRY.get(entity_id)
        return e.canonical_name if e else None

    # ── Nodes ────────────────────────────────────────────────────────────────
    field_rows = _rows(BUNDLE / "nodes" / "production_fields.csv")
    hub_rows = _rows(BUNDLE / "nodes" / "distribution_hubs.csv")

    n_nodes = 0
    for r in field_rows:
        u = str(uuid.uuid5(uuid.NAMESPACE_DNS, r["entity_id"]))
        summary = (f"{r['canonical_name']} ({r['country']}) — production field, "
                   f"{r['output_mbpd']} mbpd output, {r['spare_mbpd']} mbpd spare.")
        cy = (
            f"MERGE (n:Entity {{name: {lit(r['canonical_name'])}}}) "
            f"SET n:ProductionField, n.uuid = {lit(u)}, n.group_id = '_', "
            f"n.labels = ['ProductionField','Entity'], "
            f"n.location_lat = {lit(float(r['location_lat']))}, "
            f"n.location_lon = {lit(float(r['location_lon']))}, "
            f"n.output_mbpd = {lit(float(r['output_mbpd']))}, "
            f"n.spare_mbpd = {lit(float(r['spare_mbpd']))}, "
            f"n.country = {lit(r['country'])}, n.prov_tier = {lit(r['tier'])}, "
            f"n.prov_source_label = {lit(r['source'])}, n.prov_as_of = {lit(r['as_of'])}, "
            f"n.summary = {lit(summary)}"
        )
        await q(cy)
        n_nodes += 1

    for r in hub_rows:
        u = str(uuid.uuid5(uuid.NAMESPACE_DNS, r["entity_id"]))
        summary = (f"{r['canonical_name']} ({r['region']}) — distribution hub, "
                   f"{r['demand_mbpd']} mbpd demand ({r['primary_product_mix']}).")
        cy = (
            f"MERGE (n:Entity {{name: {lit(r['canonical_name'])}}}) "
            f"SET n:DistributionHub, n.uuid = {lit(u)}, n.group_id = '_', "
            f"n.labels = ['DistributionHub','Entity'], "
            f"n.location_lat = {lit(float(r['location_lat']))}, "
            f"n.location_lon = {lit(float(r['location_lon']))}, "
            f"n.demand_mbpd = {lit(float(r['demand_mbpd']))}, "
            f"n.region = {lit(r['region'])}, n.prov_tier = {lit(r['tier'])}, "
            f"n.prov_source_label = {lit(r['source'])}, n.prov_as_of = {lit(r['as_of'])}, "
            f"n.summary = {lit(summary)}"
        )
        await q(cy)
        n_nodes += 1

    # ── Edges (structural RELATES_TO with a name property, graphiti shape) ─────
    n_edges = 0
    for fname, rel in (("produces_at.csv", "PRODUCES_AT"), ("distributes_to.csv", "DISTRIBUTES_TO")):
        for r in _rows(BUNDLE / "edges" / fname):
            src_name = name_of(r["source_id"]) or r["source_id"]
            tgt_name = name_of(r["target_id"]) or r["target_id"]
            fact = f"{src_name} {r['relation']} {tgt_name}"
            cy = (
                f"MATCH (a:Entity {{name: {lit(src_name)}}}), (b:Entity {{name: {lit(tgt_name)}}}) "
                f"MERGE (a)-[e:RELATES_TO {{name: {lit(r['relation'])}}}]->(b) "
                f"SET e.fact = {lit(fact)}"
            )
            await q(cy)
            n_edges += 1

    print(f"G7 load complete: {n_nodes} nodes, {n_edges} edges merged.")
    await falkor.aclose()


if __name__ == "__main__":
    asyncio.run(main())
