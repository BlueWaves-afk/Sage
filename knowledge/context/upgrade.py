"""
Bundle upgrade mechanism.

Applies a new .context bundle on top of an existing live knowledge base,
replacing only structural layers while preserving all dynamic data:

  REPLACE:  facts (node/edge attributes), params, io sector weights
  PRESERVE: RISK_STATE edges, GeoEvent nodes, Vessel nodes, Graphiti episodes,
            wiki pages written by System 1 (live signal reconciliations)

Usage:
    python3.11 -m knowledge.context.upgrade <new_bundle_path>

The upgrade is idempotent: running it twice with the same bundle is safe.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


# ── Cypher helpers ─────────────────────────────────────────────────────────────

async def _cy(query: str, params: dict | None = None) -> list[dict]:
    from knowledge.api.read import _cypher
    return await _cypher(query, params or {})


# ── Structural upsert helpers ──────────────────────────────────────────────────

async def _upsert_node_attributes(node_rows: dict[str, list[dict]]) -> int:
    """
    Upsert structural attributes onto existing nodes by canonical_name.
    Does NOT create new nodes — graphiti.add_episode handles creation.
    Returns count of attributes updated.
    """
    updated = 0
    for ntype, rows in node_rows.items():
        for row in rows:
            cname = row.get("canonical_name") or row.get("entity_id", "")
            if not cname:
                continue
            # Build SET clause from non-identity fields
            skip = {"canonical_name", "entity_id", "tier", "source", "as_of", "notes"}
            props = {k: v for k, v in row.items() if k not in skip and v is not None and v != ""}
            if not props:
                continue
            set_clause = ", ".join(f"n.{k} = ${k}" for k in props)
            await _cy(
                f"MATCH (n) WHERE n.name = $name SET {set_clause}",
                {"name": cname, **props},
            )
            updated += len(props)
    return updated


async def _upsert_edge_attributes(edge_rows: dict[str, list[dict]]) -> int:
    """
    Upsert numeric attributes onto existing RELATES_TO edges by (src, dst, name).
    Structural edge weights (volume_mbpd, compatibility, etc.) — not topology.
    Returns count of edges updated.
    """
    updated = 0
    for etype, rows in edge_rows.items():
        for row in rows:
            src = row.get("src_entity_id", "")
            dst = row.get("dst_entity_id", "")
            skip = {"src_entity_id", "dst_entity_id", "tier", "source", "notes"}
            props = {k: v for k, v in row.items() if k not in skip and v is not None and v != ""}
            if not props or not src or not dst:
                continue
            set_clause = ", ".join(f"r.{k} = ${k}" for k in props)
            # Match by src/dst canonical names and edge type
            result = await _cy(
                f"""
                MATCH (s)-[r:RELATES_TO]->(d)
                WHERE (s.name = $src OR s.entity_id = $src)
                  AND (d.name = $dst OR d.entity_id = $dst)
                  AND r.name = $etype
                SET {set_clause}
                RETURN count(r) AS n
                """,
                {"src": src, "dst": dst, "etype": etype, **props},
            )
            updated += (result[0]["n"] if result else 0)
    return updated


# ── Changed-entity detection ───────────────────────────────────────────────────

def _diff_nodes(old_bundle, new_bundle) -> list[str]:
    """Return entity_ids whose structured facts changed between bundles."""
    changed: list[str] = []
    for ntype, new_rows in new_bundle.node_rows.items():
        old_rows_idx = {
            r.get("entity_id", r.get("canonical_name", "")): r
            for r in old_bundle.node_rows.get(ntype, [])
        }
        for row in new_rows:
            eid = row.get("entity_id") or row.get("canonical_name", "")
            old = old_rows_idx.get(eid, {})
            # Compare only numeric/structural fields, not provenance metadata
            skip = {"tier", "source", "as_of", "notes", "entity_id", "canonical_name"}
            if any(row.get(k) != old.get(k) for k in row if k not in skip):
                changed.append(eid)
    return changed


# ── Wiki re-synthesis for changed entities ─────────────────────────────────────

async def _resynthesize_changed(
    new_bundle,
    changed_ids: list[str],
    graphiti,
) -> int:
    """
    For each entity whose structural facts changed, re-run the synthesis path
    (facts + existing dynamic wiki content) and append a '## Context Update' note.
    Preserves all dynamic content; only the structural summary section is updated.
    """
    from knowledge.registry import REGISTRY
    from knowledge.synthesis import render_wiki_page, write_wiki_page
    from knowledge.api.read import read_wiki_page
    from graphiti_core.nodes import EpisodeType
    from knowledge.schema.entities import ENTITY_TYPES
    from knowledge.schema.edges import EDGE_TYPES, EDGE_TYPE_MAP

    written = 0
    for eid in changed_ids:
        entry = REGISTRY.get(eid)
        canonical = entry.canonical_name if entry else eid
        etype = entry.entity_type if entry else "Unknown"

        # Read existing wiki page so dynamic content (System 1 updates) is preserved
        existing = read_wiki_page(canonical) or ""
        facts = new_bundle._entity_facts(eid)
        update_note = (
            f"\n\n## Context Update (bundle {new_bundle.manifest.get('bundle_version', '?')})\n"
            f"Structural facts updated. New values: {facts}\n"
        )
        new_body = existing.rstrip() + update_note if existing else (
            new_bundle._foundational_stub(eid, canonical, etype) + update_note
        )
        try:
            page = render_wiki_page(canonical, new_body, entity_id=eid, entity_type=etype)
            write_wiki_page(canonical, page)
            await graphiti.add_episode(
                name=f"upgrade-{new_bundle.bundle_id}-{eid}",
                episode_body=new_body,
                source=EpisodeType.text,
                source_description=f"Bundle upgrade {new_bundle.bundle_id} — structural facts updated",
                entity_types=ENTITY_TYPES, edge_types=EDGE_TYPES, edge_type_map=EDGE_TYPE_MAP,
            )
            written += 1
            log.info("[upgrade] re-synthesized: %s", canonical)
        except Exception as exc:
            log.warning("[upgrade] re-synthesis FAILED (%s): %s", eid, exc)
    return written


# ── Upgrade episode (audit trail) ─────────────────────────────────────────────

async def _write_upgrade_episode(old_version: str, new_version: str, graphiti, stats: dict) -> None:
    from graphiti_core.nodes import EpisodeType
    from knowledge.schema.entities import ENTITY_TYPES
    from knowledge.schema.edges import EDGE_TYPES, EDGE_TYPE_MAP
    from datetime import datetime, timezone

    body = (
        f"SAGE context bundle upgraded from {old_version} to {new_version} "
        f"on {datetime.now(timezone.utc).isoformat()}. "
        f"Structural layers replaced: facts, params, io. "
        f"Dynamic layers preserved: RISK_STATE edges, GeoEvent nodes, episodes, wiki narratives. "
        f"Stats: {stats}"
    )
    try:
        await graphiti.add_episode(
            name=f"bundle-upgrade-{old_version}-to-{new_version}",
            episode_body=body,
            source=EpisodeType.text,
            source_description="Bundle upgrade audit",
            entity_types=ENTITY_TYPES, edge_types=EDGE_TYPES, edge_type_map=EDGE_TYPE_MAP,
        )
        log.info("[upgrade] audit episode written")
    except Exception as exc:
        log.warning("[upgrade] audit episode failed (non-fatal): %s", exc)


# ── Main upgrade function ──────────────────────────────────────────────────────

async def upgrade_bundle(new_bundle_path: str | Path) -> dict[str, Any]:
    """
    Apply new_bundle on top of the live KB.

    Steps:
      1. Load new bundle; load current bundle from env-configured path
      2. Compare bundle_version; skip if already at target version
      3. Upsert structural node/edge attributes (REPLACE layer)
      4. Re-run reconcile_edge_attributes with new bundle values
      5. Re-run derive_exposures fresh
      6. Re-synthesize wiki for entities with changed facts
      7. Write upgrade audit episode
      8. Optionally update SAGE_BUNDLE_PATH env pointer

    Returns stats dict with counts of every operation performed.
    """
    from knowledge.context.loader import load_bundle
    from knowledge.context.dedup import reconcile_edge_attributes, derive_exposures

    new_bundle = load_bundle(new_bundle_path)
    new_ver = new_bundle.manifest.get("bundle_version", "unknown")

    # Try to load current bundle for diff (graceful — may not exist on first run)
    current_bundle_path = os.environ.get("SAGE_BUNDLE_PATH", "")
    old_ver = "none"
    old_bundle = None
    if current_bundle_path and Path(current_bundle_path).exists():
        try:
            old_bundle = load_bundle(current_bundle_path)
            old_ver = old_bundle.manifest.get("bundle_version", "unknown")
        except Exception as exc:
            log.warning("[upgrade] could not load current bundle for diff: %s", exc)

    if old_ver == new_ver:
        log.info("[upgrade] already at bundle_version %s — nothing to do", new_ver)
        return {"status": "already_current", "version": new_ver}

    log.info("[upgrade] upgrading %s → %s", old_ver, new_ver)

    # Graphiti client
    import graphiti_core
    from graphiti_core import Graphiti
    neo4j_uri      = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user     = os.environ.get("NEO4J_USER", "neo4j")
    neo4j_password = os.environ.get("NEO4J_PASSWORD", "password")
    graphiti = Graphiti(neo4j_uri, neo4j_user, neo4j_password)

    stats: dict[str, Any] = {"old_version": old_ver, "new_version": new_ver}

    # Step 3: upsert structural attributes (does not delete nodes/edges)
    log.info("[upgrade] upserting structural node attributes …")
    stats["node_attrs_updated"] = await _upsert_node_attributes(new_bundle.node_rows)

    log.info("[upgrade] upserting structural edge attributes …")
    stats["edge_attrs_updated"] = await _upsert_edge_attributes(new_bundle.edge_rows)

    # Step 4: re-reconcile edge numerics from new bundle
    log.info("[upgrade] reconciling edge attributes …")
    stats["edges_reconciled"] = await reconcile_edge_attributes(new_bundle)

    # Step 5: re-derive corridor exposures
    log.info("[upgrade] deriving exposures …")
    stats["exposures_derived"] = await derive_exposures()

    # Step 6: re-synthesize wiki for changed entities
    changed_ids: list[str] = []
    if old_bundle is not None:
        changed_ids = _diff_nodes(old_bundle, new_bundle)
        log.info("[upgrade] %d entities with changed facts → re-synthesizing wiki", len(changed_ids))
    else:
        log.info("[upgrade] no previous bundle for diff — skipping wiki re-synthesis")

    stats["wiki_resynced"] = await _resynthesize_changed(new_bundle, changed_ids, graphiti)

    # Step 7: audit episode
    await _write_upgrade_episode(old_ver, new_ver, graphiti, stats)

    log.info("[upgrade] complete: %s", stats)
    return stats


# ── CLI entry point ────────────────────────────────────────────────────────────

def _cli() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(
        description="Upgrade the SAGE knowledge base to a new .context bundle."
    )
    parser.add_argument(
        "bundle_path",
        help="Path to the new .context bundle directory (e.g. data/india-energy-2027.context)",
    )
    args = parser.parse_args()

    stats = asyncio.run(upgrade_bundle(args.bundle_path))
    print("\nUpgrade complete:")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    _cli()
