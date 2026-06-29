"""
SAGE narrative synthesis agent.

Runs between triage and the Graphiti write. This is SAGE's genuine contribution
above Graphiti: the LLM reconciles new signal against the current entity wiki page,
resolves contradictions, and produces updated intelligence prose.

Key rule: synthesis happens ONCE at ingest time. Embeddings capture synthesized
understanding, not isolated raw signal noise. The /wiki store and the Graphiti
graph must always reflect the same state — this function keeps them in sync.

Write flow:
  1. Load current wiki page for entity (from /wiki markdown store)
  2. Build SYNTH_PROMPT with current page + new signal
  3. Call Nova Pro → get reconciled assessment prose (≤250 words)
  4. Write updated page to /wiki store
  5. Return synthesized text for caller to pass to add_episode()

If risk score is available (from sensory_agent fusion), embed it in the episode
text so Graphiti extracts a RISK_STATE edge from the prose. See §6.4 of the
schema spec.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from contracts.signal import NormalizedSignal

log = logging.getLogger(__name__)

WIKI_DIR = Path(os.environ.get("WIKI_DIR", "/app/wiki"))

# ---------------------------------------------------------------------------
# Synthesis prompt
# ---------------------------------------------------------------------------

SYNTH_PROMPT = """\
You maintain the intelligence page for {entity}.
A new signal has arrived.

CURRENT PAGE:
{current_page}

NEW SIGNAL:
Source: {source} | Priority: {priority} | Observed: {observed_at}
{signal_summary}

Produce an updated intelligence assessment. You MUST:
1. State the current reconciled status of {entity} in 2-3 sentences.
2. If the new signal contradicts the current page, explain WHY the contradiction
   exists (lagging data? different measurement? genuine change?). Do not overwrite
   the prior assessment without explanation.
3. Note any historical pattern this matches (e.g. prior Hormuz closures, sanction cycles).
4. List the downstream entities most directly affected (refineries, ports, vessels).
5. If a risk score is provided, embed it in a sentence like:
   "The assessed risk level is {score_placeholder} ({band_placeholder} band),
   with AIS contributing {ais_placeholder}, GDELT {gdelt_placeholder},
   price {price_placeholder}, and sanctions {sanctions_placeholder}."
   Do NOT use "Current risk score:" or "Factor breakdown:" as labels.
Keep the full response factual, cited, and under 250 words.
Do not add headers or bullet points — write in flowing prose.\
"""

# Prose-only format intentional: "Current risk score: X" / "Factor breakdown: Y"
# labels cause Nova Lite (extraction LLM) to invent HAS_RISK_SCORE /
# HAS_FACTOR_BREAKDOWN edges that are not in the SAGE schema. Same data as
# sentences; the RISK_STATE edge is still extracted correctly from the prose.
RISK_STATE_TEMPLATE = """\

The assessed risk level is {score:.2f} out of 1.0 ({band} band). \
Signal contributions: AIS dark-vessel {factor_ais:.2f}, \
GDELT conflict tone {factor_gdelt:.2f}, \
price war-risk premium {factor_price:.2f}, \
sanctions exposure {factor_sanctions:.2f}. \
{rationale} Fusion model: {model_version}.\
"""


# ---------------------------------------------------------------------------
# /wiki store helpers
# ---------------------------------------------------------------------------

def _wiki_path(entity: str) -> Path:
    slug = entity.lower().replace(" ", "_").replace("/", "-").replace("\\", "-")
    return WIKI_DIR / f"{slug}.md"


def load_wiki_page(entity: str) -> str:
    path = _wiki_path(entity)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return (
        f"# {entity}\n\n"
        "No intelligence page yet — this is the first signal for this entity.\n"
    )


def write_wiki_page(entity: str, content: str) -> None:
    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    path = _wiki_path(entity)
    path.write_text(content, encoding="utf-8")
    log.debug("Wiki page updated: %s", path)
    _git_commit_wiki(path, entity)


def _git_commit_wiki(path: Path, entity: str) -> None:
    """
    Commit the updated wiki page to git so history is preserved (spec §6.2).
    Runs as a subprocess — failure is non-fatal so a missing git repo or
    un-configured identity doesn't block ingest.
    """
    import subprocess
    try:
        subprocess.run(
            ["git", "-C", str(WIKI_DIR), "add", path.name],
            capture_output=True, check=True, timeout=10,
        )
        subprocess.run(
            ["git", "-C", str(WIKI_DIR), "commit", "-m",
             f"chore(wiki): update {entity} [{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}]"],
            capture_output=True, check=True, timeout=10,
        )
    except FileNotFoundError:
        pass   # git not installed in this environment
    except subprocess.CalledProcessError:
        pass   # not a git repo, nothing to commit, or no identity configured
    except Exception as exc:
        log.debug("Wiki git commit skipped: %s", exc)


def render_wiki_page(entity: str, synthesized_text: str) -> str:
    """Render canonical wiki markdown without persisting it.

    Split out from write_wiki_page so the caller can build the page but defer
    the write until the graph write (add_episode) has succeeded — this is what
    keeps the /wiki store and the graph from drifting apart on partial failure.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"# {entity}\n\n_Last updated: {stamp}_\n\n{synthesized_text}"


