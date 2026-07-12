"""
SAGE narrative synthesis agent — second-brain edition.

Produces wiki pages in the enforced second-brain format:
  - YAML frontmatter (entity_id, risk_score, risk_band, factors, links_out, …)
  - Body sections with [[Canonical Name]] wikilinks throughout
  - Relations table as machine-readable link metadata

Write flow:
  1. Load current wiki page (frontmatter + body) for entity
  2. Inject registry excerpt so LLM knows which names to wikilink
  3. Call Nova Pro → body sections with [[wikilinks]]
  4. render_wiki_page() wraps body in validated frontmatter
  5. normalize_wikilinks() resolves [[aliases]] → [[Canonical Name]], builds links_out
  6. validate_page() checks required fields (hard) and link count (soft warning)
  7. Caller (ingest_signal) persists if no hard errors

Risk score is NOT stored in synthesis prose labels (prevents HAS_RISK_SCORE
hallucination). It lives in frontmatter and is expressed as a sentence in the
Current Assessment section.

write_risk_state() updates frontmatter risk fields in place without
touching narrative body — wiki prose and risk score stay in sync without
accumulating appended blocks.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from contracts.signal import NormalizedSignal

log = logging.getLogger(__name__)

# The wiki store lives under knowledge/ so all three KB stores (graph, vector, wiki)
# are co-located and the growing "memory" is visible/browsable (Obsidian vault).
# Docker overrides WIKI_DIR=/app/wiki (bind-mounted to ./knowledge/wiki).
WIKI_DIR = Path(os.environ.get("WIKI_DIR", "knowledge/wiki"))


# ---------------------------------------------------------------------------
# Synthesis prompt
# ---------------------------------------------------------------------------

SYNTH_PROMPT = """\
You maintain the intelligence page for {entity} (entity_id: {entity_id}).
A new signal has arrived. Produce an updated wiki page body in the EXACT format below.

CANONICAL ENTITY REGISTRY — use [[Canonical Name]] exactly as shown for EVERY
tracked entity you mention. Do not invent wikilinks to entities not in this list:
{registry_excerpt}

CURRENT PAGE:
{current_page}

NEW SIGNAL:
Source: {source} | Priority: {priority} | Observed: {observed_at}
{signal_summary}

Produce ONLY the body sections below — no frontmatter, no extra sections.
The risk score is: {risk_score_sentence}

## Current Assessment
[2-3 sentences. State the current reconciled situation. EVERY mention of a tracked
entity is a [[Canonical Name]] wikilink — no bare entity names. Do NOT use labels
like "Current risk score:" or "Factor breakdown:" — express them in sentences only.
If the risk score is provided above, embed it naturally in a sentence.]

## Contradiction Note
[ONLY if sources disagree — explain WHY they disagree, not just WHAT differs.
Link both disagreeing sources as [[...]]. OMIT this entire section if consistent.]

## Historical Pattern
[If a clear precedent exists, state it as [[Event Name]] with feature-overlap
percentage. OMIT if no clear precedent.]

## Affected Entities
[Bulleted list. EVERY entity is a [[Canonical Name]] link. State exposure level and
the specific reason (inventory days, throughput share, etc.).]

## Signal Basis
[One line per contributing signal. Name signal clusters as [[Cluster Name]] if
significant enough to have their own page.]

## Relations
| Relation | Entity | Type | Strength |
|---|---|---|---|
[ONE row per unique [[wikilink]] above. Relation types: supply_dependency,
threat_actor, historical_precedent, bypass_option, signal_source, sanctions_link,
owned_by. Strength: high / medium / low.]

