"""
AWS Bedrock wrappers implementing Graphiti's LLMClient and EmbedderClient interfaces.

Verified against graphiti-core 0.29.2:
  LLMClient abstract method: _generate_response(messages, response_model, max_tokens, model_size) -> dict
  EmbedderClient abstract method: create(input_data) -> list[float]

Why custom wrappers (not OpenAI-compatible endpoint):
  Bedrock Nova (Nova Micro/Lite/Pro) is NOT on Bedrock's OpenAI-compatible endpoint.
  Only Claude 3.x/4.x models appear there. Nova models require the native converse() API.

Model routing:
  ModelSize.medium (synthesis, policy memos)  → Nova Pro   (~$0.80/$3.20 per 1M in/out)
  ModelSize.small  (entity extraction, triage) → Nova Micro (~$0.035/$0.14 per 1M in/out)

Throttling:
  "Too many requests"      → per-second rate limit; retried with exponential backoff,
                             then re-raised as openai.RateLimitError so Graphiti's own
                             tenacity wrapper also retries at the outer level.
  "Too many tokens per day" → daily quota; fail fast (no retries), raise RateLimitError
                              immediately so callers surface the error cleanly.

Structured output:
  Graphiti serialises the response_model JSON schema and injects it into the prompt.
  The _generate_response return is a dict with key "content" containing the raw text.
  Graphiti's generate_response() then parses the content against the schema.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import time
from typing import Any, Optional

import boto3
import httpx
from openai import RateLimitError
from graphiti_core.llm_client.errors import EmptyResponseError
from pydantic import BaseModel

from graphiti_core.llm_client.client import LLMClient
from graphiti_core.llm_client.config import LLMConfig, ModelSize
from graphiti_core.prompts.models import Message
from graphiti_core.embedder.client import EmbedderClient

log = logging.getLogger(__name__)

_AWS_REGION  = os.environ.get("AWS_REGION", "ap-south-1")
_NOVA_PRO    = "amazon.nova-pro-v1:0"
_NOVA_LITE   = "amazon.nova-lite-v1:0"
_NOVA_MICRO  = "amazon.nova-micro-v1:0"
_TITAN_EMBED = "amazon.titan-embed-text-v2:0"
_EMBED_DIM   = 1024

_DAILY_QUOTA_PHRASE = "too many tokens per day"
_RATE_LIMIT_RETRIES = 5

_TOOL_NAME = "record_result"


def _is_daily_quota(exc: Exception) -> bool:
    return _DAILY_QUOTA_PHRASE in str(exc).lower()


def _rate_limit_error(message: str) -> RateLimitError:
    """
    Build an openai.RateLimitError from a Bedrock ThrottlingException.
    openai's APIStatusError.__init__ dereferences response.request/.status_code/
    .headers — passing response=None crashes with AttributeError instead of
    surfacing the real throttling message. Construct a minimal real httpx.Response
    so the error reports cleanly to callers (and Graphiti's tenacity wrapper).
    """
    fake_response = httpx.Response(
        status_code=429,
        request=httpx.Request("POST", "https://bedrock-runtime.amazonaws.com"),
    )
    return RateLimitError(message=message, response=fake_response, body=None)


# ---------------------------------------------------------------------------
# Graphiti LLMClient
# ---------------------------------------------------------------------------

class BedrockLLMClient(LLMClient):
    """
    Graphiti-compatible LLM client backed by AWS Bedrock Nova via converse() API.

    ModelSize.medium → Nova Pro  (synthesis, wiki updates, policy memos)
    ModelSize.small  → Nova Micro (entity/edge extraction inside add_episode)

    Graphiti calls _generate_response() and expects a dict with "content" key
    containing the raw LLM text (which it then parses for structured output).
    """

    def __init__(
        self,
        model_id: str = _NOVA_PRO,
        small_model_id: str = _NOVA_LITE,
        region: str = _AWS_REGION,
        temperature: float = 0.0,
        max_tokens: int = 8192,
    ) -> None:
        super().__init__(
            config=LLMConfig(
                model=model_id,
                small_model=small_model_id,
                temperature=temperature,
                max_tokens=max_tokens,
            ),
            cache=False,
        )
        self._region      = region
        self._bedrock     = boto3.client("bedrock-runtime", region_name=region)

    async def _generate_response(
        self,
        messages: list[Message],
        response_model: type[BaseModel] | None = None,
        max_tokens: int = 8192,
        model_size: ModelSize = ModelSize.medium,
    ) -> dict[str, Any]:
        """
        Core interface method called by Graphiti's generate_response().
        Routes small model_size (entity extraction) to Nova Micro to save quota.

        When response_model is set, Graphiti has injected a JSON schema into the
        prompt and expects the PARSED structured dict back (e.g. {"extracted_entities": [...]}),
        not text wrapped in a "content" key. Nova often wraps JSON in a ```json fence,
        so strip fences before parsing. When response_model is None (synthesis,
        copilot), return {"content": text} for the convenience generate() path.
        """
        model_id = self.small_model if model_size == ModelSize.small else self.model
        bedrock_messages, system_blocks = _convert_messages(messages)
        n_tokens = min(max_tokens, self.max_tokens)

        if response_model is None:
            text = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._call_converse(bedrock_messages, system_blocks, n_tokens, model_id),
            )
            return {"content": text, "input_tokens": 0, "output_tokens": 0}

        # Structured output via native tool use: define the response_model schema
        # as a forced tool so Nova returns a schema-validated `input` object rather
        # than echoing the schema as text. This is far more reliable than parsing
        # JSON out of free text.
        tool_schema = _sanitize_schema(response_model.model_json_schema())
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._call_converse_tool(
                bedrock_messages, system_blocks, n_tokens, model_id, tool_schema
            ),
        )
        if result is None:
            raise EmptyResponseError("Bedrock tool-use returned no structured input")
        return result

    def _call_converse_tool(
        self,
        messages: list[dict],
        system: list[dict],
        max_tokens: int,
        model_id: str,
        tool_schema: dict,
    ) -> Optional[dict]:
        """Force structured output through a single tool and return its input dict."""
        kwargs: dict[str, Any] = {
            "modelId": model_id,
            "messages": messages,
            "inferenceConfig": {"maxTokens": max_tokens, "temperature": self.temperature},
            "toolConfig": {
                "tools": [{
                    "toolSpec": {
                        "name": _TOOL_NAME,
                        "description": "Return the extraction result as structured data.",
                        "inputSchema": {"json": tool_schema},
                    }
                }],
                "toolChoice": {"any": {}},
            },
        }
        if system:
            kwargs["system"] = system

        for attempt in range(_RATE_LIMIT_RETRIES + 1):
            try:
                response = self._bedrock.converse(**kwargs)
                for block in response["output"]["message"]["content"]:
                    tu = block.get("toolUse")
                    if tu and isinstance(tu.get("input"), dict):
                        return tu["input"]
                return None
            except self._bedrock.exceptions.ThrottlingException as exc:
                if _is_daily_quota(exc) or attempt == _RATE_LIMIT_RETRIES:
                    raise _rate_limit_error(str(exc)) from exc  # type: ignore[arg-type]
                wait = (2 ** attempt) + random.uniform(0, 1)
                log.warning("Bedrock tool converse throttled [%s], retry in %.1fs (%d/%d)",
                            model_id, wait, attempt + 1, _RATE_LIMIT_RETRIES)
                time.sleep(wait)
        raise RuntimeError("Unreachable")

    def _call_converse(
        self,
        messages: list[dict],
        system: list[dict],
        max_tokens: int,
        model_id: str,
    ) -> str:
        kwargs: dict[str, Any] = {
            "modelId": model_id,
            "messages": messages,
            "inferenceConfig": {
                "maxTokens": max_tokens,
                "temperature": self.temperature,
            },
        }
        if system:
            kwargs["system"] = system

        for attempt in range(_RATE_LIMIT_RETRIES + 1):
            try:
                response = self._bedrock.converse(**kwargs)
                content  = response["output"]["message"]["content"]
                for block in content:
                    text = block.get("text", "")
                    if text:
                        return text
                return ""
            except self._bedrock.exceptions.ThrottlingException as exc:
                if _is_daily_quota(exc):
                    log.error("Bedrock daily token quota exhausted (%s)", model_id)
                    raise _rate_limit_error(str(exc)) from exc
                if attempt == _RATE_LIMIT_RETRIES:
                    log.error("Bedrock converse exhausted retries (%s)", model_id)
                    raise _rate_limit_error(str(exc)) from exc
                wait = (2 ** attempt) + random.uniform(0, 1)
                log.warning(
                    "Bedrock converse throttled [%s], retrying in %.1fs (attempt %d/%d)",
                    model_id, wait, attempt + 1, _RATE_LIMIT_RETRIES,
                )
                time.sleep(wait)

        raise RuntimeError("Unreachable")

    # Convenience: non-Graphiti callers (synthesis.py) use this
    async def generate(
        self,
        messages: list[dict[str, Any]],
        response_model: type[BaseModel] | None = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> str:
        """Non-Graphiti interface for synthesis.py and copilot_query()."""
        graphiti_messages = [
            Message(role=m.get("role", "user"), content=m.get("content", ""))
            for m in messages
        ]
        result = await self._generate_response(
            graphiti_messages,
            response_model=response_model,
            max_tokens=max_tokens or self.max_tokens,
            model_size=ModelSize.medium,  # synthesis always uses the large model
        )
        return result.get("content", "")


# ---------------------------------------------------------------------------
# Graphiti EmbedderClient
# ---------------------------------------------------------------------------

class BedrockEmbedder(EmbedderClient):
    """
    Graphiti-compatible embedder using Amazon Titan Text Embeddings v2.
    Produces 1024-dimensional L2-normalised vectors.
    """

    def __init__(
        self,
        model_id: str = _TITAN_EMBED,
        region: str = _AWS_REGION,
        embedding_dim: int = _EMBED_DIM,
    ) -> None:
        self.model_id      = model_id
        self.embedding_dim = embedding_dim
        self._bedrock      = boto3.client("bedrock-runtime", region_name=region)

    async def create(self, input_data: str | list[str] | Any) -> list[float]:
        """
        Graphiti abstract interface. Called for node/edge embedding.
        When input_data is a list, embeds the first element (Graphiti batching
        is handled at a higher level via embed_batch()).
        """
        if isinstance(input_data, list):
            text = input_data[0] if input_data else ""
        else:
            text = str(input_data)

        return await asyncio.get_event_loop().run_in_executor(
            None, lambda: self._embed_sync(text)
        )

    async def create_batch(self, input_data_list: list[str]) -> list[list[float]]:
        """
        Graphiti batch interface. Titan's invoke_model is single-input, so we
        embed each text sequentially (retry/backoff handled per call). Called
        by Graphiti when embedding extracted edge facts and entity names.
        """
        results: list[list[float]] = []
        for text in input_data_list:
            results.append(await self.create(text))
        return results

    async def embed(self, text: str) -> list[float]:
        """Convenience method for non-Graphiti callers (triage.py)."""
        return await self.create(text)

    def _embed_sync(self, text: str) -> list[float]:
        body = json.dumps({
            "inputText": text[:8192],
            "dimensions": self.embedding_dim,
            "normalize": True,
        })
        for attempt in range(_RATE_LIMIT_RETRIES + 1):
            try:
                response = self._bedrock.invoke_model(
                    modelId=self.model_id,
                    body=body,
                    contentType="application/json",
                    accept="application/json",
                )
                return json.loads(response["body"].read())["embedding"]
            except self._bedrock.exceptions.ThrottlingException as exc:
                if _is_daily_quota(exc):
                    log.error("Bedrock embed daily quota exhausted")
                    raise _rate_limit_error(str(exc)) from exc
                if attempt == _RATE_LIMIT_RETRIES:
                    log.error("Bedrock embed exhausted retries")
                    raise _rate_limit_error(str(exc)) from exc
                wait = (2 ** attempt) + random.uniform(0, 1)
                log.warning(
                    "Bedrock embed throttled, retrying in %.1fs (attempt %d/%d)",
                    wait, attempt + 1, _RATE_LIMIT_RETRIES,
                )
                time.sleep(wait)

        raise RuntimeError("Unreachable")


# ---------------------------------------------------------------------------
# Message conversion
# ---------------------------------------------------------------------------

def _strip_code_fences(text: str) -> str:
    """Strip a leading ```json / ``` fence and trailing ``` from model output."""
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1] if "\n" in s else s[3:]
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
    return s.strip()


def _extract_json_object(
    text: str, required_keys: Optional[set[str]] = None
) -> Optional[dict]:
    """Extract the JSON object that matches the expected response shape.

    Nova frequently echoes the injected JSON *schema* (an object with $defs /
    properties / required) before or instead of the actual answer, sometimes as
    a separate object, sometimes merged. Taking the first '{' would pick the
    schema and miss the data. So we scan every top-level JSON object and, when
    the caller tells us which keys the real answer must have, return the first
    object containing all of them — falling back to the first parsed object.
    """
    s = _strip_code_fences(text)
    decoder = json.JSONDecoder()
    candidates: list[dict] = []
    i, n = 0, len(s)
    while i < n:
        if s[i] == "{":
            try:
                obj, end = decoder.raw_decode(s[i:])
                if isinstance(obj, dict):
                    candidates.append(obj)
                i += end
                continue
            except json.JSONDecodeError:
                pass
        i += 1

    # Drop schema echoes — they are never the real answer.
    data = [obj for obj in candidates if not _looks_like_schema(obj)]

    if not data:
        log.error("Bedrock structured output had no data object: %.300s", text)
        return None

    if required_keys:
        for obj in data:
            if required_keys.issubset(obj.keys()):
                return obj
    return data[0]


def _sanitize_schema(schema: dict) -> dict:
    """Inline $defs/$ref so Nova's tool-use input schema is self-contained.

    Pydantic emits $ref/$defs for nested models; Bedrock tool schemas are most
    reliable when references are resolved inline. We do a best-effort inline pass
    and drop leftover $defs. Falls back to the original schema on any error.
    """
    try:
        defs = schema.get("$defs", {})

        def _resolve(node: Any) -> Any:
            if isinstance(node, dict):
                if "$ref" in node and node["$ref"].startswith("#/$defs/"):
                    name = node["$ref"].split("/")[-1]
                    return _resolve(defs.get(name, {}))
                return {k: _resolve(v) for k, v in node.items() if k != "$defs"}
            if isinstance(node, list):
                return [_resolve(x) for x in node]
            return node

        return _resolve({k: v for k, v in schema.items() if k != "$defs"})
    except Exception:
        return schema


def _looks_like_schema(obj: dict) -> bool:
    """True if the object is an echoed JSON schema rather than a data instance."""
    if "$defs" in obj or "$schema" in obj:
        return True
    # A bare schema is {"type": "object", "properties": {...}, "required": [...]}
    return obj.get("type") == "object" and "properties" in obj


def _convert_messages(
    messages: list[Message],
) -> tuple[list[dict], list[dict]]:
    """
    Convert Graphiti Message objects to Bedrock converse format.
    System messages are pulled out into a separate `system` list.
    """
    bedrock_messages: list[dict] = []
    system_blocks:    list[dict] = []

    for msg in messages:
        role    = msg.role
        content = msg.content if isinstance(msg.content, str) else str(msg.content)

        if role == "system":
            system_blocks.append({"text": content})
        else:
            bedrock_role = "assistant" if role == "assistant" else "user"
            bedrock_messages.append({
                "role": bedrock_role,
                "content": [{"text": content}],
            })

    # Bedrock requires messages to start with "user"
    if bedrock_messages and bedrock_messages[0]["role"] == "assistant":
        bedrock_messages.insert(0, {"role": "user", "content": [{"text": "(context)"}]})

    # Bedrock requires non-empty messages list
    if not bedrock_messages:
        bedrock_messages.append({"role": "user", "content": [{"text": "(no message)"}]})

    return bedrock_messages, system_blocks


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------

def nova_pro(region: str = _AWS_REGION) -> BedrockLLMClient:
    """Nova Pro (medium, synthesis) + Nova Micro (small, extraction) dual-model client.

    Historical note: Micro once echoed the JSON schema instead of producing data on
    the old prompt-injection structured-output path. The current tool-use path
    (`_call_converse_tool`, forced toolChoice) fixed that — Micro now emits valid
    structured output reliably. Empirically re-tested 2026-07 on representative
    energy-news extraction: Micro's entity/relationship recall is comparable to (and
    on dense text sometimes better than) Lite, at ~1.7x lower token cost. Synthesis
    (wiki prose, memos) still routes to Nova Pro via ModelSize.medium and is
    unaffected by this choice.
    """
    return BedrockLLMClient(
        model_id=_NOVA_PRO,
        small_model_id=_NOVA_MICRO,
        region=region,
        temperature=0.0,
    )


def nova_micro(region: str = _AWS_REGION) -> BedrockLLMClient:
    """Nova Micro only — both model sizes route to Micro. Used in tests."""
    return BedrockLLMClient(
        model_id=_NOVA_MICRO,
        small_model_id=_NOVA_MICRO,
        region=region,
        temperature=0.0,
        max_tokens=2048,
    )


def titan_embedder(region: str = _AWS_REGION) -> BedrockEmbedder:
    """Titan Text Embeddings v2 — 1024-dim vectors."""
    return BedrockEmbedder(region=region)
