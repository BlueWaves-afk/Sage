"""
GDELT / News sub-agent using newsdata.io API.

Uses the newsdata.io API (latest, market, crypto endpoints) to fetch
energy/geopolitical news. Runs HuggingFace multilingual sentiment analysis
for tone/severity extraction. Resolves entities via the SAGE registry
and discards articles with no tracked entity match.

Payload contract (fusion reads these exact keys):
    tone         — float, negative = hostile (from sentiment model)
    tone_delta   — float, change from rolling average
    severity     — float 0–1, higher = more risk (from sentiment model)
    actor        — str, primary actor extracted from article
    action       — str, primary action/event type

Data sources:
    - newsdata.io Latest News API (every 15 min)
    - newsdata.io Market News API (every 15 min)
    - GDELT 2.0 event stream (every 15 min, free, no key)
"""
from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import os
import re
import urllib.request
import urllib.parse
from collections import defaultdict
from datetime import datetime, timezone
from zipfile import ZipFile

from contracts.signal import NormalizedSignal
from knowledge.registry import resolve_name, canonical_name
from sensory_agent._base import emit, new_signal_id, utcnow

log = logging.getLogger(__name__)

POLL_INTERVAL_S = int(os.environ.get("NEWS_POLL_INTERVAL_S", "900"))  # 15 min

# G10 — Hybrid LLM extraction budget guard
NEWS_LLM_BUDGET_PER_H = int(os.environ.get("NEWS_LLM_BUDGET_PER_H", "10"))

# ── newsdata.io API ──────────────────────────────────────────────────────────

NEWSDATA_API_KEY = os.environ.get("NEWSDATA_API_KEY", "")  # set in .env.local (gitignored)
NEWSDATA_BASE = "https://newsdata.io/api/1"

# Energy/geopolitics keywords for newsdata.io search
NEWS_KEYWORDS = [
    "oil supply chain India",
    "Strait of Hormuz",
    "crude oil India import",
    "OPEC production",
    "energy sanctions",
    "oil tanker attack",
    "Brent crude price",
    "Red Sea shipping",
    "Iran oil sanctions",
    "Russia oil embargo",
    "India refinery",
    "Houthi attack shipping",
    "LNG India",
]

# Rolling tone history for delta computation
_tone_history: dict[str, list[float]] = defaultdict(list)
_seen_article_ids: set[str] = set()   # dedup within session


# ── Sentiment model (lazy import) ────────────────────────────────────────────

def _get_sentiment():
    """Lazy import sentiment module to avoid loading the model at import time."""
    from sensory_agent.sentiment import predict_sentiment, sentiment_to_severity, predict_tone
    return predict_sentiment, sentiment_to_severity, predict_tone


# ── Entity extraction (keyword-based + registry matching) ────────────────────

def _extract_entities(text: str) -> list[str]:
    """
    Extract entity references from article text by matching against
    the SAGE registry. Returns list of canonical names.

    This is a registry-scan approach: for each known alias, check if
    it appears in the text. Faster than LLM extraction and guaranteed
    to produce registry-valid refs.
    """
    from knowledge.registry import ALIAS_TO_ENTITY, REGISTRY

    text_lower = text.lower()
    matched_ids = set()

    for alias, entity_id in ALIAS_TO_ENTITY.items():
        # Only check aliases with 3+ chars to avoid false positives
        if len(alias) >= 3 and alias in text_lower:
            matched_ids.add(entity_id)

    return [canonical_name(eid) for eid in matched_ids]


