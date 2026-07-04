"""
Intent classifier — maps a transcript to a VoiceAction (or None for a data
query). Heuristic-first because latency here is the largest single contributor
to the "does this feel live" perception: an LLM round-trip on every utterance
would blow the design's ~1s nav-round-trip budget.

Returns (action_dict | None, spoken_ack | None, is_data_query: bool).

- action_dict: the JSON envelope the browser's applyVoiceAction() consumes
- spoken_ack:  a short terse acknowledgment to speak back (may be None)
- is_data_query: if True, the caller should also invoke copilot_query() for
                 the full answer
"""
from __future__ import annotations

import re
from typing import Optional

# ── Canonical entity matching ────────────────────────────────────────────────
# The KB registry is the source of truth for which entities exist — we resolve
# whatever the user said against that list rather than trying to hardcode
# every name/alias here. Lazy-loaded so this module stays importable even
# without a running knowledge base (e.g. in tests).
_REGISTRY_CACHE: dict | None = None


def _registry() -> dict:
    global _REGISTRY_CACHE
    if _REGISTRY_CACHE is None:
        try:
            from knowledge.registry import REGISTRY
            _REGISTRY_CACHE = REGISTRY
        except Exception:
            _REGISTRY_CACHE = {}
    return _REGISTRY_CACHE


def _resolve_entity(fragment: str) -> Optional[str]:
    """Find the best-matching canonical entity for a spoken fragment."""
    if not fragment:
        return None
    frag = fragment.lower().strip().rstrip(".,!?")
    best_name: Optional[str] = None
    best_score = 0
    for entry in _registry().values():
        candidates = [entry.canonical_name, *entry.aliases]
        for c in candidates:
            cl = c.lower()
            if frag == cl:
                return entry.canonical_name  # exact wins immediately
            # Substring in either direction — favours the longer overlap so
            # "Strait" alone doesn't beat "Strait of Hormuz" as a candidate.
            if cl in frag or frag in cl:
                score = min(len(cl), len(frag))
                if score > best_score:
                    best_score = score
                    best_name = entry.canonical_name
    return best_name


# ── Navigation intents ───────────────────────────────────────────────────────
_NAV_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"\b(command|dashboard|home|main)\b"), "/command", "Command Center."),
    (re.compile(r"\b(intelligence|explorer|graph|knowledge graph|map)\b"), "/intelligence", "Global Intelligence."),
    (re.compile(r"\b(simulation|sandbox|lab|scenario view)\b"), "/simulation", "Simulation Lab."),
    (re.compile(r"\b(response|procurement|reserve|planner)\b"), "/response", "Response Planner."),
    (re.compile(r"\b(copilot|chat|assistant|ask)\b"), "/copilot", "Strategic Copilot."),
]

# ── KPI intents ──────────────────────────────────────────────────────────────
_KPI_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bthreat( level)?\b|\brisk level\b"), "threat_level"),
    (re.compile(r"\bbrent\b|\bcrude price\b|\boil price\b"), "brent_usd_bbl"),
    (re.compile(r"\bs\.?p\.?r\.?\b|\breserve\b|\bcoverage\b"), "spr_coverage_pct"),
    (re.compile(r"\balerts?\b"), "active_alerts"),
    (re.compile(r"\bentit(y|ies)\b|\bnodes?\b|\bmonitor(ed|ing)?\b"), "monitoring_entities"),
]

# Fragments that mean "the user wants a data answer, not just a UI change".
_DATA_QUERY_MARKERS = re.compile(
    r"\b(why|how|explain|compare|which|what|would|should|because|difference|"
    r"tradeoff|impact|risk|scenario|cascade|between)\b",
    re.IGNORECASE,
)

# Fragments that mean "open the reconciled wiki page for this entity" rather
# than move the map camera.
_WIKI_PATTERNS = re.compile(
    r"\b(tell me (?:more )?about|what is|who is|open( the)? wiki(pedia)?|"
    r"read( me)? about|briefing on|story on)\b",
    re.IGNORECASE,
)

_FOCUS_PATTERNS = re.compile(
    r"\b(show|zoom|focus|highlight|find|go to|jump to)\b",
    re.IGNORECASE,
)

_RUN_PATTERNS = re.compile(
    r"\b(run|execute|simulate|kick off|start)\b.*\b(scenario|disruption|crisis|simulation)\b",
    re.IGNORECASE,
)

# For "select ADNOC" / "pick option 2" / "compare with Aramco"
_SELECT_PATTERNS = re.compile(
    r"\b(select|pick|choose|show me|compare|why is)\b.*?(option \d+|"
    r"option one|option two|option three|first option|second option|third option|"
    r"\w+(?:\s+\w+)?)\s*(?:ranked|first|top)?\s*$",
    re.IGNORECASE,
)

_STOP_PATTERNS = re.compile(r"\b(stop|cancel|never mind|shut up|be quiet)\b", re.IGNORECASE)


def classify(text: str) -> tuple[Optional[dict], Optional[str], bool]:
    """Route a transcript. See module docstring for the return shape."""
    t = (text or "").strip()
    if not t:
        return None, None, False

    lower = t.lower()

    # Stop is handled client-side too, but if a "stop" reaches the server
    # we still want to acknowledge it so the transcript is complete.
    if _STOP_PATTERNS.search(lower):
        return None, None, False

    # 1) Entity resolution up-front — several intents need it.
    entity = _resolve_entity(t)

    # 2) Run-scenario intent — takes precedence over "show/focus" because
    #    "run a Hormuz disruption scenario" contains both patterns.
    if _RUN_PATTERNS.search(lower) and entity:
        return (
            {"type": "run_scenario", "trigger_entity": entity},
            f"Running the {entity} scenario.",
            False,
        )

    # 3) Wiki / "tell me about X" — open the drawer, then let the data-query
    #    path also fire so we speak the Current Assessment aloud.
    if _WIKI_PATTERNS.search(lower) and entity:
        return (
            {"type": "open_wiki", "entity": entity},
            None,
            True,
        )

    # 4) Focus entity — "show me the strait of hormuz" / "zoom into Jamnagar"
    if _FOCUS_PATTERNS.search(lower) and entity:
        return (
            {"type": "focus_entity", "entity": entity},
            f"Here's {entity}.",
            False,
        )

    # 5) KPI lookup — "what's the SPR coverage" hits both a KPI pattern AND
    #    a data-query marker; use the KPI action (which speaks the number)
    #    and DON'T route to the copilot (would duplicate).
    for pat, key in _KPI_PATTERNS:
        if pat.search(lower):
            return ({"type": "flash_kpi", "key": key}, None, False)

    # 6) Nav — "go to the map" / "show me the command center"
    for pat, route, ack in _NAV_PATTERNS:
        if pat.search(lower):
            return ({"type": "navigate", "route": route}, ack, False)

    # 7) Supplier / option selection on the Response Planner
    if _SELECT_PATTERNS.search(lower):
        # Prefer a resolved entity if we can (Supplier), otherwise pass the
        # raw fragment; the frontend does a lenient startsWith match.
        target = entity or t.split()[-1]
        return (
            {"type": "select_option", "supplier": target},
            f"Selecting {target}.",
            False,
        )

    # 8) Otherwise — treat as an open-ended question to copilot_query().
    is_query = bool(_DATA_QUERY_MARKERS.search(lower)) or len(t.split()) > 4
    return None, None, is_query
