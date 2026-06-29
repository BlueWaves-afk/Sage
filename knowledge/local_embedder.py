"""
Local sentence-transformers embedder — no API key required.

Uses all-MiniLM-L6-v2 (80 MB, 384-dim) by default. The model is downloaded
once to /app/.cache/huggingface on first use and cached in the Docker volume.

Used with LLM_PROVIDER=groq (Groq has no embeddings endpoint) and for
fully offline local development.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from graphiti_core.embedder.client import EmbedderClient

log = logging.getLogger(__name__)

_MODEL_NAME = os.environ.get("LOCAL_EMBED_MODEL", "all-MiniLM-L6-v2")
_model = None


def _get_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            log.info("Loading local embedding model: %s", _MODEL_NAME)
            _model = SentenceTransformer(_MODEL_NAME)
            log.info("Local embedding model loaded (dim=%d)", _model.get_sentence_embedding_dimension())
        except ImportError:
            raise RuntimeError(
                "sentence-transformers is not installed. "
                "Run: pip install sentence-transformers"
            )
    return _model


class LocalEmbedder(EmbedderClient):
    """
    Wraps sentence-transformers for use as a Graphiti EmbedderClient.
    Runs entirely locally — no API calls, no rate limits, no cost.

    Embedding dimension: 384 (all-MiniLM-L6-v2 default).
    Override with LOCAL_EMBED_MODEL env var for a larger model.
    """

    async def create(self, input_data: str | list[str] | Any) -> list[float]:
        if isinstance(input_data, list):
            text = input_data[0] if input_data else ""
        else:
            text = str(input_data)
        return self._embed(text)

    async def embed(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        model = _get_model()
        vec = model.encode(text, normalize_embeddings=True)
        return vec.tolist()