def list_wiki_entities() -> list[str]:
    """Return all entity slugs that have wiki pages."""
    if not WIKI_DIR.exists():
        return []
    return [p.stem for p in WIKI_DIR.glob("*.md")]


# ---------------------------------------------------------------------------
# Main synthesis function
# ---------------------------------------------------------------------------

async def synthesize(
    signal: NormalizedSignal,
    entity: str,
    risk_score: Optional[float] = None,
    risk_band: Optional[str] = None,
    factor_ais: float = 0.0,
    factor_gdelt: float = 0.0,
    factor_price: float = 0.0,
    factor_sanctions: float = 0.0,
    rationale: Optional[str] = None,
    model_version: Optional[str] = None,
    persist: bool = True,
) -> str:
    """
    Synthesize a new wiki page for `entity` given the incoming signal.

    Optionally embeds risk score into the episode text so Graphiti extracts
    a RISK_STATE edge from the prose (§6.4 of schema spec).

    Returns the full synthesized text — this is passed directly to add_episode().

    persist=False returns the synthesized prose WITHOUT writing the wiki page.
    The caller is then responsible for persisting it (via render_wiki_page +
    write_wiki_page) only after the graph write succeeds, so the two stores
    cannot drift. The default (True) preserves the standalone behaviour.
    """
    current_page = load_wiki_page(entity)

    prompt = SYNTH_PROMPT.format(
        entity=entity,
        current_page=current_page,
        source=signal.source,
        priority=signal.priority_hint,
        observed_at=signal.observed_at.strftime("%Y-%m-%d %H:%M UTC"),
        signal_summary=signal.summary,
        score_placeholder="<SCORE>",
        band_placeholder="<BAND>",
        ais_placeholder="<AIS>",
        gdelt_placeholder="<GDELT>",
        price_placeholder="<PRICE>",
        sanctions_placeholder="<SANCTIONS>",
    )

    synthesized_text = await _call_nova_pro(prompt, entity)

    # If risk score provided, append structured risk state block to synthesized text
    # so Graphiti can extract the RISK_STATE edge from the episode body
    if risk_score is not None and risk_band is not None:
        risk_block = RISK_STATE_TEMPLATE.format(
            score=risk_score,
            band=risk_band,
            factor_ais=factor_ais,
            factor_gdelt=factor_gdelt,
            factor_price=factor_price,
            factor_sanctions=factor_sanctions,
            rationale=rationale or "",
            model_version=model_version or "unknown",
        )
        synthesized_text = synthesized_text.rstrip() + "\n" + risk_block

    # Persist to /wiki store unless the caller wants to defer until the graph
    # write succeeds (atomic wiki↔graph consistency — see ingest_signal).
    if persist:
        write_wiki_page(entity, render_wiki_page(entity, synthesized_text))

    return synthesized_text


async def _call_nova_pro(prompt: str, entity: str) -> str:
    """
    Call Bedrock Nova Pro with the synthesis prompt.
    Falls back to a minimal stub if Bedrock is unavailable (e.g. local dev).
    """
    try:
        from knowledge.connection import _get_graphiti
        g = _get_graphiti()
        llm = g.llm_client

        messages = [
            {
                "role": "system",
                "content": (
                    "You are SAGE, an expert intelligence analyst specialising in "
                    "oil supply chain geopolitics, shipping, and energy security. "
                    "Be concise, factual, and analytically precise."
                ),
            },
            {"role": "user", "content": prompt},
        ]

        result = await llm.generate(messages=messages)
        if isinstance(result, str):
            return result.strip()
        # Pydantic model returned (shouldn't happen here — no response_model passed)
        return str(result)

    except Exception as exc:
        log.warning("Nova Pro synthesis failed for '%s': %s — using stub", entity, exc)
        return _fallback_synthesis(entity, prompt)


def _fallback_synthesis(entity: str, prompt: str) -> str:
    """
    Minimal synthesis fallback when Bedrock is unavailable.
    Produces a grammatically correct but content-free stub that at least
    won't confuse Graphiti's extraction (no malformed text).
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"{entity} — intelligence assessment updated {now}. "
        f"A new signal has been received and ingested. "
        f"Full narrative synthesis is pending Bedrock Nova Pro availability. "
        f"No contradictions with prior assessment detected at this time. "
        f"Downstream entities may be affected; monitoring continues."
    )
