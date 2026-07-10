"""
Per-node source provenance.

Every value in the .context bundle carries a `tier` + `source` (validator-enforced),
and every `source` key resolves to a real citation {label, url} in manifest.sources.
This module stamps that provenance directly onto the FalkorDB entity nodes, so each
node in the graph traces back to an actual source with a clickable link — not just in
the CSV on disk, but on the live graph the UI reads.

Written as Phase 4 of loader.instantiate() (after canonicalize, so names are final).
"""
from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


def _resolve_source(manifest: dict, key: str) -> tuple[str, str]:
    """source key → (label, url) from manifest.sources or manifest.estimation_methods."""
    if not key:
        return "", ""
    sources = manifest.get("sources", {}) or {}
    if key in sources:
        row = sources[key] or {}
        return str(row.get("label", key)), str(row.get("url", ""))
    methods = manifest.get("estimation_methods", {}) or {}
    if key in methods:
        row = methods[key] or {}
        return str(row.get("label", key) or f"estimation method: {key}"), str(row.get("url", ""))
    return key, ""


async def write_node_provenance(bundle: Any, graphiti: Any) -> int:
    """
    Stamp prov_* properties onto each FalkorDB entity node from its bundle fact row.
    Returns the number of nodes stamped.
    """
    driver = graphiti.driver
    manifest = bundle.manifest
    stamped = 0

    for ntype, rows in bundle.node_rows.items():
        for row in rows:
            name = (row.get("canonical_name") or "").strip()
            if not name:
                continue
            key = (row.get("source") or "").strip()
            label, url = _resolve_source(manifest, key)
            try:
                await driver.execute_query(
                    """
                    MATCH (n:Entity {name: $name})
                    SET n.prov_source_key   = $key,
                        n.prov_source_label = $label,
                        n.prov_source_url   = $url,
                        n.prov_tier         = $tier,
                        n.prov_as_of        = $as_of,
                        n.prov_notes        = $notes
                    """,
                    name=name,
                    key=key,
                    label=label,
                    url=url,
                    tier=(row.get("tier") or "").strip(),
                    as_of=str(row.get("as_of") or ""),
                    notes=(row.get("notes") or "").strip(),
                )
                stamped += 1
            except Exception as exc:
                log.warning("  provenance stamp failed for '%s': %s", name, exc)

    log.info("  provenance: stamped %d nodes with source/tier/url", stamped)
    return stamped
