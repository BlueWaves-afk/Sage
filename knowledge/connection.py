"""
C0 — Graphiti connection, bootstrap, and module-level singleton.

One Graphiti instance is shared across the knowledge layer. All write
and read functions call `_get_graphiti()` to access it.

Call `init()` once at container startup (from the FastAPI lifespan or
from the LangGraph agent setup). After that, `_get_graphiti()` is safe
from any async context.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from graphiti_core import Graphiti
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.nodes import EpisodeType

from knowledge.bedrock import nova_micro, nova_pro, titan_embedder
from knowledge.schema.edges import EDGE_TYPES, EDGE_TYPE_MAP
from knowledge.schema.entities import ENTITY_TYPES

log = logging.getLogger(__name__)

SCHEMA_VERSION = "1.0.0"
GRAPH_NAME     = "sage"   # FalkorDB multi-tenant graph. Must NEVER be None.

_graphiti_instance: Optional[Graphiti] = None


def build_graphiti() -> Graphiti:
    """
    Construct a connected Graphiti instance wired to Bedrock Nova + Titan.

    Environment variables:
      FALKORDB_HOST       default: falkordb
      FALKORDB_PORT       default: 6379
      FALKORDB_USERNAME   optional
      FALKORDB_PASSWORD   optional
      AWS_REGION          default: ap-south-1
    """
    driver = FalkorDriver(
        host=os.environ.get("FALKORDB_HOST", "falkordb"),
        port=int(os.environ.get("FALKORDB_PORT", "6379")),
        username=os.environ.get("FALKORDB_USERNAME") or None,
        password=os.environ.get("FALKORDB_PASSWORD") or None,
        falkor_db=GRAPH_NAME,   # graphiti-core 0.29.x uses falkor_db= (not database=)
    )

    region = os.environ.get("AWS_REGION", "ap-south-1")

    return Graphiti(
        graph_driver=driver,
        llm_client=nova_pro(region),
        embedder=titan_embedder(region),
    )


async def bootstrap(g: Graphiti) -> None:
    """
    Idempotent startup sequence. Safe to call on every boot.
      1. Build FalkorDB indices and vector constraints.
      2. Seed one episode per edge type to prime Graphiti's extraction cache
         (mitigates issue #1111: custom edge attributes missing on first appearance).
    """
    log.info("Building FalkorDB indices and constraints…")
    await g.build_indices_and_constraints()
    log.info("Seeding edge types for extraction priming…")
    await _seed_edge_types(g)
    log.info("Knowledge base bootstrap complete.")


async def _seed_edge_types(g: Graphiti) -> None:
    """
    Write one tiny synthetic episode that mentions each edge type once.
    This ensures Graphiti's extraction model has seen every custom type before
    real signals arrive, avoiding the first-appearance attribute loss of issue #1111.

    Only runs if the seed episode doesn't already exist.
    """
    seed_name = "__SAGE_EDGE_SEED_v1__"

    # Check if seed already written (search for the seed episode name)
    try:
        existing = await g.search(
            query=seed_name,
            num_results=1,
        )
        if existing:
            log.info("Edge seed already present — skipping.")
            return
    except Exception:
        pass   # search failure is non-fatal; proceed with seed

    seed_text = """
SAGE knowledge graph edge-type seed episode (internal, do not display).

Supply chain entities and relationships present in this graph:

Saudi Aramco (Supplier) EXPORTS_VIA the Strait of Hormuz (Corridor) at 6.5 mbpd.
The Strait of Hormuz (Corridor) FEEDS crude to Vadinar terminal (Port).
Vadinar terminal (Port) SUPPLIES crude to Jamnagar Refinery (Refinery).
Jamnagar Refinery (Refinery) is CONFIGURED_FOR Arab Medium grade (CrudeGrade)
  with compatibility 0.95 and yield_pct 85.
MT Destiny (Vessel) is SANCTIONED_BY OFAC (Authority) effective 2025-01-15.
NIOC (Supplier) is SANCTIONED_BY EU (Authority) effective 2022-03-01.
Saudi Aramco (Supplier) operates a BYPASS_ROUTE via Yanbu terminal (Port)
  with cost_premium 0.80 USD/bbl and added_days 3.5.
Jamnagar Refinery (Refinery) draws from Vadinar SPR Cavern (SPRCavern)
  — FEEDS_RESERVE relationship.
Current risk assessment — Strait of Hormuz (Corridor) RISK_STATE:
  score 0.62, band elevated, factor_ais 0.41, factor_gdelt 0.55,
  factor_price 0.30, factor_sanctions 0.00,
  rationale "AIS dark vessels + war-risk premium",
  model_version "weighted-sum-fallback".
This RISK_STATE edge AFFECTS_SCENARIO sandbox-00000001 (PendingScenario)
  with confidence 0.55.
""".strip()

    try:
        await g.add_episode(
            name=seed_name,
            episode_body=seed_text,
            source=EpisodeType.text,
            source_description="SAGE internal edge-type seed",
            reference_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
            entity_types=ENTITY_TYPES,
            edge_types=EDGE_TYPES,
            edge_type_map=EDGE_TYPE_MAP,
        )
        log.info("Edge seed episode written successfully.")
    except Exception as exc:
        log.warning("Edge seed write failed (non-fatal): %s", exc)


async def init() -> Graphiti:
    """
    Build + bootstrap the shared Graphiti instance.
    Call once at container startup.
    """
    global _graphiti_instance
    if _graphiti_instance is not None:
        return _graphiti_instance
    g = build_graphiti()
    await bootstrap(g)
    _graphiti_instance = g
    return g


def _get_graphiti() -> Graphiti:
    """
    Return the shared Graphiti instance.
    Raises RuntimeError if `init()` was never called.
    """
    if _graphiti_instance is None:
        raise RuntimeError(
            "Graphiti not initialised. Call `await knowledge.connection.init()` "
            "at container startup before using any knowledge API."
        )
    return _graphiti_instance
