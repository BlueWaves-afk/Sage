"""
Write an Obsidian graph-view colour configuration for a SAGE wiki vault.

Obsidian colours graph nodes via "colour groups" — each a search query + colour —
stored in <vault>/.obsidian/graph.json. SAGE wiki pages carry `sage/<type>` and
`risk/<band>` tags (see knowledge/synthesis.py), so we key one colour group per
entity type. Node SIZE already encodes prominence in Obsidian (it scales with the
number of links), so a well-connected hub like Strait of Hormuz renders large.

Run:  python3.11 scripts/write_obsidian_graph_config.py [wiki_dir]
      (defaults to $WIKI_DIR or knowledge/wiki)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# entity type (lowercased tag) -> hex colour. Distinct, high-contrast palette.
PALETTE: dict[str, str] = {
    "corridor":        "E63946",  # red      — maritime chokepoints (highest strategic risk)
    "supplier":        "457B9D",  # blue     — crude exporters
    "refinery":        "2A9D8F",  # teal     — Indian refineries
    "crudegrade":      "9D4EDD",  # purple   — crude assays
    "port":            "00B4D8",  # cyan     — terminals
    "sprcavern":       "E9C46A",  # gold     — strategic reserves
    "authority":       "8D99AE",  # slate    — sanctions bodies
    "geoevent":        "F4A261",  # orange   — historical events
    "vessel":          "90BE6D",  # green    — tracked vessels (dynamic)
    "scenariooutput":  "FF5D8F",  # pink     — System 2 outputs (dynamic)
    "pendingscenario": "ADB5BD",  # grey     — speculative sandbox forks
}

# Base graph-view settings tuned for readability (node size = prominence via links).
BASE_SETTINGS = {
    "collapse-filter": False,
    "search": "",
    "showTags": False,          # don't render tag pills as their own nodes
    "showAttachments": False,
    "hideUnresolved": False,
    "showOrphans": True,
    "collapse-color-groups": False,
    "collapse-display": False,
    "showArrow": True,
    "textFadeMultiplier": 0.2,  # keep labels legible when zoomed out a little
    "nodeSizeMultiplier": 1.4,  # larger nodes; hubs (more links) grow further
    "lineSizeMultiplier": 1.0,
    "collapse-forces": True,
    "centerStrength": 0.52,
    "repelStrength": 12,
    "linkStrength": 1,
    "linkDistance": 250,
    "scale": 0.9,
    "close": False,
}


def _rgb_int(hex_colour: str) -> int:
    return int(hex_colour, 16)


def build_color_groups() -> list[dict]:
    return [
        {"query": f"tag:#sage/{t}", "color": {"a": 1, "rgb": _rgb_int(hx)}}
        for t, hx in PALETTE.items()
    ]


def write_config(wiki_dir: Path) -> Path:
    obsidian = wiki_dir / ".obsidian"
    obsidian.mkdir(parents=True, exist_ok=True)
    graph_path = obsidian / "graph.json"

    # Preserve any existing view geometry the user set (scale/center), override groups.
    settings = dict(BASE_SETTINGS)
    if graph_path.exists():
        try:
            existing = json.loads(graph_path.read_text())
            for k in ("scale", "centerStrength", "repelStrength", "linkDistance"):
                if k in existing:
                    settings[k] = existing[k]
        except Exception:
            pass

    settings["colorGroups"] = build_color_groups()
    graph_path.write_text(json.dumps(settings, indent=2))
    return graph_path


if __name__ == "__main__":
    wiki = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(os.environ.get("WIKI_DIR", "knowledge/wiki"))
    path = write_config(wiki)
    print(f"Wrote {path} with {len(PALETTE)} entity-type colour groups:")
    for t, hx in PALETTE.items():
        print(f"  #{hx}  sage/{t}")
