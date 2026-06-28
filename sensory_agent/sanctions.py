"""
Sanctions diff sub-agent.

Downloads OFAC SDN, EU, and UN lists every 6 hours.
Diffs against Redis-cached last snapshot.
Any new addition → immediately HIGH priority, force_synthesis=True, bypasses similarity gate.
Also runs vessel ownership graph analytics: beneficial owner chains, flag-hopping patterns.
"""
from __future__ import annotations

from contracts.signal import NormalizedSignal, SanctionsPayload


async def run() -> None:
    """Entry point. APScheduler runs every 6 hours."""
    # TODO: schedule _diff_all_lists() every 6h
    raise NotImplementedError


async def _diff_all_lists() -> list[NormalizedSignal]:
    """Download and diff OFAC, EU, UN lists. Return signals for any changes. Stub."""
    signals = []
    for list_name, url in [
        ("OFAC", "https://www.treasury.gov/ofac/downloads/sdn.xml"),
        ("EU",   "https://data.europa.eu/api/hub/repo/..."),  # TODO: correct EU XML URL
        ("UN",   "https://scsanctions.un.org/resources/xml/en/consolidated.xml"),
    ]:
        # TODO: fetch XML, parse entries, diff against Redis cache
        # TODO: for each add/remove → build NormalizedSignal with force_synthesis=True
        pass
    return signals


async def _vessel_ownership_graph(subject: str) -> dict:
    """Trace beneficial owner chain for a sanctioned vessel. Stub."""
    # TODO: query vessel ownership database for flag-hopping patterns
    return {}