async def _llm_extract_entities(text: str, redis_client=None) -> list[str]:
    """
    G10: Conditional Nova Micro extraction when alias-scan returns nothing and
    severity is high. Budget-guarded: max NEWS_LLM_BUDGET_PER_H calls/hour via
    Redis counter `news:llm_calls:YYYYMMDDHH`.
    """
    try:
        import redis as _redis
        from datetime import timezone as _tz

        # Budget check
        budget_key = f"news:llm_calls:{datetime.now(tz=timezone.utc).strftime('%Y%m%d%H')}"
        if redis_client is None:
            redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
            redis_client = _redis.from_url(redis_url, decode_responses=True)
        count = int(redis_client.get(budget_key) or 0)
        if count >= NEWS_LLM_BUDGET_PER_H:
            log.debug("[news] LLM budget exhausted (%d/%d this hour)", count, NEWS_LLM_BUDGET_PER_H)
            return []

        from knowledge.bedrock import BedrockLLM
        llm = BedrockLLM()
        prompt = (
            "You are an energy supply-chain analyst. Extract entity names from the article "
            "that relate to oil suppliers, maritime corridors, refineries, or geopolitical "
            "actors affecting India's crude supply. Output only a JSON array of entity names, "
            "e.g. [\"Saudi Aramco\", \"Strait of Hormuz\"]. If none, output [].\n\n"
            f"Article: {text[:600]}"
        )
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: llm.chat([{"role": "user", "content": prompt}],
                             model_id="amazon.nova-micro-v1:0", n_tokens=150),
        )

        # Increment budget counter (TTL 3700s ≈ slightly over 1 hour)
        redis_client.incr(budget_key)
        redis_client.expire(budget_key, 3700)

        # Parse response
        raw = response.strip() if isinstance(response, str) else ""
        import json as _json
        start = raw.find("[")
        end = raw.rfind("]")
        if start == -1 or end == -1:
            return []
        names = _json.loads(raw[start:end + 1])
        # Resolve via registry
        resolved = []
        for name in names:
            cn = resolve_name(name)
            if cn:
                resolved.append(cn)
        if resolved:
            log.info("[news] LLM extracted %d entities from high-severity article", len(resolved))
        return resolved

    except Exception as exc:
        log.debug("[news] LLM extraction failed: %s", exc)
        return []


def _extract_actor_action(text: str) -> tuple[str, str]:
    """
    Simple actor/action extraction from headline or first sentence.
    Returns (actor, action) strings.
    """
    # Take first sentence
    first_sentence = text.split(".")[0].strip() if text else ""

    # Common energy-sector actors
    actors = [
        "Iran", "IRGC", "Houthi", "Saudi Arabia", "Aramco", "OPEC",
        "Russia", "Rosneft", "India", "ONGC", "IOCL", "Reliance",
        "US", "United States", "EU", "China", "Venezuela", "PDVSA",
        "Iraq", "Kuwait", "UAE", "ADNOC", "Qatar", "Nigeria",
    ]

    actor = "unknown"
    for a in actors:
        if a.lower() in first_sentence.lower():
            actor = a
            break

    # Common action keywords
    action_keywords = {
        "sanction": "sanctions_action",
        "attack": "military_attack",
        "seize": "vessel_seizure",
        "block": "blockade",
        "cut": "production_cut",
        "increase": "production_increase",
        "export": "export_change",
        "import": "import_change",
        "price": "price_movement",
        "oil": "oil_market",
        "tanker": "tanker_incident",
        "pipeline": "pipeline_event",
        "refinery": "refinery_event",
        "ship": "shipping_event",
        "missile": "military_attack",
        "drone": "military_attack",
        "nuclear": "nuclear_event",
        "negotiate": "diplomacy",
        "treaty": "diplomacy",
        "embargo": "embargo",
    }

    action = "general"
    for keyword, act in action_keywords.items():
        if keyword in first_sentence.lower():
            action = act
            break

    return actor, action


# ── newsdata.io fetching ─────────────────────────────────────────────────────

async def _fetch_newsdata(endpoint: str, params: dict) -> list[dict]:
    """
    Fetch articles from newsdata.io API endpoint.
    Returns list of article dicts.
    """
    params["apikey"] = NEWSDATA_API_KEY
    url = f"{NEWSDATA_BASE}/{endpoint}?{urllib.parse.urlencode(params)}"

    try:
        loop = asyncio.get_event_loop()
        req = urllib.request.Request(url, headers={
            "User-Agent": "SAGE-System1/1.0",
        })
        response = await loop.run_in_executor(
            None,
            lambda: urllib.request.urlopen(req, timeout=30),
        )
        data = json.loads(response.read().decode("utf-8"))

        if data.get("status") == "success":
            return data.get("results", [])
        else:
            log.warning("newsdata.io %s error: %s", endpoint, data.get("message", "unknown"))
            return []

    except Exception as exc:
        log.error("newsdata.io fetch error (%s): %s", endpoint, exc)
        return []


