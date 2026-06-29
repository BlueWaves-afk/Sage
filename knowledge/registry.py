"""
Canonical entity registry — single source of truth for entity identity.

Resolves the two-layer entity-resolution problem:
  Layer 1 (wiki routing): entity_refs attached by detector → wiki slug
  Layer 2 (graph routing): Graphiti anchors to canonical_name in episode text

Three pre-built lookup indices:
  H3_TO_ENTITY         AIS detector: cell → entity_id
  INSTRUMENT_TO_ENTITIES  Price detector: instrument → [entity_id, ...]
  ALIAS_TO_ENTITY      Sanctions/news: free-form name → entity_id

Four resolver functions used by sub-agents and synthesis:
  resolve_h3(cell)           → entity_id | None
  resolve_instrument(instr)  → [entity_id, ...]
  resolve_name(name)         → entity_id | None
  canonical_name(entity_id)  → display_name str
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EntityRegistryEntry:
    entity_id:      str
    entity_type:    str           # C2 type — exactly one of the 11 schema types
    canonical_name: str           # exact string used in wiki files and Graphiti episodes
    aliases:        list[str] = field(default_factory=list)
    h3_cells:       list[str] = field(default_factory=list)   # AIS routing (Corridor/Port)
    instruments:    list[str] = field(default_factory=list)   # price routing
    coordinates:    dict     = field(default_factory=dict)    # lat/lon


REGISTRY: dict[str, EntityRegistryEntry] = {

    # ── Corridors ──────────────────────────────────────────────────────────────

    "corridor_hormuz": EntityRegistryEntry(
        entity_id="corridor_hormuz",
        entity_type="Corridor",
        canonical_name="Strait of Hormuz",
        aliases=["Hormuz", "Hormuz Strait", "the Strait", "SoH",
                 "Strait of Hormuz", "Persian Gulf entrance"],
        h3_cells=[
            "8a2a1072b59ffff",   # Larak Island area
            "8a2a1072b4fffff",   # Hormuz mouth north
            "8a2a10728b7ffff",   # Hormuz mouth south
            "8a2a1072897ffff",
            "8a2a10728b3ffff",
        ],
        instruments=["BZ=F", "CL=F"],
        coordinates={"lat": 26.5, "lon": 56.4},
    ),

    "corridor_bab_el_mandeb": EntityRegistryEntry(
        entity_id="corridor_bab_el_mandeb",
        entity_type="Corridor",
        canonical_name="Bab-el-Mandeb",
        aliases=["Bab el Mandeb", "BAM", "Red Sea Strait", "Mandeb",
                 "Bab-al-Mandab", "Gate of Grief"],
        h3_cells=[
            "8a2a4d64b0fffff",
            "8a2a4d64b27ffff",
        ],
        instruments=["BZ=F"],
        coordinates={"lat": 12.5, "lon": 43.3},
    ),

    "corridor_suez": EntityRegistryEntry(
        entity_id="corridor_suez",
        entity_type="Corridor",
        canonical_name="Suez Canal",
        aliases=["Suez", "the Canal", "SUMED", "Suez Canal Authority", "SCA"],
        h3_cells=[
            "8a3900000007fff",
            "8a39000000b7fff",
        ],
        coordinates={"lat": 30.7, "lon": 32.3},
    ),

    "corridor_malacca": EntityRegistryEntry(
        entity_id="corridor_malacca",
        entity_type="Corridor",
        canonical_name="Strait of Malacca",
        aliases=["Malacca", "Malacca Strait", "Strait of Malacca"],
        h3_cells=[
            "8a600001d83ffff",
            "8a600001da7ffff",
        ],
        coordinates={"lat": 2.5, "lon": 102.0},
    ),

    # ── Suppliers ──────────────────────────────────────────────────────────────

    "supplier_aramco": EntityRegistryEntry(
        entity_id="supplier_aramco",
        entity_type="Supplier",
        canonical_name="Saudi Aramco",
        aliases=["Aramco", "Saudi Arabian Oil Company", "Aramco Trading",
                 "Saudi Aramco Trading", "SAOC"],
    ),

    "supplier_nioc": EntityRegistryEntry(
        entity_id="supplier_nioc",
        entity_type="Supplier",
        canonical_name="NIOC",
        aliases=["National Iranian Oil Company", "Iran National Oil",
                 "NIOC Trading", "Iranian oil", "Iran NOC"],
    ),

    "supplier_adnoc": EntityRegistryEntry(
        entity_id="supplier_adnoc",
        entity_type="Supplier",
        canonical_name="ADNOC",
        aliases=["Abu Dhabi National Oil Company", "Abu Dhabi NOC",
                 "ADNOC Distribution", "ADNOC Trading"],
    ),

    "supplier_rosneft": EntityRegistryEntry(
        entity_id="supplier_rosneft",
        entity_type="Supplier",
        canonical_name="Rosneft",
        aliases=["Rosneft Oil", "PJSC Rosneft", "Rosneftegas",
                 "Russian oil Rosneft"],
    ),

    "supplier_iraqoil": EntityRegistryEntry(
        entity_id="supplier_iraqoil",
        entity_type="Supplier",
        canonical_name="Iraqi Oil Ministry",
        aliases=["SOMO", "State Organisation for Marketing of Oil",
                 "Iraq oil", "Iraq NOC", "Iraqi NOC", "INOC"],
    ),

    # ── Refineries ─────────────────────────────────────────────────────────────

    "refinery_jamnagar": EntityRegistryEntry(
        entity_id="refinery_jamnagar",
        entity_type="Refinery",
        canonical_name="Jamnagar Refinery",
        aliases=["Jamnagar", "Reliance Jamnagar", "RIL Jamnagar",
                 "Reliance Industries Jamnagar", "DTA Jamnagar"],
        coordinates={"lat": 22.47, "lon": 70.07},
    ),

    "refinery_mangaluru": EntityRegistryEntry(
        entity_id="refinery_mangaluru",
        entity_type="Refinery",
        canonical_name="Mangaluru",
        aliases=["MRPL Mangaluru", "Mangalore Refinery", "MRPL",
                 "Mangalore Refinery and Petrochemicals", "HPCL-Mittal Mangaluru"],
        coordinates={"lat": 12.91, "lon": 74.84},
    ),

    "refinery_paradip": EntityRegistryEntry(
        entity_id="refinery_paradip",
        entity_type="Refinery",
        canonical_name="Paradip",
        aliases=["IOCL Paradip", "Paradip Refinery", "IOC Paradip",
                 "Indian Oil Paradip"],
        coordinates={"lat": 20.31, "lon": 86.69},
    ),

    # ── Ports ──────────────────────────────────────────────────────────────────

    "port_vadinar": EntityRegistryEntry(
        entity_id="port_vadinar",
        entity_type="Port",
        canonical_name="Vadinar",
        aliases=["Vadinar Port", "Vadinar Terminal", "Reliance Vadinar",
                 "Sikka-Vadinar", "Vadinar Oil Terminal"],
        coordinates={"lat": 22.47, "lon": 69.77},
    ),

    "port_yanbu": EntityRegistryEntry(
        entity_id="port_yanbu",
        entity_type="Port",
        canonical_name="Yanbu",
        aliases=["Yanbu Terminal", "Yanbu Al Bahr", "Yanbu port",
                 "Yanbu Industrial City", "Yanbu al-Bahr"],
        coordinates={"lat": 24.09, "lon": 38.05},
    ),

    "port_sikka": EntityRegistryEntry(
        entity_id="port_sikka",
        entity_type="Port",
        canonical_name="Sikka",
        aliases=["Sikka Port", "Sikka Terminal", "IOCL Sikka",
                 "Kandla Sikka"],
        coordinates={"lat": 22.60, "lon": 69.87},
    ),

    "port_fujairah": EntityRegistryEntry(
        entity_id="port_fujairah",
        entity_type="Port",
        canonical_name="Fujairah",
        aliases=["Port of Fujairah", "Fujairah Terminal",
                 "Fujairah Anchorage", "FOIZ"],
        coordinates={"lat": 25.11, "lon": 56.34},
    ),

    # ── SPR Caverns ────────────────────────────────────────────────────────────

    "spr_vizag": EntityRegistryEntry(
        entity_id="spr_vizag",
        entity_type="SPRCavern",
        canonical_name="Vizag SPR",
        aliases=["Visakhapatnam SPR", "Vizag cavern", "ISPRL Vizag",
                 "Visakhapatnam cavern", "Vishakhapatnam SPR"],
        coordinates={"lat": 17.69, "lon": 83.28},
    ),

    "spr_mangaluru": EntityRegistryEntry(
        entity_id="spr_mangaluru",
        entity_type="SPRCavern",
        canonical_name="Mangaluru SPR",
        aliases=["Padur SPR Mangaluru", "ISPRL Mangaluru", "Mangalore SPR",
                 "Mangaluru cavern"],
        coordinates={"lat": 12.91, "lon": 74.84},
    ),

    "spr_padur": EntityRegistryEntry(
        entity_id="spr_padur",
        entity_type="SPRCavern",
        canonical_name="Padur SPR",
        aliases=["Padur cavern", "ISPRL Padur", "Padur storage",
                 "Udupi Padur SPR"],
        coordinates={"lat": 13.06, "lon": 74.68},
    ),

    # ── Authorities ────────────────────────────────────────────────────────────

    "authority_ofac": EntityRegistryEntry(
        entity_id="authority_ofac",
        entity_type="Authority",
        canonical_name="OFAC",
        aliases=["US Treasury OFAC", "Office of Foreign Assets Control",
                 "Treasury SDN", "US sanctions", "OFAC SDN"],
    ),

    "authority_eu": EntityRegistryEntry(
        entity_id="authority_eu",
        entity_type="Authority",
        canonical_name="EU",
        aliases=["European Union", "EU sanctions", "Council of the EU",
                 "European Council sanctions", "EU restrictive measures"],
    ),

    "authority_un": EntityRegistryEntry(
        entity_id="authority_un",
        entity_type="Authority",
        canonical_name="UN",
        aliases=["United Nations", "UN Security Council", "UNSC",
                 "United Nations sanctions"],
    ),
}


# ── Lookup indices (built once at module load) ──────────────────────────────────

H3_TO_ENTITY: dict[str, str] = {
    cell: entry.entity_id
    for entry in REGISTRY.values()
    for cell in entry.h3_cells
}

INSTRUMENT_TO_ENTITIES: dict[str, list[str]] = {}
for _entry in REGISTRY.values():
    for _inst in _entry.instruments:
        INSTRUMENT_TO_ENTITIES.setdefault(_inst, []).append(_entry.entity_id)

# Alias lookup: normalized lowercase → entity_id
ALIAS_TO_ENTITY: dict[str, str] = {}
for _entry in REGISTRY.values():
    for _alias in [_entry.canonical_name] + _entry.aliases:
        ALIAS_TO_ENTITY[_alias.lower()] = _entry.entity_id


# ── Resolver functions ──────────────────────────────────────────────────────────

def resolve_h3(h3_cell: str) -> str | None:
    """AIS detector: H3 cell → entity_id, or None if cell not tracked."""
    return H3_TO_ENTITY.get(h3_cell)


def resolve_instrument(instrument: str) -> list[str]:
    """Price detector: instrument ticker → [entity_id, ...] affected."""
    return INSTRUMENT_TO_ENTITIES.get(instrument, [])


def resolve_name(name: str) -> str | None:
    """
    Resolve a free-form name (alias, abbreviation, variant) to entity_id.
    Used by sanctions and news sub-agents. Case-insensitive.
    Returns None if not in registry — caller decides new-entity policy.
    """
    return ALIAS_TO_ENTITY.get(name.strip().lower())


def canonical_name(entity_id: str) -> str:
    """
    Return the canonical display name for an entity_id.
    This is the exact string used as [[wikilink]] text and as the first
    token of every Graphiti episode body — both resolution layers anchor to it.
    Raises KeyError if entity_id is not in the registry.
    """
    return REGISTRY[entity_id].canonical_name


def entity_type(entity_id: str) -> str:
    """Return the C2 entity type for an entity_id."""
    return REGISTRY[entity_id].entity_type


def coordinates(entity_id: str) -> dict:
    """Return lat/lon coordinates dict for an entity_id (may be empty dict)."""
    return REGISTRY[entity_id].coordinates


def entity_id_from_display(display_name: str) -> str | None:
    """
    Reverse lookup: canonical display name or alias → entity_id.
    Equivalent to resolve_name but named for clarity at call sites that
    already have a display name (not a user-supplied free-form string).
    """
    return ALIAS_TO_ENTITY.get(display_name.strip().lower())


def register_vessel(
    mmsi: str,
    vessel_name: str,
    operator_entity_id: str | None = None,
    imo: str | None = None,
) -> str:
    """
    Register a newly-sanctioned vessel at runtime.
    Called by the sanctions sub-agent when a vessel not in the registry appears.
    Returns the new entity_id.
    """
    entity_id = f"vessel_{mmsi}"
    aliases = [vessel_name, mmsi]
    if imo:
        aliases.append(imo)

    entry = EntityRegistryEntry(
        entity_id=entity_id,
        entity_type="Vessel",
        canonical_name=vessel_name,
        aliases=aliases,
    )
    REGISTRY[entity_id] = entry
    for alias in aliases:
        ALIAS_TO_ENTITY[alias.lower()] = entity_id

    return entity_id


def build_registry_excerpt() -> str:
    """
    Compact list of all canonical entity names for injection into synthesis prompt.
    Tells the LLM exactly which names to use as [[wikilink]] text.
    """
    lines = ["Tracked entities (use [[Canonical Name]] exactly as shown):"]
    by_type: dict[str, list[EntityRegistryEntry]] = {}
    for entry in REGISTRY.values():
        by_type.setdefault(entry.entity_type, []).append(entry)
    for etype in sorted(by_type):
        lines.append(f"\n{etype}:")
        for e in by_type[etype]:
            lines.append(f"  [[{e.canonical_name}]]  (id: {e.entity_id})")
    return "\n".join(lines)
