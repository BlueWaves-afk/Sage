"""
C0 — Graphiti connection, bootstrap, and module-level singleton.

LLM_PROVIDER controls which LLM + embedder backend is used:
  stub    → no external calls; synthesis returns placeholder prose (local dev / CI)
  openai  → OpenAI GPT-4o-mini + text-embedding-3-small (OPENAI_API_KEY required)
  bedrock → AWS Bedrock Nova Pro + Titan Embeddings v2 (AWS_* credentials required)

Call `init()` once at container startup. After that, `_get_graphiti()` is safe
from any async context.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from graphiti_core import Graphiti
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.nodes import EpisodeType

log = logging.getLogger(__name__)

SCHEMA_VERSION = "1.0.0"
GRAPH_NAME     = "sage"   # FalkorDB multi-tenant graph. Must NEVER be None.

_graphiti_instance: Optional[Graphiti] = None


def build_graphiti() -> Graphiti:
    """
    Construct a connected Graphiti instance.
    Backend selected via LLM_PROVIDER env var: stub | openai | groq | bedrock
    """
    driver = FalkorDriver(
        host=os.environ.get("FALKORDB_HOST", "falkordb"),
        port=int(os.environ.get("FALKORDB_PORT", "6379")),
        username=os.environ.get("FALKORDB_USERNAME") or None,
        password=os.environ.get("FALKORDB_PASSWORD") or None,
        database=GRAPH_NAME,   # string graph name; falkor_db= takes a FalkorDB client object
    )

    provider = os.environ.get("LLM_PROVIDER", "stub").lower()
    log.info("Building Graphiti with LLM_PROVIDER=%s", provider)

    if provider == "bedrock":
        from knowledge.bedrock import nova_pro, titan_embedder
        from knowledge.stub_llm import StubCrossEncoder
        region = os.environ.get("AWS_REGION", "us-east-1")
        return Graphiti(
            graph_driver=driver,
            llm_client=nova_pro(region),
            embedder=titan_embedder(region),
            cross_encoder=StubCrossEncoder(),
        )

    if provider == "openai":
        from graphiti_core.llm_client.openai_client import OpenAIClient
        from graphiti_core.llm_client.config import LLMConfig
        from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        return Graphiti(
            graph_driver=driver,
            llm_client=OpenAIClient(config=LLMConfig(model=model)),
            embedder=OpenAIEmbedder(config=OpenAIEmbedderConfig(
                model="text-embedding-3-small",
            )),
        )

    # stub — no LLM calls; synthesis falls back to placeholder prose
    from knowledge.stub_llm import StubLLMClient, StubEmbedder, StubCrossEncoder
    return Graphiti(
        graph_driver=driver,
        llm_client=StubLLMClient(),
        embedder=StubEmbedder(),
        cross_encoder=StubCrossEncoder(),
    )


async def bootstrap(g: Graphiti) -> None:
    """
    Idempotent startup: build FalkorDB indices + seed edge types.
    Safe to call on every boot.
    """
    from knowledge.schema.edges import EDGE_TYPE_MAP, EDGE_TYPES
    from knowledge.schema.entities import ENTITY_TYPES

    log.info("Building FalkorDB indices and constraints…")
    await g.build_indices_and_constraints()
    # NOTE: _seed_edge_types() (placeholder SeedX entities) is intentionally NOT called.
    # The context bundle's structural episodes exercise every custom edge type with real
    # data, so the seed is redundant — and its SeedX placeholders leaked into reads
    # (e.g. a phantom SeedReserveX SPRCavern polluting get_spr_state). Left for reference.
    log.info("Knowledge base bootstrap complete.")


async def _seed_edge_types(g, ENTITY_TYPES, EDGE_TYPES, EDGE_TYPE_MAP) -> None:
    """
    Write one synthetic episode that exercises every custom edge type.
    Mitigates graphiti issue #1111 (custom edge attributes missing on first appearance).
    Skips if seed already present.
    """
    seed_name = "__SAGE_EDGE_SEED_v1__"
    try:
        existing = await g.search(query=seed_name, num_results=1)
        if existing:
            log.info("Edge seed already present — skipping.")
            return
    except Exception:
        pass

    # Uses synthetic placeholder entities (not real tracked ones) so it registers
    # every custom edge type's attributes without polluting real-entity facts. The
    # real values come from the context bundle (data/<bundle>.context).
    seed_text = """
SAGE knowledge graph edge-type seed episode (internal placeholders only).
SeedSupplierX (Supplier) EXPORTS_VIA SeedCorridorX (Corridor) at volume_mbpd 1.0.
SeedCorridorX (Corridor) FEEDS SeedPortX (Port) with throughput_share_pct 0.50.
SeedPortX (Port) SUPPLIES SeedRefineryX (Refinery) with throughput_share_pct 0.50.
SeedRefineryX (Refinery) CONFIGURED_FOR SeedGradeX (CrudeGrade) compatibility 0.50 yield_pct 50.
SeedVesselX (Vessel) SANCTIONED_BY SeedAuthorityX (Authority) effective 2025-01-01.
SeedSupplierX (Supplier) BYPASS_ROUTE via SeedPortX (Port) cost_premium 1.0 added_days 1.0.
SeedRefineryX (Refinery) FEEDS_RESERVE SeedReserveX (SPRCavern).
SeedCorridorX RISK_STATE: score 0.50, band watch, factor_ais 0.0,
  factor_gdelt 0.0, factor_price 0.0, factor_sanctions 0.0.
RISK_STATE AFFECTS_SCENARIO seed-scenario-0 (PendingScenario) confidence 0.50.
""".strip()

    try:
        await g.add_episode(
            name=seed_name,
            episode_body=seed_text,
            source=EpisodeType.text,
            source_description="SAGE internal seed",
            reference_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
            entity_types=ENTITY_TYPES,
            edge_types=EDGE_TYPES,
            edge_type_map=EDGE_TYPE_MAP,
        )
        log.info("Edge seed written.")
    except Exception as exc:
        log.warning("Edge seed write failed (non-fatal): %s", exc)


async def init() -> Graphiti:
    """Build + bootstrap the shared Graphiti instance. Call once at startup."""
    global _graphiti_instance
    if _graphiti_instance is not None:
        return _graphiti_instance
    g = build_graphiti()
    await bootstrap(g)
    _graphiti_instance = g
    return g


def _get_graphiti() -> Graphiti:
    if _graphiti_instance is None:
        raise RuntimeError(
            "Graphiti not initialised. Call `await knowledge.connection.init()` at startup."
        )
    return _graphiti_instance
