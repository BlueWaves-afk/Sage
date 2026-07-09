"""
System 1 — Sensory Agent runner.

Launches all four sub-agents as concurrent asyncio tasks.
This is the entry point for the sensory agent container(s).

Usage:
    python -m sensory_agent.runner              # run all 4 sub-agents
    python -m sensory_agent.runner prices       # run only prices
    python -m sensory_agent.runner news         # run only news/GDELT
    python -m sensory_agent.runner sanctions    # run only sanctions
    python -m sensory_agent.runner ais          # run only AIS
"""
from __future__ import annotations

import asyncio
import logging
import sys

log = logging.getLogger("sensory_agent")


async def run_all() -> None:
    """Launch all four sub-agents concurrently."""
    from sensory_agent import prices, news, sanctions, ais

    log.info("=" * 60)
    log.info("System 1 — Sensory Agent starting (all sub-agents)")
    log.info("=" * 60)

    tasks = [
        asyncio.create_task(prices.run(), name="prices"),
        asyncio.create_task(news.run(), name="news"),
        asyncio.create_task(sanctions.run(), name="sanctions"),
        asyncio.create_task(ais.run(), name="ais"),
    ]

    # If any sub-agent crashes, log it but keep others running
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
    for task in done:
        if task.exception():
            log.error(
                "Sub-agent '%s' crashed: %s", task.get_name(), task.exception()
            )
            # Restart the crashed agent
            agent_name = task.get_name()
            log.info("Restarting sub-agent '%s'...", agent_name)
            module = {"prices": prices, "news": news,
                      "sanctions": sanctions, "ais": ais}[agent_name]
            new_task = asyncio.create_task(module.run(), name=agent_name)
            pending.add(new_task)

    # Wait for remaining
    if pending:
        await asyncio.wait(pending)


async def run_single(agent_name: str) -> None:
    """Launch a single sub-agent by name."""
    agents = {
        "prices": "sensory_agent.prices",
        "news": "sensory_agent.news",
        "sanctions": "sensory_agent.sanctions",
        "ais": "sensory_agent.ais",
    }

    if agent_name not in agents:
        print(f"Unknown agent: {agent_name}")
        print(f"Available: {', '.join(agents.keys())}")
        sys.exit(1)

    log.info("System 1 — starting single sub-agent: %s", agent_name)

    import importlib
    module = importlib.import_module(agents[agent_name])
    await module.run()


def main() -> None:
    """CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)-20s | %(levelname)-5s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if len(sys.argv) > 1:
        agent_name = sys.argv[1].lower().strip()
        asyncio.run(run_single(agent_name))
    else:
        asyncio.run(run_all())


if __name__ == "__main__":
    main()
