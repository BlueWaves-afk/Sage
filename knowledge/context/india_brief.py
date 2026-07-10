"""
India Supply Chain Situation Brief — living KB node.

Synthesizes a continuously-updated geopolitical situation assessment for India's
energy supply chain, written to knowledge/wiki/india.md.

Updated by:
  - System 1: after every HIGH signal that mentions India-connected entities
  - Systems 2/3/4: after scenario/procurement/SPR outputs are written

The brief is structured for the AI Situation Brief panel in the Command Center.
It is written by Nova Pro from live KB state — not hardcoded.

Cooldown: _LAST_REFRESH tracks the last write time so we don't call the LLM on
every single signal. HIGH signals trigger a refresh at most once per 20 minutes;
System 2/3/4 outputs always trigger a refresh (they're infrequent).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

log = logging.getLogger(__name__)

_LAST_REFRESH: Optional[datetime] = None
_COOLDOWN_MIN = 20  # minimum minutes between autonomous refreshes
_INDIA_WIKI_SLUG = "india"

# Source URLs for citing the data in the brief
_SOURCE_URLS = {
    "eia": "https://www.eia.gov/petroleum/",
    "ofac": "https://ofac.treasury.gov/sanctions-list-search",
    "un": "https://www.un.org/securitycouncil/sanctions/information",
    "aisstream": "https://aisstream.io",
    "newsdata": "https://newsdata.io",
}


async def refresh_india_brief(force: bool = False) -> bool:
    """
    Re-synthesize india.md from current KB state.
    Returns True if the page was written, False if skipped (cooldown / error).
    `force=True` bypasses cooldown (used when Systems 2/3/4 produce outputs).
    """
    global _LAST_REFRESH

    now = datetime.now(timezone.utc)
    if not force and _LAST_REFRESH is not None:
        elapsed = (now - _LAST_REFRESH).total_seconds() / 60
        if elapsed < _COOLDOWN_MIN:
            return False

    try:
        content = await _synthesize_india_brief(now)
        if content:
            _write_india_wiki(content)
            _LAST_REFRESH = now
            log.info("India supply chain brief refreshed at %s", now.isoformat())
            return True
    except Exception as exc:
        log.warning("india_brief refresh failed: %s", exc)
    return False


async def _synthesize_india_brief(now: datetime) -> str:
    """Build the full india.md page content via Nova Pro."""
    context = await _gather_context()
    prompt = _build_prompt(context, now)

    try:
        from knowledge.connection import _get_graphiti
        g = _get_graphiti()
        llm = g.llm_client
        messages = [
            {
                "role": "system",
                "content": (
                    "You are SAGE, an expert intelligence analyst specialising in "
                    "India's energy security, oil supply chain geopolitics, shipping, "
                    "and strategic petroleum reserves. "
                    "Write analytically, factually, and concisely. "
                    "Always wikilink tracked entities using [[Canonical Name]] syntax. "
                    "Focus on India's perspective: import dependency, corridor risks, "
                    "SPR adequacy, price shocks, and supplier diversification."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        body = await llm.generate(messages=messages)
        if not isinstance(body, str):
            body = str(body)
    except Exception as exc:
        log.warning("India brief LLM call failed: %s", exc)
        body = _fallback_body(context, now)

    return _wrap_page(body.strip(), context, now)


async def _gather_context() -> dict:
    """Pull live KB data: risk scores, recent signals, System 2/3/4 outputs."""
    ctx: dict = {
        "risk_scores": [],
        "recent_signals": [],
        "scenario": None,
        "procurement": None,
        "spr": None,
        "brent": None,
        "spr_coverage_pct": None,
        "threat_level": "LOW",
    }

    try:
        from knowledge.api.read import get_risk_scores, get_recent_intelligence
        scores = await get_risk_scores()
        ctx["risk_scores"] = [
            {"entity": s.entity, "score": round(s.score, 3), "band": s.band}
            for s in scores[:10]
        ]
        ctx["threat_level"] = (
            "CRITICAL" if any(s.score > 0.85 for s in scores) else
            "HIGH" if any(s.score > 0.65 for s in scores) else
            "MEDIUM" if any(s.score > 0.4 for s in scores) else "LOW"
        )

        signals = await get_recent_intelligence(limit=8)
        ctx["recent_signals"] = [
            {"source": s.source, "headline": s.headline, "url": s.source_url or ""}
            for s in signals
        ]
    except Exception as exc:
        log.debug("india_brief context: risk/intel failed: %s", exc)

    try:
        import redis.asyncio as aioredis, json, os
        r = aioredis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"))
        for key, field in [("scenario", "sage:scenario:latest"),
                            ("procurement", "sage:procurement:latest"),
                            ("spr", "sage:spr:latest")]:
            raw = await r.get(field)
            if raw:
                ctx[key] = json.loads(raw)
        await r.aclose()
    except Exception as exc:
        log.debug("india_brief context: redis failed: %s", exc)

    try:
        from knowledge.context.volatile import get_volatile
        ctx["brent"] = get_volatile("baseline_brent_usd_per_bbl", 95.0)
        ctx["spr_coverage_pct"] = get_volatile("spr_fill_fraction", 0.572) * 100
    except Exception as exc:
        log.debug("india_brief context: volatile failed: %s", exc)

    return ctx


def _build_prompt(ctx: dict, now: datetime) -> str:
    risk_lines = "\n".join(
        f"  - {r['entity']}: {r['band']} ({r['score']})"
        for r in ctx["risk_scores"]
    ) or "  - No entity risk scores yet"

    signal_lines = "\n".join(
        f"  - [{s['source'].upper()}] {s['headline']}"
        for s in ctx["recent_signals"]
    ) or "  - No recent signals"

    scenario_block = ""
    if ctx.get("scenario"):
        sc = ctx["scenario"]
        scenario_block = (
            f"\nSystem 2 Scenario Output:\n"
            f"  - Trigger: {sc.get('trigger_entity','?')}\n"
            f"  - Supply gap: {sc.get('gap_mbpd','?')} mbpd over {sc.get('duration_days','?')} days\n"
            f"  - Price impact: ${sc.get('price_impact_low','?')}–${sc.get('price_impact_high','?')}/bbl\n"
            f"  - SPR cover: {sc.get('spr_depletion_days','?')} days"
        )

    procurement_block = ""
    if ctx.get("procurement") and ctx["procurement"].get("ranked"):
        top = ctx["procurement"]["ranked"][0]
        procurement_block = (
            f"\nSystem 3 Procurement Recommendation:\n"
            f"  - Top alternative: {top.get('supplier','?')} ({top.get('grade','?')}) "
            f"via {top.get('route_via','?')}, TOPSIS score {top.get('topsis_score','?')}"
        )

    spr_block = ""
    if ctx.get("spr"):
        sp = ctx["spr"]
        spr_block = (
            f"\nSystem 4 SPR Recommendation:\n"
            f"  - Action: {sp.get('policy_memo','draw/maintain')[:120]}\n"
            f"  - Buffer probability: {round((sp.get('prob_above_buffer',0))*100,1)}%"
        )

    return f"""As of {now.strftime('%Y-%m-%d %H:%M UTC')}, write India's energy supply chain situation brief.

