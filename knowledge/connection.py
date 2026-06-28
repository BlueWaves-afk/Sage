"""
C0 — Graphiti connection and bootstrap.

Single function to build a connected Graphiti instance against FalkorDB.
Call bootstrap() once at container startup — it is idempotent.
"""
from __future__ import annotations

import os

from graphiti_core import Graphiti
from graphiti_core.driver.falkordb_driver import FalkorDriver

SCHEMA_VERSION = "1.0.0"
GRAPH_NAME = "sage"   # FalkorDB multi-tenant graph name. Must NEVER be None.


def build_graphiti() -> Graphiti:
    """
    Construct a connected Graphiti instance.
    LLM + embedder clients (Bedrock Nova) are configured here.
    """
    driver = FalkorDriver(
        host=os.environ.get("FALKORDB_HOST", "falkordb"),
        port=int(os.environ.get("FALKORDB_PORT", "6379")),
        username=os.environ.get("FALKORDB_USERNAME") or None,
        password=os.environ.get("FALKORDB_PASSWORD"),
        database=GRAPH_NAME,
    )
    # TODO: attach Bedrock Nova LLM client + Titan embedder client
    return Graphiti(graph_driver=driver)


async def bootstrap(g: Graphiti) -> None:
    """
    Build FalkorDB indices and constraints. Idempotent — safe to call on every boot.
    Also runs a seed episode to prime custom edge-type extraction (avoids issue #1111).
    """
    await g.build_indices_and_constraints()
    # TODO: call _seed_edge_types(g) once real schema is wired
