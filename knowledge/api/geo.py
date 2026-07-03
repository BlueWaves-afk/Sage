"""
Geospatial positioning for the knowledge graph — gives EVERY entity a lat/lon so
the graph can be drawn on a map (the "Obsidian graph, but geographic" view).

Coordinate source, in priority order:
  1. Registry `coordinates` — the authoritative source for physical assets
     (Corridors, Ports, Refineries, SPR caverns). 22 entities carry real coords.
  2. Supplier country → representative oil-hub coordinate (this module).
  3. CrudeGrade → its origin country's coordinate, with a small deterministic
     offset so grades cluster around (not on top of) their producer.
  4. Authority → real HQ coordinate (OFAC/EU/UN/G7).
  5. GeoEvent → anchored to the corridor/region it concerns.

Positions are derived deterministically (no randomness) so the map is stable
across reloads. Non-physical nodes still sit at a sensible real-world place, so
edges read as genuine supply-chain arcs rather than an abstract force layout.
"""
from __future__ import annotations

import hashlib

# Representative oil-hub coordinate per producing country (not the capital —
# the point a viewer associates with that country's crude exports).
COUNTRY_COORDS: dict[str, dict[str, float]] = {
    "Saudi Arabia":         {"lat": 25.36, "lon": 49.59},  # Ghawar / Dhahran
    "Iraq":                 {"lat": 30.51, "lon": 47.78},  # Basrah
    "United Arab Emirates": {"lat": 24.47, "lon": 54.37},  # Abu Dhabi
    "Russia":               {"lat": 55.75, "lon": 37.62},  # Moscow
    "Iran":                 {"lat": 29.61, "lon": 50.83},  # Kharg / Bushehr
    "Kuwait":               {"lat": 29.34, "lon": 47.68},  # Kuwait City
    "Qatar":                {"lat": 25.29, "lon": 51.53},  # Doha
    "Nigeria":              {"lat": 4.77,  "lon": 7.01},   # Bonny / Port Harcourt
    "United States":        {"lat": 29.76, "lon": -95.37}, # Houston
    "Brazil":               {"lat": -22.9, "lon": -43.17}, # Rio / Santos basin
    "Venezuela":            {"lat": 10.5,  "lon": -66.9},  # Caracas
    "Kazakhstan":           {"lat": 47.12, "lon": 51.88},  # Atyrau
    "Angola":               {"lat": -8.84, "lon": 13.23},  # Luanda
}

# Sanctions / governance authority headquarters.
AUTHORITY_COORDS: dict[str, dict[str, float]] = {
    "OFAC": {"lat": 38.90, "lon": -77.04},  # US Treasury, Washington DC
    "EU":   {"lat": 50.85, "lon": 4.35},    # Brussels
    "UN":   {"lat": 40.75, "lon": -73.97},  # New York
    "G7 Price Cap Coalition": {"lat": 51.51, "lon": -0.13},  # London (proxy)
}

# GeoEvents anchored to the region they concern.
EVENT_COORDS: dict[str, dict[str, float]] = {
    "2019 Tanker Attacks":        {"lat": 25.6, "lon": 56.9},
    "2024 Red Sea Crisis":        {"lat": 14.5, "lon": 42.5},
    "Ever Given Suez Blockage":   {"lat": 30.02, "lon": 32.58},
    "2025 Iran-Israel Conflict":  {"lat": 27.0, "lon": 55.5},
    "2022 Russia-Ukraine War":    {"lat": 49.0, "lon": 37.0},
    "Tanker War":                 {"lat": 27.5, "lon": 51.5},
}


def _offset(seed: str, spread: float = 1.6) -> tuple[float, float]:
    """Deterministic small lat/lon jitter derived from an entity id/name."""
    h = hashlib.md5(seed.encode()).digest()
    dx = (h[0] / 255.0 - 0.5) * 2 * spread
    dy = (h[1] / 255.0 - 0.5) * 2 * spread
    return dy, dx


def resolve_coordinates(
    name: str,
    entity_type: str,
    country: str | None = None,
    origin: str | None = None,
    registry_coords: dict | None = None,
) -> dict[str, float] | None:
    """
    Return {'lat','lon'} for an entity, or None if it genuinely cannot be placed.
    `registry_coords` (if present) always wins — it's the physical truth.
    """
    if registry_coords and "lat" in registry_coords and "lon" in registry_coords:
        return {"lat": float(registry_coords["lat"]), "lon": float(registry_coords["lon"])}

    t = entity_type.lower()

    if t == "supplier":
        base = COUNTRY_COORDS.get(country or "") or COUNTRY_COORDS.get(name)
        return dict(base) if base else None

    if t == "crudegrade":
        base = COUNTRY_COORDS.get(origin or "")
        if not base:
            return None
        dlat, dlon = _offset(name, spread=2.2)
        return {"lat": base["lat"] + dlat, "lon": base["lon"] + dlon}

    if t == "authority":
        base = AUTHORITY_COORDS.get(name)
        return dict(base) if base else None

    if t == "geoevent":
        base = EVENT_COORDS.get(name)
        return dict(base) if base else None

    return None