RULES:
1. Every tracked entity in prose is a [[Canonical Name]] link — no exceptions.
2. Do NOT write "Current risk score:" or "Factor breakdown:" as labels.
3. Do NOT invent wikilinks to entities not in the registry list above.
4. Include a Relations row for EVERY unique entity you wikilinked.
5. The Relations table must have at least 1 row.
6. If the new signal contradicts the current page, include Contradiction Note.
7. Keep Current Assessment to 2-3 sentences maximum.\
"""

# Prose-only risk template — "Current risk score: X" / "Factor breakdown: Y"
# labels cause Nova Lite extraction LLM to hallucinate HAS_RISK_SCORE /
# HAS_FACTOR_BREAKDOWN edges not in the SAGE schema.
_RISK_SENTENCE_TEMPLATE = (
    "The assessed risk level for {entity} is {score:.2f} out of 1.0 "
    "({band} band) as of {ts}Z, with AIS dark-vessel contributing {factor_ais:.2f}, "
    "GDELT conflict tone {factor_gdelt:.2f}, "
    "price war-risk premium {factor_price:.2f}, "
    "and sanctions exposure {factor_sanctions:.2f}."
)


# ---------------------------------------------------------------------------
# /wiki store helpers
# ---------------------------------------------------------------------------

def _wiki_path(entity: str) -> Path:
    """
    Derive wiki file path from entity display name or entity_id.
    Canonical entity_ids (from registry) are preferred keys.
    """
    slug = entity.lower().replace(" ", "_").replace("/", "-").replace("\\", "-")
    return WIKI_DIR / f"{slug}.md"


def _wiki_path_by_id(entity_id: str) -> Path:
    return WIKI_DIR / f"{entity_id}.md"


def load_wiki_page(entity: str) -> str:
    """Load wiki page by display name. Falls back to empty stub if not found."""
    # Try entity_id (from registry) first, then display-name slug
    from knowledge.registry import entity_id_from_display
    eid = entity_id_from_display(entity)
    if eid:
        path = _wiki_path_by_id(eid)
        if path.exists():
            return path.read_text(encoding="utf-8")

    path = _wiki_path(entity)
    if path.exists():
        return path.read_text(encoding="utf-8")

    return (
        f"# {entity}\n\n"
        "No intelligence page yet — this is the first signal for this entity.\n"
    )


def write_wiki_page(entity: str, content: str) -> None:
    """Write wiki page. Uses entity_id as filename if entity is in registry."""
    WIKI_DIR.mkdir(parents=True, exist_ok=True)

    from knowledge.registry import entity_id_from_display
    eid = entity_id_from_display(entity)
    path = _wiki_path_by_id(eid) if eid else _wiki_path(entity)

    path.write_text(content, encoding="utf-8")
    log.debug("Wiki page updated: %s", path)
    _git_commit_wiki(path, entity)


def _git_commit_wiki(path: Path, entity: str) -> None:
    import subprocess
    try:
        subprocess.run(
            ["git", "-C", str(WIKI_DIR), "add", path.name],
            capture_output=True, check=True, timeout=10,
        )
        subprocess.run(
            ["git", "-C", str(WIKI_DIR), "commit", "-m",
             f"chore(wiki): update {entity} "
             f"[{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}]"],
            capture_output=True, check=True, timeout=10,
        )
    except FileNotFoundError:
        pass
    except Exception as exc:
        log.debug("Wiki git commit skipped: %s", exc)


def list_wiki_entities() -> list[str]:
    """Return all entity slugs that have wiki pages."""
    if not WIKI_DIR.exists():
        return []
    return [p.stem for p in WIKI_DIR.glob("*.md")]


# ---------------------------------------------------------------------------
# render_wiki_page — builds full frontmatter + normalized body
# ---------------------------------------------------------------------------

def _entity_tags(entity_type: str, risk_band: str) -> list[str]:
    """
    Obsidian graph-colouring tags. `sage/<type>` groups nodes by entity type (the
    default colouring); `risk/<band>` lets the user re-colour by risk band. Lowercased
    and space-free so they are valid Obsidian tags (e.g. CrudeGrade -> sage/crudegrade).
    """
    t = (entity_type or "unknown").lower().replace(" ", "").replace("/", "")
    b = (risk_band or "calm").lower()
    return [f"sage/{t}", f"risk/{b}"]


def render_wiki_page(
    entity: str,
    synthesized_body: str,
    *,
    entity_id: Optional[str] = None,
    entity_type: str = "Unknown",
    risk_score: float = 0.0,
    risk_band: str = "calm",
    factors: Optional[dict] = None,
    valid_at: Optional[str] = None,
    source_episodes: Optional[list[str]] = None,
    coordinates: Optional[dict] = None,
    # Carry over existing links_out if synthesis produced no wikilinks
    existing_links_out: Optional[list[str]] = None,
) -> str:
    """
    Render a full wiki page: frontmatter + normalized body.

    1. Build YAML frontmatter from known values (not from LLM)
    2. Assemble page = frontmatter + synthesized_body
    3. Run normalize_wikilinks() → resolves [[aliases]], builds links_out
    4. links_out in frontmatter is replaced by normalizer output

    Returns the complete normalized page content ready for validate_page().
    """
    from knowledge.wikilink_processor import normalize_wikilinks
    from knowledge.registry import entity_id_from_display, REGISTRY

    stamp = datetime.now(timezone.utc).isoformat()

    # Resolve entity_id from registry if not supplied
    if entity_id is None:
        entity_id = entity_id_from_display(entity) or (
            entity.lower().replace(" ", "_").replace("/", "-")
        )

    # Resolve entity_type from registry if still "Unknown"
    if entity_type == "Unknown" and entity_id in REGISTRY:
        entity_type = REGISTRY[entity_id].entity_type

    # Resolve coordinates from registry if not supplied
    if not coordinates and entity_id in REGISTRY:
        coordinates = REGISTRY[entity_id].coordinates or {}

    fm = {
        "entity_id":       entity_id,
        # Obsidian resolves [[Display Name]] wikilinks to this file via aliases,
        # even though the filename is the entity_id (e.g. corridor_hormuz.md).
        "aliases":         [entity],
        "entity_type":     entity_type,
        # Tags drive Obsidian graph color groups: sage/<type> colours nodes by entity
        # type, risk/<band> lets the user re-colour by risk. See .obsidian/graph.json.
        "tags":            _entity_tags(entity_type, risk_band),
        "risk_score":      round(risk_score, 4),
        "risk_band":       risk_band.upper(),
        "factors":         factors or {"ais": 0.0, "gdelt": 0.0, "price": 0.0, "sanctions": 0.0},
        "last_updated":    stamp,
        "valid_at":        valid_at or stamp,
        "source_episodes": source_episodes or [],
        "links_out":       existing_links_out or [],   # normalizer will rebuild this
        "coordinates":     coordinates or {},
    }

    fm_text = yaml.dump(fm, default_flow_style=False, allow_unicode=True, sort_keys=False)
    raw_page = f"---\n{fm_text}---\n\n{synthesized_body}"

    # Normalizer resolves [[aliases]], rebuilds links_out from resolved entities
    normalized = normalize_wikilinks(raw_page)
    return normalized


# ---------------------------------------------------------------------------
# Main synthesis function
# ---------------------------------------------------------------------------

async def synthesize(
    signal: NormalizedSignal,
    entity: str,
    *,
    risk_score: Optional[float] = None,
    risk_band: Optional[str] = None,
    factor_ais: float = 0.0,
    factor_gdelt: float = 0.0,
    factor_price: float = 0.0,
    factor_sanctions: float = 0.0,
    rationale: Optional[str] = None,
    model_version: Optional[str] = None,
    source_episodes: Optional[list[str]] = None,
    persist: bool = True,
) -> str:
    """
    Synthesize and optionally persist an updated wiki page for `entity`.

    Returns the full normalized page content (frontmatter + body).
    Caller passes this directly to ingest_signal for validation + add_episode.

    persist=False: return content without writing to /wiki (caller defers write
    until graph write succeeds — atomic wiki ↔ graph consistency).
    persist=True: write immediately (standalone use).
    """
    from knowledge.registry import (
        entity_id_from_display, entity_type as get_entity_type,
        REGISTRY, build_registry_excerpt,
    )

    current_page = load_wiki_page(entity)

    # Resolve entity_id and entity_type from registry
    eid   = entity_id_from_display(entity)
    etype = REGISTRY[eid].entity_type if eid else "Unknown"
    coords = REGISTRY[eid].coordinates if eid else {}

    # Build risk score sentence for prompt (prose — no structured labels)
    if risk_score is not None and risk_band is not None:
        rs_sentence = _RISK_SENTENCE_TEMPLATE.format(
            entity=entity,
            score=risk_score,
            band=risk_band,
            ts=signal.observed_at.strftime("%Y-%m-%d %H:%M"),
            factor_ais=factor_ais,
            factor_gdelt=factor_gdelt,
            factor_price=factor_price,
            factor_sanctions=factor_sanctions,
        )
    else:
        rs_sentence = "No risk score available for this signal."

    prompt = SYNTH_PROMPT.format(
        entity=entity,
        entity_id=eid or entity.lower().replace(" ", "_"),
        registry_excerpt=build_registry_excerpt(),
        current_page=current_page,
        source=signal.source,
        priority=signal.priority_hint,
        observed_at=signal.observed_at.strftime("%Y-%m-%d %H:%M UTC"),
        signal_summary=signal.summary,
        risk_score_sentence=rs_sentence,
    )

    synthesized_body = await _call_nova_pro(prompt, entity)

    page_content = render_wiki_page(
        entity=entity,
        synthesized_body=synthesized_body,
        entity_id=eid,
        entity_type=etype,
        risk_score=risk_score or 0.0,
        risk_band=risk_band or "calm",
        factors={
            "ais":        factor_ais,
            "gdelt":      factor_gdelt,
            "price":      factor_price,
            "sanctions":  factor_sanctions,
        },
        valid_at=signal.observed_at.isoformat(),
        source_episodes=source_episodes or [],
        coordinates=coords,
    )

    if persist:
        write_wiki_page(entity, page_content)

    return page_content


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

_SYNTH_LLM = None  # dedicated client for user-facing wiki prose


def _get_synthesis_llm():
    """Dedicated Nova Lite client for wiki synthesis.

    Wiki prose is user-facing (it renders as the Live Intelligence feed detail).
    It runs on Nova Lite (~13x cheaper than Nova Pro) — Lite produces adequate
    analytical prose for the feed and keeps synthesis cost negligible. Falls back
    to the shared Graphiti client for non-bedrock providers (stub/openai), which
    don't distinguish model tiers here.
    """
    global _SYNTH_LLM
    if _SYNTH_LLM is not None:
        return _SYNTH_LLM
    import os
    from knowledge.connection import _get_graphiti
    if os.environ.get("LLM_PROVIDER", "stub").lower() == "bedrock":
        from knowledge.bedrock import nova_lite
        _SYNTH_LLM = nova_lite(os.environ.get("AWS_REGION", "us-east-1"))
    else:
        _SYNTH_LLM = _get_graphiti().llm_client
    return _SYNTH_LLM


async def _call_nova_pro(prompt: str, entity: str) -> str:
    try:
        llm = _get_synthesis_llm()

        messages = [
            {
                "role": "system",
                "content": (
                    "You are SAGE, an expert intelligence analyst specialising in "
                    "oil supply chain geopolitics, shipping, and energy security. "
                    "Be concise, factual, and analytically precise. "
                    "Always wikilink tracked entities as [[Canonical Name]]."
                ),
            },
            {"role": "user", "content": prompt},
        ]

        result = await llm.generate(messages=messages)
        return result.strip() if isinstance(result, str) else str(result)

    except Exception as exc:
        log.warning("Nova Pro synthesis failed for '%s': %s — using stub", entity, exc)
        return _fallback_synthesis(entity)


def _fallback_synthesis(entity: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"## Current Assessment\n\n"
        f"{entity} intelligence page updated {now}. "
        f"A new signal has been received and ingested. "
        f"Full narrative synthesis pending Bedrock Nova Pro availability. "
        f"Monitoring continues.\n\n"
        f"## Signal Basis\n\n"
        f"- Signal received but synthesis LLM unavailable at {now}\n\n"
        f"## Relations\n\n"
        f"| Relation | Entity | Type | Strength |\n"
        f"|---|---|---|---|\n"
    )
