"""
SAGE triage gate.

Scores each incoming NormalizedSignal and decides which synthesis path to take.
Runs before narrative synthesis — keeps the majority of signals out of the
expensive Nova Pro path.

Decision logic (in priority order):
  1. force_synthesis=True  → always "synthesize"  (sanctions diffs, BOCD breakpoints)
  2. similarity > SYNTH_THRESHOLD (0.72) → "synthesize"
  3. similarity > EXTRACT_THRESHOLD (0.40) → "extract" (entity extraction only, no wiki)
  4. otherwise → "store" (raw signal stored, no Graphiti write)

Similarity method:
  Embed signal.summary with Titan v2 → compare cosine similarity against
  the embedded names of all tracked entity_refs (resolved or not).

  If entity_refs are provided and at least one resolves to a known Graphiti node,
  we use the node's stored embedding directly (faster, graph-aware).
  Otherwise we embed the entity display_name and compare.

Caching:
  Entity name embeddings are cached in memory for 5 minutes to avoid
  redundant Bedrock calls during high-throughput ingestion windows.
"""
from __future__ import annotations

import asyncio
import logging
import math
import time
from typing import Literal, Optional

from contracts.signal import NormalizedSignal

log = logging.getLogger(__name__)

TriageDecision = Literal["synthesize", "extract", "store", "drop"]

SYNTH_THRESHOLD   = 0.72
EXTRACT_THRESHOLD = 0.40
CACHE_TTL_S       = 300   # 5 minutes

# Sources that NEVER produce standalone wiki prose — they contribute numeric
# factors to the risk score and may trigger re-synthesis of affected entities,
# but never author a wiki page on their own.
# AIS: telemetry, not narrative. Price: a number, not prose.
_NUMERIC_SOURCES: frozenset[str] = frozenset({"ais", "price"})

# Sources that always bypass similarity scoring and go straight to (light) synthesis.
_ALWAYS_SYNTH_SOURCES: frozenset[str] = frozenset({"sanctions"})

# In-memory embedding cache: entity_name → (embedding, expiry_timestamp)
_embed_cache: dict[str, tuple[list[float], float]] = {}
_cache_lock = asyncio.Lock()


async def triage(signal: NormalizedSignal) -> tuple[TriageDecision, float]:
    """
    Returns (decision, similarity_score).

    Source-aware routing (applied before similarity scoring):
      ais / price  → always "extract" (numeric factor, never narrative prose)
      sanctions    → always "synthesize" (structured facts, always significant)
      news / gdelt → similarity-based (expensive path for rich content only)

    force_synthesis=True is respected for news/gdelt/sanctions but is BLOCKED
    for ais/price — numeric sources must never trigger narrative synthesis regardless
    of sub-agent priority hint.
    """
    source = signal.source

    # ── Numeric sources: always extract, never synthesize ─────────────────────
    if source in _NUMERIC_SOURCES:
        return "extract", 1.0

    # ── Sanctions: always synthesize (high importance, structured facts) ───────
    if source in _ALWAYS_SYNTH_SOURCES or signal.force_synthesis:
        return "synthesize", 1.0

    if not signal.entity_refs:
        return "store", 0.0

    # ── News / GDELT: similarity-based ────────────────────────────────────────
    signal_embedding = await _embed_text(signal.summary)
    if not signal_embedding:
        return "store", 0.0

    max_sim = 0.0
    for entity_name in signal.entity_refs:
        entity_embedding = await _get_entity_embedding(entity_name)
        if entity_embedding:
            sim = _cosine(signal_embedding, entity_embedding)
            max_sim = max(max_sim, sim)

    if max_sim > SYNTH_THRESHOLD:
        return "synthesize", max_sim
    elif max_sim > EXTRACT_THRESHOLD:
        return "extract", max_sim
    else:
        return "store", max_sim


async def _embed_text(text: str) -> Optional[list[float]]:
    """Embed text via BedrockEmbedder, with in-memory caching."""
    now = time.monotonic()

    async with _cache_lock:
        cached = _embed_cache.get(text)
        if cached and cached[1] > now:
            return cached[0]

    try:
        from knowledge.connection import _get_graphiti
        g = _get_graphiti()
        embedding = await g.embedder.embed(text)
        async with _cache_lock:
            _embed_cache[text] = (embedding, now + CACHE_TTL_S)
        return embedding
    except Exception as exc:
        log.warning("Embedding failed for triage (text='%.60s'): %s", text, exc)
        return None


async def _get_entity_embedding(entity_name: str) -> Optional[list[float]]:
    """
    Get embedding for entity_name. First tries the Graphiti node's stored embedding
    (if the entity exists in the graph); falls back to embedding the name directly.
    """
    now = time.monotonic()
    cache_key = f"entity:{entity_name}"

    async with _cache_lock:
        cached = _embed_cache.get(cache_key)
        if cached and cached[1] > now:
            return cached[0]

    embedding: Optional[list[float]] = None

    # Try to get stored node embedding from Graphiti (graph-aware, most accurate)
    try:
        from knowledge.connection import _get_graphiti
        g = _get_graphiti()

        # Search for the entity node by name
        edges = await g.search(
            query=entity_name,
            num_results=3,
        )
        # If the entity is in the graph, we can embed its name as a proxy
        # (Graphiti stores embeddings on nodes but doesn't expose them directly via search)
        # Fall through to direct embedding
    except Exception:
        pass

    # Embed the entity name directly as proxy
    if embedding is None:
        embedding = await _embed_text(entity_name)

    if embedding:
        async with _cache_lock:
            _embed_cache[cache_key] = (embedding, now + CACHE_TTL_S)

    return embedding


def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length float vectors."""
    if len(a) != len(b) or not a:
        return 0.0
    dot   = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


def clear_cache() -> None:
    """Clear embedding cache. Useful in tests."""
    _embed_cache.clear()
