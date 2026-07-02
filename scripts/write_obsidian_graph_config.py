"""
Write an Obsidian graph-view colour configuration for a SAGE wiki vault.

Obsidian colours graph nodes via "colour groups" — each a search query + colour —
stored in <vault>/.obsidian/graph.json. SAGE wiki pages carry `sage/<type>` and
`risk/<band>` tags (see knowledge/synthesis.py), so we key one colour group per
entity type. Node SIZE already encodes prominence in Obsidian (it scales with the
number of links), so a well-connected hub like Strait of Hormuz renders large.

Run:  python3.11 scripts/write_obsidian_graph_config.py [wiki_dir] [--mode risk|type]
      mode defaults to "risk" (the standard SAGE view); "type" colours by entity type.
      wiki_dir defaults to $WIKI_DIR or knowledge/wiki.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# ── STANDARD view: colour by RISK BAND (traffic-light escalation gradient) ──────
# Keyed on the risk/<band> tag. All nodes start calm (green) on a fresh instantiation
# and shift toward red as System 1 raises RISK_STATE — so the graph IS the risk map.
RISK_PALETTE: dict[str, str] = {
    "calm":     "2A9D8F",  # green      — nominal
    "watch":    "E9C46A",  # gold       — early signals
    "elevated": "F4A261",  # orange     — sandbox/elevated band
    "action":   "E76F51",  # red-orange — action band (threshold crossed)
    "critical": "E63946",  # red        — critical band (human escalation)
}

# ── Alternate view: colour by ENTITY TYPE ──────────────────────────────────────
TYPE_PALETTE: dict[str, str] = {
    "corridor":        "E63946",  # red      — maritime chokepoints
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

# Tag namespace per mode. `risk` is the standard.
_MODES = {
    "risk": ("risk", RISK_PALETTE),
    "type": ("sage", TYPE_PALETTE),
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


def build_color_groups(mode: str = "risk") -> list[dict]:
    ns, palette = _MODES[mode]
    return [
        {"query": f"tag:#{ns}/{k}", "color": {"a": 1, "rgb": _rgb_int(hx)}}
        for k, hx in palette.items()
    ]


def write_config(wiki_dir: Path, mode: str = "risk") -> Path:
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

    settings["colorGroups"] = build_color_groups(mode)
    graph_path.write_text(json.dumps(settings, indent=2))
    return graph_path


def _parse_mode(argv: list[str]) -> str:
    """--mode risk|type (or bare --type). Defaults to risk (the standard)."""
    if "--type" in argv:
        return "type"
    if "--mode" in argv:
        i = argv.index("--mode")
        if i + 1 < len(argv) and argv[i + 1] in _MODES:
            return argv[i + 1]
    return "risk"


if __name__ == "__main__":
    positional = [a for a in sys.argv[1:] if not a.startswith("--") and a not in _MODES]
    mode = _parse_mode(sys.argv[1:])
    wiki = Path(positional[0]) if positional else Path(os.environ.get("WIKI_DIR", "knowledge/wiki"))
    path = write_config(wiki, mode)
    ns, palette = _MODES[mode]
    print(f"Wrote {path} — STANDARD view = {mode.upper()} ({len(palette)} colour groups):")
    for k, hx in palette.items():
        print(f"  #{hx}  {ns}/{k}")