KEY FACTS:
  - Brent crude: ${ctx.get('brent', 95.0):.1f}/bbl
  - SPR coverage: {ctx.get('spr_coverage_pct', 57.2):.1f}%
  - India import dependence: ~88.6% of crude is imported
  - Hormuz share of Indian imports: ~42.5%
  - Overall threat level: {ctx['threat_level']}

ENTITY RISK SCORES (from live fusion):
{risk_lines}

RECENT LIVE SIGNALS (System 1):
{signal_lines}
{scenario_block}{procurement_block}{spr_block}

Write a structured Current Assessment in 3–5 paragraphs covering:
1. Current geopolitical situation affecting India's supply corridors
2. Key risk factors and complicating elements (sanctions, AIS anomalies, price moves)
3. India-specific vulnerability and exposure
4. Strategic outlook and what to watch

Be specific, cite entities with [[wikilinks]], and ground every claim in the data above.
Do NOT add section headers — write continuous prose paragraphs only.
Do NOT repeat "India" as the first word of every sentence.
End with one sentence on the most critical near-term watchpoint."""


def _wrap_page(body: str, ctx: dict, now: datetime) -> str:
    ts = now.isoformat()
    threat = ctx.get("threat_level", "LOW")
    risk_band = threat.lower()
    return f"""---
entity_id: india
aliases:
- India
- India Supply Chain
entity_type: Sovereign
tags:
- sage/india
- risk/{risk_band}
risk_score: {_threat_to_score(threat)}
last_updated: '{ts}'
valid_at: '{ts}'
auto_synthesized: true
---

## Current Assessment
{body}

## Key Metrics
- Brent crude: ${ctx.get('brent', 95.0):.1f}/bbl (EIA reference)
- SPR coverage: {ctx.get('spr_coverage_pct', 57.2):.1f}% of capacity
- Import dependence: 88.6% crude imported
- Hormuz share: 42.5% of imports transit [[Strait of Hormuz]]

## Signal Basis
{chr(10).join('- [' + s['source'].upper() + '] ' + s['headline'] + (' · ' + s['url'] if s.get('url') else '') for s in ctx.get('recent_signals', [])[:5])}

## Relations
| Relation | Entity | Type | Strength |
|---|---|---|---|
| primary_corridor | [[Strait of Hormuz]] | transit_dependency | critical |
| secondary_corridor | [[Bab-el-Mandeb]] | transit_dependency | high |
| major_refinery | [[Jamnagar Refinery]] | refinery_dependency | critical |
| strategic_reserve | [[India SPR]] | spr_dependency | high |
| top_supplier | [[Saudi Aramco]] | supply_dependency | high |
| top_supplier | [[ADNOC]] | supply_dependency | high |
"""


def _write_india_wiki(content: str) -> None:
    wiki_dir = os.environ.get("WIKI_DIR", "/app/wiki")
    path = os.path.join(wiki_dir, "india.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _threat_to_score(threat: str) -> float:
    return {"CRITICAL": 0.95, "HIGH": 0.75, "MEDIUM": 0.5, "LOW": 0.15}.get(threat, 0.15)


def _fallback_body(ctx: dict, now: datetime) -> str:
    threat = ctx.get("threat_level", "LOW")
    brent = ctx.get("brent", 95.0)
    spr = ctx.get("spr_coverage_pct", 57.2)
    recent = ctx.get("recent_signals", [])
    headlines = "; ".join(s["headline"][:80] for s in recent[:3]) if recent else "no recent signals"
    return (
        f"India's energy supply chain is currently assessed at {threat} threat level as of "
        f"{now.strftime('%Y-%m-%d %H:%M UTC')}. "
        f"Brent crude trades at ${brent:.1f}/bbl with SPR coverage at {spr:.1f}%. "
        f"[[Strait of Hormuz]] remains the primary chokepoint, handling ~42.5% of India's crude imports. "
        f"Recent signals: {headlines}. "
        f"System is monitoring all corridors and supplier nodes autonomously."
    )
