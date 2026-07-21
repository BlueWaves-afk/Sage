from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import redis.asyncio as aioredis

from contracts.signal import NormalizedSignal


_RECENT_KEY = "sage:intelligence:recent"
_RETENTION_DAYS = 5


async def record_signal(signal: NormalizedSignal, origin: str = "live") -> None:
    client = aioredis.from_url(
        os.environ.get("REDIS_URL", "redis://redis:6379/0"), decode_responses=True
    )
    payload = json.dumps(
        {
            "id": signal.signal_id,
            "source": signal.source,
            "headline": signal.summary,
            "detail": signal.summary,
            "source_url": signal.source_url or "",
            "recorded_at": signal.observed_at.isoformat(),
            "origin": origin,
        },
        sort_keys=True,
    )
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=_RETENTION_DAYS)).timestamp()
        async with client.pipeline(transaction=False) as pipeline:
            pipeline.zadd(_RECENT_KEY, {payload: signal.observed_at.timestamp()})
            pipeline.zremrangebyscore(_RECENT_KEY, "-inf", cutoff)
            await pipeline.execute()
    finally:
        await client.aclose()


async def read_recent_signals(limit: int) -> list[dict]:
    tenant_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    global_url = os.environ.get("SAGE_GLOBAL_REDIS_URL", "redis://redis:6379/0")
    urls = list(dict.fromkeys([tenant_url, global_url]))
    rows: list[str] = []
    for redis_url in urls:
        client = aioredis.from_url(redis_url, decode_responses=True)
        try:
            rows.extend(
                await client.zrevrange(_RECENT_KEY, 0, max(limit * 3, limit) - 1)
            )
        finally:
            await client.aclose()
    decoded = [json.loads(row) for row in set(rows)]
    decoded.sort(key=lambda item: str(item.get("recorded_at") or ""), reverse=True)
    return decoded[: max(limit * 3, limit)]
