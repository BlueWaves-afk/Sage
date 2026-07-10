"""
Static scenario preset library for the Simulation Lab.

Presets encode the canonical entity names (verified against registry.py) and the
parameter bundles that seed the builder. The POST /api/scenario/run endpoint
validates `entity` against KNOWN_ENTITIES before dispatching the runner.
"""
from __future__ import annotations

PRESETS: list[dict] = [
    {
        "id": "hormuz_full",
        "label": "Strait of Hormuz — Full Closure",
        "entity": "Strait of Hormuz",
        "disruption_fraction": 1.0,
        "disruption_days": 21,
        "escalation_profile": "constant",
        "bypass_compromised_frac": 0.0,
        "spr_policy": "aggressive",
        "demand_destruction_pct": 0.05,
        "blurb": "Complete Hormuz blockage; ~20% of global seaborne crude halted.",
    },
    {
        "id": "hormuz_partial",
        "label": "Hormuz — Contained Confrontation",
        "entity": "Strait of Hormuz",
        "disruption_fraction": 0.4,
        "disruption_days": 10,
        "escalation_profile": "escalating",
        "bypass_compromised_frac": 0.0,
        "spr_policy": "moderate",
        "demand_destruction_pct": 0.0,
        "blurb": "Partial closure / harassment; insurance + rerouting friction.",
    },
    {
        "id": "redsea_hormuz",
        "label": "Red Sea + Hormuz — Bypass Compromised",
        "entity": "Strait of Hormuz",
        "disruption_fraction": 0.7,
        "disruption_days": 18,
        "escalation_profile": "constant",
        "bypass_compromised_frac": 1.0,
        "spr_policy": "aggressive",
        "demand_destruction_pct": 0.05,
        "blurb": "Simultaneous chokepoint stress removes the Petroline/ADCOP bypass relief.",
    },
    {
        "id": "supplier_sanction",
        "label": "Major Supplier Sanctioned",
        "entity": "Strait of Hormuz",
        "disruption_fraction": 0.3,
        "disruption_days": 45,
        "escalation_profile": "constant",
        "bypass_compromised_frac": 0.0,
        "spr_policy": "moderate",
        "demand_destruction_pct": 0.0,
        "blurb": "Long-duration sourcing loss; procurement substitution dominates.",
    },
]

# Entities the runner accepts — validated against registry canonical names.
KNOWN_ENTITIES: set[str] = {
    "Strait of Hormuz",
    "Bab-el-Mandeb",
    "Suez Canal",
    "Strait of Malacca",
    "Cape of Good Hope",
}


def validate_entity(entity: str) -> bool:
    return entity in KNOWN_ENTITIES