async def _poll_newsdata_latest() -> list[NormalizedSignal]:
    """
    Fetch latest energy/geopolitics news from newsdata.io.
    Uses rotating keywords to maximize coverage.
    """
    predict_sentiment, sentiment_to_severity, predict_tone = _get_sentiment()
    signals = []

    # Rotate through keyword groups to stay within rate limits
    for keyword in NEWS_KEYWORDS[:3]:  # 3 queries per poll cycle
        articles = await _fetch_newsdata("latest", {
            "q": keyword,
            "language": "en",
            "category": "business,politics,world",
        })

        for article in articles:
            article_id = article.get("article_id", "")
            if article_id in _seen_article_ids:
                continue
            _seen_article_ids.add(article_id)

            title = article.get("title", "")
            description = article.get("description", "") or ""
            content = article.get("content", "") or ""
            text = f"{title}. {description}. {content}"[:2000]
            url = article.get("link", "")
            pub_date = article.get("pubDate")

            # Parse publication date
            observed_at = utcnow()
            if pub_date:
                try:
                    observed_at = datetime.fromisoformat(
                        pub_date.replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    pass

            # Sentiment analysis first so we can use severity for LLM gate
            tone = predict_tone(title)
            severity = sentiment_to_severity(
                predict_sentiment(title)[0]
            )

            # Entity resolution — alias-scan fast path, LLM fallback for high severity
            refs = _extract_entities(text)
            if not refs:
                if severity >= 0.7:
                    # G10: escalate to Nova Micro only when no alias matched and risk is high
                    refs = await _llm_extract_entities(text)
                if not refs:
                    continue  # no tracked entity → discard

            # Actor/action extraction
            actor, action = _extract_actor_action(text)

            # Tone delta (change from rolling average)
            primary_entity = refs[0]
            _tone_history[primary_entity].append(tone)
            hist = _tone_history[primary_entity]
            if len(hist) > 20:
                _tone_history[primary_entity] = hist[-20:]
            tone_delta = tone - (sum(hist[:-1]) / len(hist[:-1])) if len(hist) > 1 else 0.0

            signal = NormalizedSignal(
                signal_id=new_signal_id("news"),
                source="news",
                observed_at=observed_at,
                ingested_at=utcnow(),
                priority_hint="HIGH" if severity > 0.6 else "MED",
                force_synthesis=False,   # let triage similarity-gate decide
                entity_refs=refs,
                summary=title[:200] if title else "News article",
                payload={
                    "actor": actor,
                    "action": action,
                    "tone": tone,
                    "gdelt_tone": tone,
                    "severity": round(severity, 4),
                    "tone_delta": round(tone_delta, 4),
                },
                source_url=url,
            )
            signals.append(signal)

    # Keep dedup set bounded
    if len(_seen_article_ids) > 5000:
        _seen_article_ids.clear()

    return signals


async def _poll_newsdata_market() -> list[NormalizedSignal]:
    """
    Fetch market news from newsdata.io market endpoint.
    Good for commodity price movement news.
    """
    predict_sentiment, sentiment_to_severity, predict_tone = _get_sentiment()
    signals = []

    articles = await _fetch_newsdata("market", {
        "q": "crude oil OR brent OR energy",
        "language": "en",
    })

    for article in articles:
        article_id = article.get("article_id", "")
        if article_id in _seen_article_ids:
            continue
        _seen_article_ids.add(article_id)

        title = article.get("title", "")
        description = article.get("description", "") or ""
        text = f"{title}. {description}"[:1500]
        url = article.get("link", "")

        refs = _extract_entities(text)
        if not refs:
            continue

        tone = predict_tone(title)
        severity = sentiment_to_severity(predict_sentiment(title)[0])
        actor, action = _extract_actor_action(text)

        primary_entity = refs[0]
        _tone_history[primary_entity].append(tone)

        signal = NormalizedSignal(
            signal_id=new_signal_id("news"),
            source="news",
            observed_at=utcnow(),
            ingested_at=utcnow(),
            priority_hint="HIGH" if severity > 0.6 else "MED",
            force_synthesis=False,
            entity_refs=refs,
            summary=title[:200] if title else "Market news",
            payload={
                "actor": actor,
                "action": action,
                "tone": tone,
                "gdelt_tone": tone,
                "severity": round(severity, 4),
                "tone_delta": 0.0,
            },
            source_url=url,
        )
        signals.append(signal)

    return signals


# ── GDELT 2.0 polling ───────────────────────────────────────────────────────

GDELT_LAST_UPDATE_URL = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"

# GDELT event columns (V2 format) — we need a subset
GDELT_COLS = {
    "actor1_name": 6,
    "actor2_name": 16,
    "event_code": 26,
    "goldstein": 30,
    "num_mentions": 31,
    "avg_tone": 34,
    "actor1_geo_lat": 39,
    "actor1_geo_long": 40,
    "source_url": 57,
}


async def _poll_gdelt() -> list[NormalizedSignal]:
    """
    Fetch GDELT 2.0 15-minute event update.
    Filters for energy/conflict events and extracts tone/severity.
    """
    predict_sentiment, sentiment_to_severity, predict_tone = _get_sentiment()
    signals = []

    try:
        loop = asyncio.get_event_loop()
        # Get latest update URL
        req = urllib.request.Request(GDELT_LAST_UPDATE_URL)
        resp = await loop.run_in_executor(
            None,
            lambda: urllib.request.urlopen(req, timeout=15),
        )
        lines = resp.read().decode("utf-8").strip().split("\n")

        # First line is the export file (events)
        if not lines:
            return []

        parts = lines[0].strip().split()
        if len(parts) < 3:
            return []

        csv_url = parts[2]  # URL to the zip file

        # Download and extract the CSV
        req = urllib.request.Request(csv_url)
        resp = await loop.run_in_executor(
            None,
            lambda: urllib.request.urlopen(req, timeout=30),
        )
        zip_data = resp.read()

        # Parse the zip
        zip_buf = io.BytesIO(zip_data)
        with ZipFile(zip_buf) as zf:
            csv_filename = zf.namelist()[0]
            csv_data = zf.read(csv_filename).decode("utf-8", errors="replace")

        # Parse CSV (tab-separated, no header)
        reader = csv.reader(io.StringIO(csv_data), delimiter="\t")
        for row in reader:
            if len(row) < 58:
                continue

            actor1 = row[GDELT_COLS["actor1_name"]] if row[GDELT_COLS["actor1_name"]] else ""
            actor2 = row[GDELT_COLS["actor2_name"]] if row[GDELT_COLS["actor2_name"]] else ""
            goldstein = float(row[GDELT_COLS["goldstein"]]) if row[GDELT_COLS["goldstein"]] else 0.0
            avg_tone = float(row[GDELT_COLS["avg_tone"]]) if row[GDELT_COLS["avg_tone"]] else 0.0
            source_url = row[GDELT_COLS["source_url"]] if len(row) > 57 else ""

            # Filter: only keep high-conflict events (negative Goldstein)
            if goldstein > -2.0:
                continue

            # Entity resolution
            text = f"{actor1} {actor2}"
            refs = _extract_entities(text)
            if not refs:
                continue

            severity = min(1.0, max(0.0, abs(goldstein) / 10.0))

            primary_entity = refs[0]
            _tone_history[primary_entity].append(avg_tone)
            hist = _tone_history[primary_entity]
            tone_delta = avg_tone - (sum(hist[:-1]) / len(hist[:-1])) if len(hist) > 1 else 0.0

            signal = NormalizedSignal(
                signal_id=new_signal_id("gdelt"),
                source="gdelt",
                observed_at=utcnow(),
                ingested_at=utcnow(),
                priority_hint="HIGH" if severity > 0.6 else "MED",
                force_synthesis=False,
                entity_refs=refs,
                summary=f"GDELT: {actor1} → {actor2}, Goldstein={goldstein:.1f}, tone={avg_tone:.1f}",
                payload={
                    "actor": actor1,
                    "action": f"GDELT event (Goldstein={goldstein:.1f})",
                    "tone": avg_tone,
                    "gdelt_tone": avg_tone,
                    "severity": round(severity, 4),
                    "tone_delta": round(tone_delta, 4),
                },
                source_url=source_url,
            )
            signals.append(signal)

            # Limit to avoid flooding
            if len(signals) >= 20:
                break

    except Exception as exc:
        log.error("GDELT fetch error: %s", exc)

    return signals


async def run() -> None:
    """
    Entry point. Polls newsdata.io and GDELT every 15 minutes.
    Uses HuggingFace sentiment model for tone/severity extraction.
    Discards articles with no tracked entity match.
    """
    log.info(
        "News/GDELT sub-agent started. Interval=%ds, newsdata_key=%s...",
        POLL_INTERVAL_S,
        NEWSDATA_API_KEY[:10] if NEWSDATA_API_KEY else "MISSING",
    )

    # Pre-load the sentiment model
    try:
        _get_sentiment()
        log.info("Sentiment model pre-loaded successfully")
    except Exception as exc:
        log.warning("Sentiment model pre-load failed: %s — will retry on first use", exc)

    while True:
        try:
            # Fetch from all sources in parallel
            results = await asyncio.gather(
                _poll_newsdata_latest(),
                _poll_newsdata_market(),
                _poll_gdelt(),
                return_exceptions=True,
            )

            total = 0
            for result in results:
                if isinstance(result, Exception):
                    log.error("News source error: %s", result)
                    continue
                for signal in result:
                    await emit(signal)
                    total += 1

            log.info("News cycle complete: %d signals emitted", total)

        except Exception as exc:
            log.error("News poll error: %s", exc)

        await asyncio.sleep(POLL_INTERVAL_S)
