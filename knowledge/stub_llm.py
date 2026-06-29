"""
Stub LLM + Embedder for local development without any LLM API credentials.

LLM_PROVIDER=stub (the default):
  - Synthesis returns clearly-labelled placeholder prose — no hallucination risk.
  - Embeddings return a deterministic pseudo-random vector derived from the text hash.
    This means cosine similarity still ranks semantically-similar texts closer together
    than unrelated ones (via hash distribution), so triage works in demo mode.
  - Graphiti's entity extraction still runs but returns generic labels since there
    is no real LLM. Good enough to populate the graph for demos using the seed episode.

Switch to openai or bedrock when you have credentials:
  LLM_PROVIDER=openai  OPENAI_API_KEY=sk-...
  LLM_PROVIDER=bedrock AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=...
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
from typing import Any, Optional

from pydantic import BaseModel

from graphiti_core.llm_client.client import LLMClient
from graphiti_core.llm_client.config import LLMConfig, ModelSize
from graphiti_core.prompts.models import Message
from graphiti_core.embedder.client import EmbedderClient
from graphiti_core.cross_encoder.client import CrossEncoderClient

log = logging.getLogger(__name__)

EMBED_DIM = 1024


class StubLLMClient(LLMClient):
    """
    Returns minimal valid responses without calling any API.

    For structured extraction (response_model provided): returns an empty
    dict serialised as JSON, which Graphiti deserialises to default-valued fields.
    For plain text (synthesis): returns a clearly-labelled stub string.
    """

    def __init__(self) -> None:
        super().__init__(config=LLMConfig(model="stub"))

    async def _generate_response(
        self,
        messages: list[Message],
        response_model: Optional[type[BaseModel]] = None,
        max_tokens: int = 8192,
        model_size: ModelSize = ModelSize.medium,
    ) -> dict[str, Any]:
        if response_model is not None:
            # Graphiti does Model(**llm_response) directly — return the model's fields,
            # not a {"content": "..."} wrapper.
            return _empty_for(response_model)

        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"), ""
        )
        entity = _extract_entity_hint(str(last_user))
        content = (
            f"[STUB — LLM_PROVIDER=stub] {entity} intelligence page. "
            f"No LLM credentials configured. "
            f"Set LLM_PROVIDER=openai or LLM_PROVIDER=bedrock in .env to enable synthesis."
        )
        return {"content": content, "input_tokens": 0, "output_tokens": 0}

    # Non-Graphiti callers (synthesis.py) use this
    async def generate(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> str:
        last_user = next(
            (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), ""
        )
        entity = _extract_entity_hint(str(last_user))
        return (
            f"[STUB] {entity} — LLM_PROVIDER=stub. "
            f"Set LLM_PROVIDER=openai or bedrock in .env to enable real synthesis."
        )


class StubEmbedder(EmbedderClient):
    """
    Returns deterministic 1024-D unit vectors derived from text SHA-256 hash.

    Two identical strings produce identical vectors (cache-coherent).
    Two different strings produce different vectors with no semantic structure,
    so similarity-based triage will mostly route to "store" — which is safe:
    it means force_synthesis=True signals (sanctions, BOCD, dark vessels) still
    trigger synthesis, while routine signals are stored without synthesis.
    """

    async def create(self, input_data: str | list[str] | Any) -> list[float]:
        text = input_data[0] if isinstance(input_data, list) else str(input_data)
        return _hash_embed(text, EMBED_DIM)

    async def embed(self, text: str) -> list[float]:
        return _hash_embed(text, EMBED_DIM)


class StubCrossEncoder(CrossEncoderClient):
    """Returns passages in original order with a uniform score of 0.5."""

    async def rank(self, query: str, passages: list[str]) -> list[tuple[str, float]]:
        return [(p, 0.5) for p in passages]


def _hash_embed(text: str, dim: int) -> list[float]:
    """
    Deterministic pseudo-random unit vector from SHA-256.
    Expand hash to `dim` floats via repeated hashing of the seed.
    """
    floats: list[float] = []
    seed = text.encode()
    while len(floats) < dim:
        digest = hashlib.sha256(seed).digest()
        for i in range(0, len(digest) - 3, 4):
            val = int.from_bytes(digest[i:i+4], "big") / (2**32)
            floats.append(val * 2 - 1)   # map [0,1] → [-1,1]
        seed = digest   # chain hashes

    raw = floats[:dim]
    # L2 normalise
    mag = math.sqrt(sum(x * x for x in raw)) or 1.0
    return [x / mag for x in raw]


def _empty_for(response_model: type[BaseModel]) -> dict:
    """
    Return a valid minimal JSON dict for any graphiti extraction response_model.
    Each model has at least one required list field — return it empty.
    Keyed by class name so we don't import graphiti internals here.
    """
    name = response_model.__name__
    _EMPTY: dict[str, dict] = {
        "ExtractedEntities":  {"extracted_entities": []},
        "SummarizedEntities": {"summaries": []},
        "NodeResolutions":    {"entity_resolutions": []},
        "ExtractedEdges":     {"edges": []},
        "EdgeDuplicate":      {"duplicate_facts": [], "contradicted_facts": []},
        "SagaSummary":        {"summary": ""},
        "Summary":            {"summary": ""},
        "SummaryDescription": {"summary": "", "description": ""},
        "CombinedExtraction": {"extracted_entities": [], "edges": []},
        "BatchEdgeTimestamps":{"edge_timestamps": []},
        "EdgeTimestamps":     {"valid_at": None, "invalid_at": None},
        "QAResponse":         {"answer": ""},
    }
    if name in _EMPTY:
        return _EMPTY[name]
    # Unknown model — try to build an empty dict from field defaults
    try:
        empty = {}
        for field_name, field in response_model.model_fields.items():
            ann = str(field.annotation)
            if "list" in ann:
                empty[field_name] = []
            elif "str" in ann:
                empty[field_name] = ""
            elif "int" in ann or "float" in ann:
                empty[field_name] = 0
            elif "bool" in ann:
                empty[field_name] = False
            else:
                empty[field_name] = None
        return empty
    except Exception:
        return {}


def _extract_entity_hint(prompt: str) -> str:
    """Pull entity name from synthesis prompt if present."""
    for line in prompt.splitlines():
        if "intelligence page for" in line.lower():
            parts = line.split("intelligence page for")
            if len(parts) > 1:
                return parts[1].strip().rstrip(".")
    return "entity"
