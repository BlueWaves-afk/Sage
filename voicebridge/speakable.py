"""
Speakable-text step. Converts a Perplexity-style Markdown answer (with
headings, bullet lists, tables, **bold**, and inline [n] citations) into a
short, TTS-appropriate sentence stream.

Design rule: the TTS voice reads aloud what a human colleague would summarise
— not the full 300-word Markdown answer. The Markdown answer is still shown
on-screen in the copilot / caption panel; the voice just gives a quick verbal
lede.
"""
from __future__ import annotations

import re


def to_speech(markdown: str, sources_index_to_entity: dict[int, str] | None = None) -> str:
    """
    Reduce a Markdown answer to a short paragraph suitable for TTS.

    - Strips headings, bullets, tables — takes the FIRST non-header sentence
      (the "direct answer" per the copilot's own style guide) and adds up to
      one additional short sentence for supporting context.
    - Replaces bare "[3]" citations with a spoken form ("according to the
      NIOC assessment") when we can resolve them to an entity name; otherwise
      just drops the bracket entirely (it's noise in speech).
    """
    if not markdown:
        return "I don't have anything on that yet."
    text = markdown.strip()

    # ── Structural cleanup ────────────────────────────────────────────────
    # Drop code fences and tables — they don't survive as speech.
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"^\s*\|.*\|\s*$", "", text, flags=re.MULTILINE)

    # Convert lists to comma-joined phrases so a 3-item bullet reads naturally.
    def _joinlist(match: re.Match) -> str:
        items = [
            re.sub(r"^\s*(?:\d+\.|[-*•])\s+", "", ln).strip()
            for ln in match.group(0).splitlines()
            if ln.strip()
        ]
        # Preserve them as a single sentence — the caller decides how many.
        if len(items) <= 1:
            return " ".join(items)
        return "; ".join(items) + "."

    text = re.sub(
        r"(?:^\s*(?:\d+\.|[-*•])\s+.+(?:\n|$))+",
        _joinlist,
        text,
        flags=re.MULTILINE,
    )

    # ── Inline styling → plain prose ──────────────────────────────────────
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # bold
    text = re.sub(r"\*(.+?)\*", r"\1", text)      # italic
    text = re.sub(r"`([^`]+)`", r"\1", text)       # code
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)  # wikilinks

    # ── Citations: [3] → "…according to X" or drop entirely ───────────────
    def _cite(m: re.Match) -> str:
        n = int(m.group(1))
        if sources_index_to_entity and n in sources_index_to_entity:
            return f" (from {sources_index_to_entity[n]})"
        return ""

    text = re.sub(r"\s*\[(\d+)\]", _cite, text)

    # ── Headings and blank lines ──────────────────────────────────────────
    lines = [ln.strip() for ln in text.splitlines()]
    keep: list[str] = []
    for ln in lines:
        if not ln:
            continue
        if ln.startswith("#"):
            continue  # skip section headings — the following sentence is the
            # "direct answer" per the copilot style guide already.
        keep.append(ln)
    body = " ".join(keep)
    body = re.sub(r"\s+", " ", body).strip()

    # ── Truncate to ~2 sentences ──────────────────────────────────────────
    # Split conservatively; some answers have "$1.5B, 2026." which shouldn't
    # split. Look for ". " followed by a capital letter.
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'])", body)
    if not sentences:
        return body[:280]

    speech = sentences[0]
    if len(sentences) > 1 and len(speech) < 160:
        speech += " " + sentences[1]

    # Hard cap so TTS latency is bounded.
    if len(speech) > 320:
        speech = speech[:317].rstrip(",;:") + "…"

    return speech
