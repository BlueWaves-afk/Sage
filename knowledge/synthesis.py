"""
SAGE narrative synthesis agent.

Runs between triage and the Graphiti write. The genuine contribution above Graphiti:
LLM reconciles new signal against the current entity wiki page, resolves contradictions,
produces updated prose, writes /wiki, then hands synthesized text to add_episode().

Key rule: synthesis happens ONCE at ingest time. Embeddings capture synthesized
understanding, not raw signal noise.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from contracts.signal import NormalizedSignal

WIKI_DIR = Path(os.environ.get("WIKI_DIR", "/app/wiki"))

SYNTH_PROMPT = """You maintain the intelligence page for {entity}.
A new signal has arrived.

CURRENT PAGE:
{current_page}

NEW SIGNAL:
{signal_summary}

Produce an updated assessment. You MUST:
1. State the current reconciled status in 2-3 sentences.
2. If the new signal contradicts the current page, explain WHY the contradiction
   exists (lagging data? different measurement? genuine change?). Do not just overwrite.
3. Note any historical pattern this matches.
4. List affected downstream entities.
Keep it factual, cited, under 250 words."""


def _wiki_path(entity: str) -> Path:
    slug = entity.lower().replace(" ", "_").replace("/", "-")
    return WIKI_DIR / f"{slug}.md"


def load_wiki_page(entity: str) -> str:
    path = _wiki_path(entity)
    if path.exists():
        return path.read_text()
    return f"# {entity}\n\nNo intelligence page yet — this is the first signal.\n"


def write_wiki_page(entity: str, content: str) -> None:
    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    _wiki_path(entity).write_text(content)


async def synthesize(signal: NormalizedSignal, entity: str) -> str:
    """
    Synthesize a new wiki page for `entity` given the incoming signal.
    Returns the synthesized text — this is what gets passed to add_episode().

    Stub — real implementation calls Bedrock Nova Pro with SYNTH_PROMPT.
    """
    current_page = load_wiki_page(entity)

    # TODO: call Bedrock Nova Pro with SYNTH_PROMPT formatted below
    prompt = SYNTH_PROMPT.format(
        entity=entity,
        current_page=current_page,
        signal_summary=signal.summary,
    )
    synthesized_text: str = f"[STUB] Synthesis for {entity} at {datetime.now(timezone.utc).isoformat()}\n{signal.summary}"

    write_wiki_page(entity, synthesized_text)
    return synthesized_text
