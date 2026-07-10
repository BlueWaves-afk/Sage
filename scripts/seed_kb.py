"""
Bootstrap the SAGE knowledge base from the sourced context bundle.

Populates the foundational (Store 1/2/3) knowledge:
  1. /wiki markdown store      — narrative intelligence pages per entity
  2. Episodic subgraph         — structural episodes via add_episode()
  3. Semantic entity subgraph  — typed entity nodes + structural edges

This is exactly the `SAGE.instantiate(bundle)` step — the same call
`scripts/sage_instantiate.py` makes directly. No risk scores, scenarios,
procurement recommendations, or sample signals are written here: those must
come from real System 1 signals (live AIS/news/price/sanctions) and real
System 2/3/4 runs (autonomous threshold-crossing or a manual Simulation Lab
run), never from fabricated seed data. A fresh deployment starts all-CALM —
risk state should only ever reflect what the live system has actually
observed.

Run inside a container that has FalkorDB access:
  docker exec -it sage-api-gateway-1 python scripts/seed_kb.py

Or from your host (requires FALKORDB_HOST=localhost in env):
  FALKORDB_HOST=localhost LLM_PROVIDER=stub python scripts/seed_kb.py
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env / .env.local so LLM_PROVIDER=bedrock + AWS creds are set (else the
# stub LLM runs and no entities are extracted from episodes).
try:
    from config_env import load_local_env
    load_local_env()
except Exception:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger("seed_kb")

# The foundational static knowledge (corridors, suppliers, refineries, crude
# grades, ports, SPR, and their structural edges) lives in a versioned,
# provenance-tracked CONTEXT BUNDLE at data/india-energy-2026.context — NOT
# hardcoded here. Swap CONTEXT_BUNDLE for a newer/region-specific bundle to
# re-base the worldview. See data/CONTEXT_BUNDLE_SCHEMA.md for the format.
CONTEXT_BUNDLE = os.environ.get("SAGE_CONTEXT_BUNDLE", "data/india-energy-2026.context")


async def main() -> None:
    log.info("Bootstrapping SAGE knowledge base from context bundle…")
    os.makedirs("demo_cache", exist_ok=True)

    # ── Init KB ──────────────────────────────────────────────────────────────
    from knowledge.connection import init as kb_init
    await kb_init()
    log.info("KB initialised.")

    # ── Instantiate the context bundle (foundational static knowledge) ───────
    # Loads + validates the provenance-tracked bundle, then writes its
    # structural episodes + reconciled narrative pages. No risk state, no
    # scenario/procurement/SPR output, no sample signals — those are only
    # ever written by the live system.
    from graphiti_core.nodes import EpisodeType  # noqa: F401 (re-exported for callers importing this module)
    from knowledge.connection import _get_graphiti
    from knowledge.context import load_bundle

    g = _get_graphiti()
    now = datetime.now(timezone.utc)

    bundle = load_bundle(CONTEXT_BUNDLE)
    bsum = bundle.summary()
    log.info("Context bundle '%s' (schema %s): nodes=%s edges=%s by_tier=%s",
             bsum["bundle_id"], bsum["schema"], bsum["nodes"], bsum["edges"], bsum["by_tier"])
    counts = await bundle.instantiate(g, reference_time=now)
    log.info("Instantiated bundle: %d fact episodes + %d narrative pages "
             "(wiki store + reconciled episodes).", counts["facts"], counts["narratives"])

    # ── Read back and verify ──────────────────────────────────────────────────
    log.info("─── Verification ────────────────────────────────────────────────")
    from knowledge.api.read import (
        get_risk_scores, get_wiki_page, get_available_suppliers,
        get_subgraph, get_grade_specs, get_routes, get_spr_state,
    )
    from knowledge.synthesis import list_wiki_entities as list_wiki_pages

    wiki_pages = list_wiki_pages()
    log.info("Wiki pages on disk: %d", len(wiki_pages))

    scores = await get_risk_scores()
    log.info("Risk scores in graph: %d entities (expected 0 — risk state only comes "
             "from live System 1 signals, never from seeding)", len(scores))

    page = await get_wiki_page("Strait of Hormuz")
    log.info("Wiki page retrieved: %s (length=%d chars)", page.entity, len(page.content))

    # Verify structural data landed (the values Systems 2/3/4 read)
    suppliers = await get_available_suppliers(risk_max=1.0)
    log.info("Suppliers queryable: %d (with daily_export_mbpd populated)", len(suppliers))
    grades = await get_grade_specs("Jamnagar Refinery")
    log.info("Jamnagar CONFIGURED_FOR grades: %d (api_gravity/compatibility populated)", len(grades))
    routes = await get_routes(risk_max=1.0)
    log.info("Corridors queryable: %d (with throughput_mbpd)", len(routes))
    caverns = await get_spr_state()
    log.info("SPR caverns queryable: %d (with capacity_mmt/current_fill_mmt)", len(caverns))
    sub = await get_subgraph("Strait of Hormuz", hops=2)
    log.info("Hormuz 2-hop subgraph: %d nodes, %d edges (ARIO input)", len(sub.nodes), len(sub.edges))

    log.info("─── Bootstrap complete ──────────────────────────────────────────")
    log.info("  Risk state, scenarios, and procurement/SPR recommendations will")
    log.info("  populate organically as System 1 sensory agents ingest real")
    log.info("  signals, or when a Simulation Lab run is triggered manually.")
    log.info("  FalkorDB browser: http://localhost:3000")
    log.info("  API:              http://localhost:8000/api/risk-scores")
    log.info("  Wiki page:        http://localhost:8000/api/wiki/Strait%%20of%%20Hormuz")


if __name__ == "__main__":
    asyncio.run(main())
