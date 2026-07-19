"""
C0 — Graphiti connection, bootstrap, and module-level singleton.

LLM_PROVIDER controls which LLM + embedder backend is used:
  stub    → no external calls; synthesis returns placeholder prose (local dev / CI)
  openai  → OpenAI GPT-4o-mini + text-embedding-3-small (OPENAI_API_KEY required)
  bedrock → AWS Bedrock Nova (Lite) + Titan Embeddings v2 (AWS_* credentials required)
  gemini  → Google Gemini Flash + text-embedding-004, free tier (GOOGLE_API_KEY required)

NOTE: switching the embedder (e.g. bedrock→gemini) changes the embedding dimension
(Titan v2 = 1024-d, text-embedding-004 = 768-d). Existing node embeddings and the
FalkorDB vector index are dimension-specific, so a provider switch requires wiping
and re-seeding the graph (reload the context bundle) — mixed dimensions break
semantic search.

Call `init()` once at container startup. After that, `_get_graphiti()` is safe
from any async context.
"""
from __future__ import annotations

import inspect
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
        from knowledge.bedrock import nova_lite, titan_embedder
        from knowledge.stub_llm import StubCrossEncoder
        region = os.environ.get("AWS_REGION", "us-east-1")
        # Graphiti's internal client runs entity/edge extraction, dedup, and node
        # summarization on EVERY add_episode — machine-internal, schema-constrained
        # work whose output no user ever reads. Use Nova Lite here (~13x cheaper than
        # Pro). User-facing wiki prose synthesis uses its own dedicated Nova Pro
        # client (knowledge/synthesis.py), so feed quality is unaffected.
        return Graphiti(
            graph_driver=driver,
            llm_client=nova_lite(region),
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

    if provider == "gemini":
        # Free-tier Google Gemini backend (no AWS dependency). Gemini Flash handles
        # both Graphiti's internal extraction AND the user-facing wiki synthesis
        # (synthesis.py falls back to this shared client for non-bedrock providers).
        # Embeddings via text-embedding-004. Requires GOOGLE_API_KEY (or GEMINI_API_KEY)
        # and the google-genai SDK (graphiti-core[google-genai]).
        from graphiti_core.llm_client.gemini_client import GeminiClient
        from graphiti_core.llm_client.config import LLMConfig
        from graphiti_core.embedder.gemini import GeminiEmbedder, GeminiEmbedderConfig
        from knowledge.stub_llm import StubCrossEncoder
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "LLM_PROVIDER=gemini requires GOOGLE_API_KEY (or GEMINI_API_KEY). "
                "Get a free key at https://aistudio.google.com/apikey and set it in .env.local."
            )
        # Flash is the free-tier workhorse; flash-lite ("small") for lightweight
        # extraction sub-calls. Both are on the free tier.
        model       = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
        small_model = os.environ.get("GEMINI_SMALL_MODEL", "gemini-2.0-flash-lite")
        # gemini-embedding-001 is the current embedding model (text-embedding-004 is
        # not served for newer API keys). NOTE: it is exposed on the v1 endpoint, not
        # v1beta — if GeminiEmbedder 404s, set the SDK api_version to v1.
        embed_model = os.environ.get("GEMINI_EMBED_MODEL", "gemini-embedding-001")
        return Graphiti(
            graph_driver=driver,
            llm_client=GeminiClient(config=LLMConfig(
                api_key=api_key, model=model, small_model=small_model, temperature=0.0,
            )),
            embedder=GeminiEmbedder(config=GeminiEmbedderConfig(
                api_key=api_key, embedding_model=embed_model,
            )),
            cross_encoder=StubCrossEncoder(),
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

    # FalkorDB's default per-query timeout (1000ms) is too tight for the 2-hop
    # subgraph traversals System 2/copilot run (get_subgraph, _graph_ppr_query) once
    # the graph has a few hundred edges — those queries were observed timing out
    # under normal load, silently degrading to an empty subgraph (get_subgraph
    # swallows Cypher errors and returns []). Set here (not just via docker-compose)
    # so it's enforced on every boot regardless of deployment environment.
    try:
        client = g.driver.client
        config_set = client.config_set
        result = config_set("TIMEOUT", 10000)
        if inspect.isawaitable(result):
            await result
        log.info("FalkorDB query timeout set to 10000ms.")
    except Exception as exc:
        log.warning("Could not set FalkorDB TIMEOUT config (non-fatal): %s", exc)
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
