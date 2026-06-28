"""
AWS Bedrock wrappers implementing Graphiti's LLMClient and EmbedderClient interfaces.

Verified against graphiti-core 0.29.2:
  LLMClient abstract method: _generate_response(messages, response_model, max_tokens, model_size) -> dict
  EmbedderClient abstract method: create(input_data) -> list[float]

Why custom wrappers (not OpenAI-compatible endpoint):
  Bedrock Nova (Nova Micro/Lite/Pro) is NOT on Bedrock's OpenAI-compatible endpoint.
  Only Claude 3.x/4.x models appear there. Nova models require the native converse() API.

Structured output:
  Graphiti serialises the response_model JSON schema and injects it into the prompt.
  The _generate_response return is a dict with key "content" containing the raw text.
  Graphiti's generate_response() then parses the content against the schema.
  We don't need tool_use — just return clean JSON-parseable text for structured calls.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Optional

import boto3
from pydantic import BaseModel

log = logging.getLogger(__name__)

_AWS_REGION  = os.environ.get("AWS_REGION", "ap-south-1")
_NOVA_PRO    = "amazon.nova-pro-v1:0"
_NOVA_MICRO  = "amazon.nova-micro-v1:0"
_TITAN_EMBED = "amazon.titan-embed-text-v2:0"
_EMBED_DIM   = 1024


# ---------------------------------------------------------------------------
# Graphiti LLMClient
# ---------------------------------------------------------------------------

from graphiti_core.llm_client.client import LLMClient
from graphiti_core.llm_client.config import LLMConfig, ModelSize
from graphiti_core.prompts.models import Message


class BedrockLLMClient(LLMClient):
    """
    Graphiti-compatible LLM client backed by AWS Bedrock Nova via converse() API.

    Graphiti calls _generate_response() and expects a dict with "content" key
    containing the raw LLM text (which it then parses for structured output).
    """

    def __init__(
        self,
        model_id: str = _NOVA_PRO,
        region: str = _AWS_REGION,
        temperature: float = 0.0,
        max_tokens: int = 8192,
    ) -> None:
        # LLMClient.__init__ may not exist as a proper __init__; set attributes directly
        self.model_id    = model_id
        self.temperature = temperature
        self.max_tokens  = max_tokens
        self._bedrock    = boto3.client("bedrock-runtime", region_name=region)

    async def _generate_response(
        self,
        messages: list[Message],
        response_model: type[BaseModel] | None = None,
        max_tokens: int = 8192,
        model_size: ModelSize = ModelSize.medium,
    ) -> dict[str, Any]:
        """
        Core interface method. Called by Graphiti's generate_response().
        Returns {"content": "<text>", "input_tokens": N, "output_tokens": M}.
        """
        bedrock_messages, system_blocks = _convert_messages(messages)
        n_tokens = min(max_tokens, self.max_tokens)

        text = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._call_converse(bedrock_messages, system_blocks, n_tokens),
        )
        return {"content": text, "input_tokens": 0, "output_tokens": 0}

    def _call_converse(
        self,
        messages: list[dict],
        system: list[dict],
        max_tokens: int,
    ) -> str:
        kwargs: dict[str, Any] = {
            "modelId": self.model_id,
            "messages": messages,
            "inferenceConfig": {
                "maxTokens": max_tokens,
                "temperature": self.temperature,
            },
        }
        if system:
            kwargs["system"] = system

        response = self._bedrock.converse(**kwargs)
        content  = response["output"]["message"]["content"]
        for block in content:
            text = block.get("text", "")
            if text:
                return text
        return ""

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
        )
        return result.get("content", "")


# ---------------------------------------------------------------------------
# Graphiti EmbedderClient
# ---------------------------------------------------------------------------

from graphiti_core.embedder.client import EmbedderClient


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

    # Convenience: non-Graphiti callers (triage.py) call this
    async def embed(self, text: str) -> list[float]:
        return await self.create(text)

    def _embed_sync(self, text: str) -> list[float]:
        body = json.dumps({
            "inputText": text[:8192],
            "dimensions": self.embedding_dim,
            "normalize": True,
        })
        response = self._bedrock.invoke_model(
            modelId=self.model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        return json.loads(response["body"].read())["embedding"]


# ---------------------------------------------------------------------------
# Message conversion
# ---------------------------------------------------------------------------

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
    """Nova Pro — synthesis, policy memos, copilot. ~$0.0008/1K tokens."""
    return BedrockLLMClient(model_id=_NOVA_PRO, region=region, temperature=0.0)


def nova_micro(region: str = _AWS_REGION) -> BedrockLLMClient:
    """Nova Micro — triage, simple extraction. ~$0.000035/1K tokens."""
    return BedrockLLMClient(model_id=_NOVA_MICRO, region=region, temperature=0.0, max_tokens=2048)


def titan_embedder(region: str = _AWS_REGION) -> BedrockEmbedder:
    """Titan Text Embeddings v2 — 1024-dim vectors."""
    return BedrockEmbedder(region=region)
