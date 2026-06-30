#!/usr/bin/env python3
"""
fetch_sources — populate a context bundle's sources/ evidence layer.

Reads <bundle>/sources_index.csv  (columns: entity_id, url, note)  and fetches
each URL, concatenating the readable text per entity into
<bundle>/sources/<entity_id>.md  with provenance headers.

These cached source files are the EVIDENCE that bundle.instantiate() grounds the
LLM narratives on (RAG) — the model summarises this real text, it does not write
from parametric memory. Caching keeps instantiation reproducible and offline, and
survives link-rot.

Usage:
  python scripts/fetch_sources.py data/india-energy-2026.context
  python scripts/fetch_sources.py data/india-energy-2026.context --only corridor_hormuz

Note: this is a best-effort stdlib fetcher (some sites block bots / need JS). For
those, paste the article text into sources/<entity_id>.md manually — the loader
treats any text there as the grounding evidence regardless of how it got there.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

_TAG = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
_HTML = re.compile(r"<[^>]+>")
_WS = re.compile(r"\n\s*\n\s*\n+")


def _strip_html(html: str) -> str:
    html = _TAG.sub(" ", html)
    text = _HTML.sub(" ", html)
    text = re.sub(r"[ \t]+", " ", text)
    return _WS.sub("\n\n", text).strip()


def _fetch(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "SAGE-context-fetcher/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
    return _strip_html(raw)[:8000]   # cap per source to keep prompts bounded


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch a bundle's source evidence.")
    ap.add_argument("bundle")
    ap.add_argument("--only", help="fetch only this entity_id")
    args = ap.parse_args()

    bundle = Path(args.bundle)
    index = bundle / "sources_index.csv"
    if not index.exists():
        print(f"✗ no sources_index.csv in {bundle}")
        return 2

    src_dir = bundle / "sources"
    src_dir.mkdir(exist_ok=True)

    by_entity: dict[str, list[dict]] = defaultdict(list)
    with index.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            by_entity[row["entity_id"]].append(row)

    for entity_id, rows in by_entity.items():
        if args.only and entity_id != args.only:
            continue
        chunks = [f"# Source evidence — {entity_id}\n"
                  f"_Fetched {datetime.now(timezone.utc).date()}. Provenance for grounded synthesis._\n"]
        for row in rows:
            url = row["url"]
            try:
                text = _fetch(url)
                chunks.append(f"\n## Source: {url}\n_{row.get('note','')}_\n\n{text}\n")
                print(f"  ✓ {entity_id}  ←  {url[:60]}")
            except Exception as exc:
                chunks.append(f"\n## Source: {url}  (FETCH FAILED: {exc})\n_{row.get('note','')}_\n")
                print(f"  ✗ {entity_id}  ←  {url[:60]}  ({exc})")
        (src_dir / f"{entity_id}.md").write_text("\n".join(chunks), encoding="utf-8")

    print(f"done → {src_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
