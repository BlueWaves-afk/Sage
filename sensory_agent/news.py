"""
GDELT / News sub-agent.

Polls GDELT (free, 15-min updates) and NewsAPI RSS.
Nova Micro extracts {actor, action, target, severity, timestamp} from each article.
GDELT conflict tone is a leading indicator for price moves.
"""
from __future__ import annotations

from contracts.signal import EventPayload, NormalizedSignal


async def run() -> None:
    """Entry point. APScheduler polls every 15 minutes."""
    # TODO: schedule _poll_gdelt() and _poll_newsapi() every 15 min
    raise NotImplementedError


async def _poll_gdelt() -> list[NormalizedSignal]:
    """Fetch GDELT event stream and extract structured events. Stub."""
    # TODO: GET http://data.gdeltproject.org/gdeltv2/lastupdate.txt
    # TODO: parse event CSV rows relevant to energy/Middle East/India
    # TODO: send each article through Nova Micro for entity/event extraction
    # TODO: return list of NormalizedSignal with source='gdelt'
    return []


async def _poll_newsapi() -> list[NormalizedSignal]:
    """Fetch NewsAPI RSS headlines and extract structured events. Stub."""
    # TODO: GET newsapi.org headlines for energy/geopolitics topics with NEWSAPI_KEY
    # TODO: run Nova Micro extraction inline
    # TODO: return list of NormalizedSignal with source='news'
    return []
