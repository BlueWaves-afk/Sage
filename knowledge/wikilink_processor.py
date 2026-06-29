"""
Wikilink normalizer, validator, and frontmatter parser for SAGE second-brain wiki pages.

Three main functions:
  normalize_wikilinks(content)  → resolves [[aliases]] to [[Canonical Name]],
                                  rebuilds links_out from resolved entities
  validate_page(content)        → returns list[str] of validation errors
  parse_frontmatter(content)    → returns dict of YAML frontmatter fields
  parse_links_out(content)      → returns list[str] entity_ids from links_out

Used by:
  knowledge/synthesis.py  → render_wiki_page() passes output through normalizer
  knowledge/api/write.py  → ingest_signal() gates wiki write on validate_page()
  api_gateway/routes/wiki → parse_links_out() for geospatial renderer edge list
"""
from __future__ import annotations

import logging
import re
from typing import Any

import yaml

log = logging.getLogger(__name__)

_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")

# Required frontmatter fields (hard validation — page rejected if missing)
_REQUIRED_FM_FIELDS = (
    "entity_id", "entity_type", "risk_score", "risk_band",
    "factors", "last_updated", "valid_at",
)
_REQUIRED_FACTORS = ("ais", "gdelt", "price", "sanctions")


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------

def parse_frontmatter(content: str) -> dict[str, Any]:
    """
    Parse YAML frontmatter from a wiki page.
    Returns empty dict if no frontmatter or parse error.
    """
    if not content.startswith("---"):
        return {}
    try:
        end = content.index("---", 3)
        fm_text = content[3:end]
        return yaml.safe_load(fm_text) or {}
    except (ValueError, yaml.YAMLError) as exc:
        log.debug("Frontmatter parse error: %s", exc)
        return {}


def _split_page(content: str) -> tuple[dict[str, Any], str]:
    """
    Split page into (frontmatter_dict, body_text).
    body_text includes the leading newline after the closing ---.
    """
    if not content.startswith("---"):
        return {}, content
    try:
        end = content.index("---", 3)
        fm  = yaml.safe_load(content[3:end]) or {}
        body = content[end + 3:]
        return fm, body
    except (ValueError, yaml.YAMLError):
        return {}, content


def _reassemble(fm: dict[str, Any], body: str) -> str:
    """Reassemble frontmatter dict + body into a full page string."""
    fm_text = yaml.dump(fm, default_flow_style=False, allow_unicode=True,
                        sort_keys=False)
    return f"---\n{fm_text}---\n{body}"


# ---------------------------------------------------------------------------
# Normalizer
# ---------------------------------------------------------------------------

def normalize_wikilinks(content: str) -> str:
    """
    1. Find all [[...]] in the page body.
    2. Resolve each link text to a registry entity_id (alias lookup).
    3. Replace [[alias]] with [[Canonical Name]] if found in registry.
    4. Remove wikilinks that have no registry match (keep plain text).
    5. Rebuild links_out frontmatter field from resolved entity_ids.

    Returns the normalized full page content.
    """
    from knowledge.registry import ALIAS_TO_ENTITY, canonical_name as get_canonical

    fm, body = _split_page(content)
    resolved_ids: list[str] = []

    def _replace(match: re.Match) -> str:
        link_text = match.group(1).strip()
        entity_id = ALIAS_TO_ENTITY.get(link_text.lower())
        if entity_id:
            resolved_ids.append(entity_id)
            return f"[[{get_canonical(entity_id)}]]"
        # Not in registry — strip wikilink syntax, keep plain text
        log.debug("Wikilink [[%s]] has no registry match — unlinked", link_text)
        return link_text

    normalized_body = _WIKILINK_RE.sub(_replace, body)

    # Deduplicate while preserving first-seen order; remove self-links
    own_id = fm.get("entity_id", "")
    seen: list[str] = []
    for eid in resolved_ids:
        if eid != own_id and eid not in seen:
            seen.append(eid)

    fm["links_out"] = seen

    return _reassemble(fm, normalized_body)


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

def validate_page(content: str) -> list[str]:
    """
    Validate a wiki page against the enforced second-brain schema.

    Returns a list of error strings. Empty list = page is valid.

    Hard errors (page rejected if any present):
      - Missing frontmatter
      - Missing required frontmatter fields
      - Missing factor sub-fields
      - Malformed YAML

    Soft warnings (logged but page is still accepted):
      - links_out has < 2 entries (low-connectivity page)
      - No [[wikilinks]] in body
    """
    errors: list[str] = []

    if not content.startswith("---"):
        errors.append("Missing YAML frontmatter block")
        return errors

    try:
        end = content.index("---", 3)
        fm  = yaml.safe_load(content[3:end]) or {}
    except (ValueError, yaml.YAMLError) as exc:
        errors.append(f"Malformed frontmatter YAML: {exc}")
        return errors

    for field in _REQUIRED_FM_FIELDS:
        if field not in fm:
            errors.append(f"Missing required frontmatter field: '{field}'")

    if "factors" in fm and isinstance(fm["factors"], dict):
        for factor in _REQUIRED_FACTORS:
            if factor not in fm["factors"]:
                errors.append(f"Missing factor sub-field: 'factors.{factor}'")
    elif "factors" in fm:
        errors.append("'factors' must be a dict with keys: ais, gdelt, price, sanctions")

    # Soft warnings — do not add to errors (won't block write), just log
    body = content[content.index("---", 3) + 3:] if "---" in content[3:] else content
    links = fm.get("links_out", [])
    if len(links) < 2:
        log.warning(
            "Wiki page '%s' has only %d outgoing links (minimum 2 recommended). "
            "May indicate synthesis failed to find related entities.",
            fm.get("entity_id", "unknown"), len(links),
        )

    wikilinks_in_body = _WIKILINK_RE.findall(body)
    if not wikilinks_in_body and not errors:
        log.warning(
            "Wiki page '%s' has no [[wikilinks]] in body — synthesis may not have "
            "emitted wikilinks.",
            fm.get("entity_id", "unknown"),
        )

    return errors


# ---------------------------------------------------------------------------
# Helpers for downstream consumers
# ---------------------------------------------------------------------------

def parse_links_out(content: str) -> list[str]:
    """
    Extract links_out entity_ids from page frontmatter.
    Used by the geospatial renderer and copilot without regexing prose.
    Returns empty list if page has no frontmatter or no links_out.
    """
    fm = parse_frontmatter(content)
    links = fm.get("links_out", [])
    return links if isinstance(links, list) else []


def update_frontmatter_risk(
    content: str,
    score: float,
    band: str,
    factors: dict[str, float],
    valid_at: str,
    last_updated: str,
) -> str:
    """
    Update only the risk-related frontmatter fields in place.
    Body prose and [[wikilinks]] are left untouched.

    Used by write_risk_state() to update the score without overwriting
    the synthesis-authored narrative.
    """
    fm, body = _split_page(content)

    fm["risk_score"]   = round(score, 4)
    fm["risk_band"]    = band.upper()
    fm["factors"]      = {k: round(v, 4) for k, v in factors.items()}
    fm["valid_at"]     = valid_at
    fm["last_updated"] = last_updated

    return _reassemble(fm, body)


def extract_current_assessment(content: str) -> str:
    """
    Extract just the Current Assessment paragraph from a wiki page.
    Used by the copilot to get the 2-3 sentence summary for embedding.
    """
    body_match = re.search(r"## Current Assessment\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
    if body_match:
        return body_match.group(1).strip()
    return ""
