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

    # ── Expansion: additional suppliers (India's wider sourcing) ─────────────────

    "supplier_kpc": EntityRegistryEntry(
        entity_id="supplier_kpc", entity_type="Supplier",
        canonical_name="Kuwait Petroleum Corporation",
        aliases=["KPC", "Kuwait Petroleum", "Kuwait", "KOC"],
    ),
    "supplier_qatarenergy": EntityRegistryEntry(
        entity_id="supplier_qatarenergy", entity_type="Supplier",
        canonical_name="QatarEnergy",
        aliases=["Qatar Petroleum", "QatarEnergy", "Qatar", "QP"],
    ),
    "supplier_nnpc": EntityRegistryEntry(
        entity_id="supplier_nnpc", entity_type="Supplier",
        canonical_name="NNPC",
        aliases=["Nigerian National Petroleum", "Nigeria", "NNPC Limited"],
    ),

    # ── Expansion: additional Indian refineries ──────────────────────────────────

    "refinery_panipat": EntityRegistryEntry(
        entity_id="refinery_panipat", entity_type="Refinery",
        canonical_name="Panipat",
        aliases=["IOCL Panipat", "Panipat Refinery", "Indian Oil Panipat"],
        coordinates={"lat": 29.39, "lon": 76.97},
    ),
    "refinery_kochi": EntityRegistryEntry(
        entity_id="refinery_kochi", entity_type="Refinery",
        canonical_name="Kochi",
        aliases=["BPCL Kochi", "Kochi Refinery", "Cochin Refinery", "BPCL Kochi Refinery"],
        coordinates={"lat": 9.97, "lon": 76.28},
    ),

    # ── Expansion: additional corridor ───────────────────────────────────────────

    "corridor_cape": EntityRegistryEntry(
        entity_id="corridor_cape", entity_type="Corridor",
        canonical_name="Cape of Good Hope",
        aliases=["Cape route", "Cape of Good Hope", "Cape passage", "around Africa"],
        coordinates={"lat": -34.36, "lon": 18.47},
    ),

    # ── Historical / geopolitical events (GeoEvent nodes) ────────────────────────

    "event_tanker_war": EntityRegistryEntry(
        entity_id="event_tanker_war", entity_type="GeoEvent",
        canonical_name="Tanker War",
        aliases=["Iran-Iraq Tanker War", "1980s Tanker War"],
    ),
    "event_2019_hormuz_attacks": EntityRegistryEntry(
        entity_id="event_2019_hormuz_attacks", entity_type="GeoEvent",
        canonical_name="2019 Tanker Attacks",
        aliases=["2019 Gulf of Oman attacks", "2019 tanker attacks", "Fujairah attacks"],
    ),
    "event_2024_red_sea": EntityRegistryEntry(
        entity_id="event_2024_red_sea", entity_type="GeoEvent",
        canonical_name="2024 Red Sea Crisis",
        aliases=["Houthi Red Sea attacks", "Red Sea shipping crisis", "Bab-el-Mandeb crisis"],
    ),
    "event_ever_given": EntityRegistryEntry(
        entity_id="event_ever_given", entity_type="GeoEvent",
        canonical_name="Ever Given Suez Blockage",
        aliases=["Ever Given", "Suez Canal blockage 2021", "Ever Given grounding"],
    ),
    "event_2025_iran_israel": EntityRegistryEntry(
        entity_id="event_2025_iran_israel", entity_type="GeoEvent",
        canonical_name="2025 Iran-Israel Conflict",
        aliases=["2025 Iran Israel war", "June 2025 Iran-Israel conflict"],
    ),

    # ── Expansion v2: broader supplier / refinery / port / event coverage ───────

    "supplier_us": EntityRegistryEntry(
        entity_id="supplier_us", entity_type="Supplier",
        canonical_name="United States",
        aliases=["US crude exporters", "USA", "American crude", "US oil"],
    ),
    "supplier_petrobras": EntityRegistryEntry(
        entity_id="supplier_petrobras", entity_type="Supplier",
        canonical_name="Petrobras",
        aliases=["Brazil", "Brazilian oil", "Petroleo Brasileiro"],
    ),
    "supplier_pdvsa": EntityRegistryEntry(
        entity_id="supplier_pdvsa", entity_type="Supplier",
        canonical_name="PDVSA",
        aliases=["Venezuela", "Petroleos de Venezuela", "Venezuelan oil"],
    ),
    "supplier_kazmunaygas": EntityRegistryEntry(
        entity_id="supplier_kazmunaygas", entity_type="Supplier",
        canonical_name="KazMunayGas",
        aliases=["Kazakhstan", "Kazakh oil", "KMG"],
    ),
    "supplier_sonangol": EntityRegistryEntry(
        entity_id="supplier_sonangol", entity_type="Supplier",
        canonical_name="Sonangol",
        aliases=["Angola", "Angolan oil"],
    ),

    "refinery_nayara": EntityRegistryEntry(
        entity_id="refinery_nayara", entity_type="Refinery",
        canonical_name="Vadinar Refinery",
        aliases=["Nayara Energy", "Nayara", "Essar Oil Vadinar", "Vadinar refinery"],
        coordinates={"lat": 22.28, "lon": 69.73},
    ),
    "refinery_visakh": EntityRegistryEntry(
        entity_id="refinery_visakh", entity_type="Refinery",
        canonical_name="Visakhapatnam Refinery",
        aliases=["HPCL Visakhapatnam", "Vizag Refinery", "HPCL Vizag"],
        coordinates={"lat": 17.69, "lon": 83.22},
    ),
    "refinery_chennai": EntityRegistryEntry(
        entity_id="refinery_chennai", entity_type="Refinery",
        canonical_name="Chennai Refinery",
        aliases=["CPCL", "Chennai Petroleum", "Manali Refinery"],
        coordinates={"lat": 13.16, "lon": 80.26},
    ),

    "port_mundra": EntityRegistryEntry(
        entity_id="port_mundra", entity_type="Port",
        canonical_name="Mundra",
        aliases=["Mundra Port", "Adani Mundra", "Mundra terminal"],
        coordinates={"lat": 22.74, "lon": 69.70},
    ),
    "port_paradip": EntityRegistryEntry(
        entity_id="port_paradip", entity_type="Port",
        canonical_name="Paradip Port",
        aliases=["Paradip terminal", "Paradip harbour"],
        coordinates={"lat": 20.26, "lon": 86.67},
    ),

    "authority_g7": EntityRegistryEntry(
        entity_id="authority_g7", entity_type="Authority",
        canonical_name="G7 Price Cap Coalition",
        aliases=["G7", "G7 price cap", "Price Cap Coalition", "oil price cap"],
    ),

    "event_russia_ukraine_2022": EntityRegistryEntry(
        entity_id="event_russia_ukraine_2022", entity_type="GeoEvent",
        canonical_name="2022 Russia-Ukraine War",
        aliases=["Russian invasion of Ukraine", "Ukraine war", "2022 Russia sanctions"],
    ),

    # ── G7 ProductionField nodes (wellheads) ─────────────────────────────────────
    # Upstream production fields that feed into the supply chain. output_mbpd and
    # spare_mbpd are public EIA/OPEC data.

    "field_ghawar": EntityRegistryEntry(
        entity_id="field_ghawar", entity_type="ProductionField",
        canonical_name="Ghawar Field",
        aliases=["Ghawar", "Ghawar oil field", "Saudi Ghawar"],
        coordinates={"lat": 25.1, "lon": 49.8},
    ),
    "field_rumaila": EntityRegistryEntry(
        entity_id="field_rumaila", entity_type="ProductionField",
        canonical_name="Rumaila Field",
        aliases=["Rumaila", "Rumaila oil field", "Iraq Rumaila"],
        coordinates={"lat": 30.0, "lon": 47.5},
    ),
    "field_upper_zakum": EntityRegistryEntry(
        entity_id="field_upper_zakum", entity_type="ProductionField",
        canonical_name="Upper Zakum",
        aliases=["Upper Zakum", "Zakum field", "ADNOC Zakum"],
        coordinates={"lat": 24.8, "lon": 53.5},
    ),
    "field_khurais": EntityRegistryEntry(
        entity_id="field_khurais", entity_type="ProductionField",
        canonical_name="Khurais Complex",
        aliases=["Khurais", "Khurais oil field"],
        coordinates={"lat": 25.1, "lon": 48.4},
    ),
    "field_west_qurna": EntityRegistryEntry(
        entity_id="field_west_qurna", entity_type="ProductionField",
        canonical_name="West Qurna",
        aliases=["West Qurna", "WQ-1", "WQ-2", "West Qurna Iraq"],
        coordinates={"lat": 30.8, "lon": 47.7},
    ),
    "field_safaniya": EntityRegistryEntry(
        entity_id="field_safaniya", entity_type="ProductionField",
        canonical_name="Safaniya Field",
        aliases=["Safaniya", "Safaniya offshore", "Saudi Safaniya"],
        coordinates={"lat": 27.8, "lon": 48.8},
    ),
    "field_zakum_lower": EntityRegistryEntry(
        entity_id="field_zakum_lower", entity_type="ProductionField",
        canonical_name="Lower Zakum",
        aliases=["Lower Zakum", "Umm Shaif Zakum"],
        coordinates={"lat": 24.1, "lon": 53.0},
    ),
    "field_basra": EntityRegistryEntry(
        entity_id="field_basra", entity_type="ProductionField",
        canonical_name="Basra Fields",
        aliases=["Basra crude fields", "South Iraq fields", "Basra"],
        coordinates={"lat": 30.5, "lon": 47.8},
    ),
    "field_kirkuk": EntityRegistryEntry(
        entity_id="field_kirkuk", entity_type="ProductionField",
        canonical_name="Kirkuk Field",
        aliases=["Kirkuk", "Kirkuk crude", "North Iraq Kirkuk"],
        coordinates={"lat": 35.5, "lon": 44.4},
    ),
    "field_tengiz": EntityRegistryEntry(
        entity_id="field_tengiz", entity_type="ProductionField",
        canonical_name="Tengiz Field",
        aliases=["Tengiz", "Tengizchevroil", "Kazakhstan Tengiz"],
        coordinates={"lat": 45.5, "lon": 53.0},
    ),

    # ── G7 DistributionHub nodes (India state-level demand) ───────────────────────
    # State-level crude demand hubs based on PPAC state consumption data.

    "hub_gujarat": EntityRegistryEntry(
        entity_id="hub_gujarat", entity_type="DistributionHub",
        canonical_name="Gujarat Hub",
        aliases=["Gujarat distribution", "Gujarat refineries hub", "Jamnagar area"],
        coordinates={"lat": 22.5, "lon": 70.5},
    ),
    "hub_maharashtra": EntityRegistryEntry(
        entity_id="hub_maharashtra", entity_type="DistributionHub",
        canonical_name="Maharashtra Hub",
        aliases=["Maharashtra distribution", "Mumbai hub", "Ratnagiri hub"],
        coordinates={"lat": 19.0, "lon": 73.5},
    ),
    "hub_karnataka": EntityRegistryEntry(
        entity_id="hub_karnataka", entity_type="DistributionHub",
        canonical_name="Karnataka Hub",
        aliases=["Karnataka distribution", "Mangaluru hub", "Bangalore region"],
        coordinates={"lat": 13.0, "lon": 75.5},
    ),
    "hub_tamilnadu": EntityRegistryEntry(
        entity_id="hub_tamilnadu", entity_type="DistributionHub",
        canonical_name="Tamil Nadu Hub",
        aliases=["Tamil Nadu distribution", "Chennai hub", "CPCL region"],
        coordinates={"lat": 13.1, "lon": 80.2},
    ),
    "hub_andhra": EntityRegistryEntry(
        entity_id="hub_andhra", entity_type="DistributionHub",
        canonical_name="Andhra Pradesh Hub",
        aliases=["Andhra distribution", "Vizag hub", "HPCL Vizag region"],
        coordinates={"lat": 17.7, "lon": 83.2},
    ),
    "hub_odisha": EntityRegistryEntry(
        entity_id="hub_odisha", entity_type="DistributionHub",
        canonical_name="Odisha Hub",
        aliases=["Odisha distribution", "Paradip hub", "IOCL Paradip region"],
        coordinates={"lat": 20.3, "lon": 86.7},
    ),
    "hub_up_north": EntityRegistryEntry(
        entity_id="hub_up_north", entity_type="DistributionHub",
        canonical_name="North India Hub",
        aliases=["North India distribution", "UP hub", "Panipat region"],
        coordinates={"lat": 28.7, "lon": 77.2},
    ),
    "hub_haryana_punjab": EntityRegistryEntry(
        entity_id="hub_haryana_punjab", entity_type="DistributionHub",
        canonical_name="Haryana-Punjab Hub",
        aliases=["Punjab Haryana hub", "Bathinda distribution", "Northwest India hub"],
        coordinates={"lat": 30.2, "lon": 74.9},
    ),

    # ── Crude Grades ─────────────────────────────────────────────────────────────
    # No H3 cells / instruments — grades are referenced by name in news/sanctions
    # text and configured on refineries via CONFIGURED_FOR edges. Assays in docs/data.md §4.

    "grade_arab_light": EntityRegistryEntry(
        entity_id="grade_arab_light",
        entity_type="CrudeGrade",
        canonical_name="Arab Light",
        aliases=["Arabian Light", "AL crude", "Saudi Arab Light"],
    ),

    "grade_arab_medium": EntityRegistryEntry(
        entity_id="grade_arab_medium",
        entity_type="CrudeGrade",
        canonical_name="Arab Medium",
        aliases=["Arabian Medium", "AM crude"],
    ),

    "grade_arab_heavy": EntityRegistryEntry(
        entity_id="grade_arab_heavy",
        entity_type="CrudeGrade",
        canonical_name="Arab Heavy",
        aliases=["Arabian Heavy", "Safaniya"],
    ),

    "grade_arab_xlight": EntityRegistryEntry(
        entity_id="grade_arab_xlight",
        entity_type="CrudeGrade",
        canonical_name="Arab Extra Light",
        aliases=["Arabian Extra Light", "AXL", "Berri"],
    ),

    "grade_basrah_medium": EntityRegistryEntry(
        entity_id="grade_basrah_medium",
        entity_type="CrudeGrade",
        canonical_name="Basrah Medium",
        aliases=["Basra Medium", "Basrah Light", "Basra Light"],
    ),

    "grade_basrah_heavy": EntityRegistryEntry(
        entity_id="grade_basrah_heavy",
        entity_type="CrudeGrade",
        canonical_name="Basrah Heavy",
        aliases=["Basra Heavy"],
    ),

    "grade_urals": EntityRegistryEntry(
        entity_id="grade_urals",
        entity_type="CrudeGrade",
        canonical_name="Urals",
        aliases=["Russian Urals", "Urals blend", "REBCO"],
    ),

    "grade_murban": EntityRegistryEntry(
        entity_id="grade_murban",
        entity_type="CrudeGrade",
        canonical_name="Murban",
        aliases=["ADNOC Murban", "Murban crude"],
    ),

    "grade_bonny_light": EntityRegistryEntry(
        entity_id="grade_bonny_light",
        entity_type="CrudeGrade",
        canonical_name="Bonny Light",
        aliases=["Nigerian Bonny Light", "Bonny"],
    ),

    "grade_kuwait_export": EntityRegistryEntry(
        entity_id="grade_kuwait_export",
        entity_type="CrudeGrade",
        canonical_name="Kuwait Export Crude",
        aliases=["KEC", "Kuwait Export", "Kuwait Blend"],
    ),

    "grade_qatar_marine": EntityRegistryEntry(
        entity_id="grade_qatar_marine",
        entity_type="CrudeGrade",
        canonical_name="Qatar Marine",
        aliases=["Qatar Marine crude", "Marine crude"],
    ),

    "grade_wti_midland": EntityRegistryEntry(
        entity_id="grade_wti_midland", entity_type="CrudeGrade",
        canonical_name="WTI Midland",
        aliases=["WTI", "West Texas Intermediate", "WTI Midland crude"],
    ),
    "grade_tupi": EntityRegistryEntry(
        entity_id="grade_tupi", entity_type="CrudeGrade",
        canonical_name="Tupi",
        aliases=["Lula", "Tupi crude", "Brazilian Tupi"],
    ),
    "grade_merey": EntityRegistryEntry(
        entity_id="grade_merey", entity_type="CrudeGrade",
        canonical_name="Merey",
        aliases=["Merey 16", "Venezuelan Merey"],
    ),
    "grade_cpc_blend": EntityRegistryEntry(
        entity_id="grade_cpc_blend", entity_type="CrudeGrade",
        canonical_name="CPC Blend",
        aliases=["CPC", "Caspian Pipeline Consortium blend", "Tengiz"],
    ),
    "grade_cabinda": EntityRegistryEntry(
        entity_id="grade_cabinda", entity_type="CrudeGrade",
        canonical_name="Cabinda",
        aliases=["Cabinda crude", "Angolan Cabinda"],
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
