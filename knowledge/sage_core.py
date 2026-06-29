"""
SAGE core process entrypoint.

Runs the ingest consumer loop and risk monitor as concurrent async tasks.
This is the long-lived process in the sage-core container.

Usage:
  python -m knowledge.sage_core
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("sage_core")


async def main() -> None:
    log.info("SAGE core starting (LLM_PROVIDER=%s)", os.environ.get("LLM_PROVIDER", "stub"))

    # 1. Init knowledge base
    from knowledge.connection import init as kb_init
    await kb_init()
    log.info("Knowledge base ready.")

    # 2. Start ingest consumer + risk monitor concurrently
    from knowledge.ingest_queue import run_consumer_loop
    from orchestration.monitor import run_monitor

    tasks = await asyncio.gather(
        asyncio.create_task(run_consumer_loop(), name="ingest_consumer"),
        asyncio.create_task(run_monitor(), name="risk_monitor"),
        return_exceptions=True,
    )
    for t in tasks:
        if isinstance(t, Exception):
            log.error("Task failed: %s", t)


def _handle_sigterm(*_):
    log.info("SIGTERM received — shutting down.")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _handle_sigterm)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Interrupted.")
