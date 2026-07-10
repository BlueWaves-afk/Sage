#!/usr/bin/env python3
"""
sage-instantiate — load a SAGE context bundle into the knowledge base.

This is the SAGE.from_pretrained() step: it reads a provenance-tracked .context
bundle and writes its foundational knowledge into all three stores —
  • graph + vector  (FalkorDB, via Graphiti)   → knowledge/graph_store
  • wiki            (Obsidian-format markdown)  → knowledge/wiki

Two phases run automatically:
  1. FACTS      structured ground truth → graph attributes (deterministic)
  2. NARRATIVES per-entity prose → synthesis path → wiki + reconciled episodes
                (hand-authored .md, or LLM-authored with Nova Pro, or a stub)

Usage:
  # from the host, against the dockerised FalkorDB, using Bedrock for synthesis
  FALKORDB_HOST=localhost LLM_PROVIDER=bedrock \\
    python scripts/sage_instantiate.py data/india-energy-2026.context

  python scripts/sage_instantiate.py BUNDLE [--no-llm-author] [--facts-only]
"""
from __future__ import annotations

import argparse
import asyncio
import itertools
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env / .env.local so LLM_PROVIDER (bedrock) + AWS creds are set — otherwise
# the KB falls back to the STUB LLM which writes episodes but extracts NO entities.
try:
    from config_env import load_local_env
    load_local_env()
except Exception:
    pass

_SPIN = itertools.cycle("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")
_PHASE_LABEL = {
    "facts":          "facts    ",
    "synthesizing":   "Nova Pro ",
    "narrative":      "wiki     ",
    "canonicalizing": "dedup    ",
}


def _render(phase: str, name: str, i: int, total: int) -> None:
    """Live single-line progress loader."""
    bar_w = 24
    filled = int(bar_w * i / max(total, 1))
    bar = "█" * filled + "·" * (bar_w - filled)
    label = _PHASE_LABEL.get(phase, phase)
    spin = next(_SPIN)
    line = f"\r  {spin} {label} [{bar}] {i:>2}/{total:<2}  {name[:46]:<46}"
    sys.stdout.write(line)
    sys.stdout.flush()


async def main() -> int:
    ap = argparse.ArgumentParser(description="Instantiate SAGE from a context bundle.")
    ap.add_argument("bundle", nargs="?", default=os.environ.get(
        "SAGE_CONTEXT_BUNDLE", "data/india-energy-2026.context"),
        help="Path to the .context bundle directory")
    ap.add_argument("--no-llm-author", action="store_true",
        help="Use deterministic stubs for entities without a hand-authored narrative "
             "(default: author them with Nova Pro when LLM_PROVIDER=bedrock/openai)")
    ap.add_argument("--facts-only", action="store_true",
        help="Load only the facts layer; skip narratives/wiki")
    args = ap.parse_args()

    provider = os.environ.get("LLM_PROVIDER", "stub").lower()
    use_llm = (not args.no_llm_author) and provider in ("bedrock", "openai")

    print("─" * 72)
    print(f"  SAGE · instantiate foundational knowledge")
    print(f"  bundle   : {args.bundle}")
    print(f"  provider : {provider}   (LLM-authored narratives: {'on' if use_llm else 'off'})")
    print(f"  wiki     : {os.environ.get('WIKI_DIR', 'knowledge/wiki')}")
    print(f"  falkordb : {os.environ.get('FALKORDB_HOST', 'falkordb')}:{os.environ.get('FALKORDB_PORT','6379')}")
    print("─" * 72)

    from knowledge.context import load_bundle, BundleValidationError
    try:
        bundle = load_bundle(args.bundle)
    except BundleValidationError as e:
        print(f"✗ bundle validation failed:\n{e}")
        return 2

    s = bundle.summary()
    print(f"  ✓ validated  {s['bundle_id']} (schema {s['schema']})")
    print(f"    nodes={sum(s['nodes'].values())}  edges={sum(s['edges'].values())}  "
          f"narratives={s['narratives']}  tiers={s['by_tier']}")
    print("─" * 72)

    print("  initialising knowledge base (FalkorDB + Graphiti)…")
    from knowledge.connection import init as kb_init
    g = await kb_init()

    t0 = time.monotonic()
    if args.facts_only:
        eps = bundle.to_episodes()
        from graphiti_core.nodes import EpisodeType
        from knowledge.schema.entities import ENTITY_TYPES
        from knowledge.schema.edges import EDGE_TYPES, EDGE_TYPE_MAP
        for i, ep in enumerate(eps, 1):
            _render("facts", ep["name"], i, len(eps))
            await g.add_episode(name=ep["name"], episode_body=ep["body"],
                source=EpisodeType.text, source_description=ep["source_desc"],
                entity_types=ENTITY_TYPES, edge_types=EDGE_TYPES, edge_type_map=EDGE_TYPE_MAP)
        counts = {"facts": len(eps), "narratives": 0}
    else:
        counts = await bundle.instantiate(g, author_missing_with_llm=use_llm, on_progress=_render)

    dt = time.monotonic() - t0
    sys.stdout.write("\r" + " " * 90 + "\r")   # clear loader line
    print(f"  ✓ instantiated in {dt:.1f}s")
    print(f"    facts episodes   : {counts['facts']}")
    print(f"    narrative pages  : {counts['narratives']}  (wiki store + reconciled episodes)")
    if counts.get("edges_removed") or counts.get("nodes_merged"):
        print(f"    canonicalized    : −{counts.get('edges_removed',0)} dup edges, "
              f"−{counts.get('nodes_merged',0)} alias nodes merged")
    print("─" * 72)

    # Quick read-back so the user sees the growing memory
    try:
        from knowledge.synthesis import list_wiki_entities
        from knowledge.api.read import get_risk_scores
        wikis = list_wiki_entities()
        print(f"  wiki pages on disk : {len(wikis)}  →  {os.environ.get('WIKI_DIR','knowledge/wiki')}/")
        scores = await get_risk_scores()
        print(f"  graph risk states  : {len(scores)} entities")
    except Exception as exc:
        print(f"  (read-back skipped: {exc})")
    print("─" * 72)
    print("  done. Inspect the memory:")
    print("    • wiki  : open knowledge/wiki/ as an Obsidian vault")
    print("    • graph : http://localhost:3000  (FalkorDB browser)")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
