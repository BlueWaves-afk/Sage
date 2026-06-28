# SAGE — Schema & Contracts Specification

**Project:** SAGE · Problem Statement 2 (AI-Driven Energy Supply Chain Resilience)
**Status:** 🔒 NORMATIVE — this is the lock-in artifact. Every system codes against this.
**Owner:** Knowledge Layer · **Sign-off required from:** System 1 (sensing), Monitor/LangGraph, Systems 2–5
**Companion:** [`SAGE_Knowledge_Base_Spec.md`](./SAGE_Knowledge_Base_Spec.md) (narrative build guide)
**Stack:** `graphiti-core[falkordb]` ≥ 0.17 · FalkorDB ≥ 1.1.2 · Pydantic v2 · Python 3.11+

---

> **What this document is.** The KB spec explains *why* the architecture looks the way it does. **This document is the contract.** It contains the exact Pydantic models, JSON shapes, field names, units, and function signatures that four people build against in parallel. It is deliberately exhaustive and deliberately boring. The single most expensive failure mode on this project is a contract that changes in Week 3 and forces four people to refactor. **Lock this in Week 1, version it, and treat every change after that as a breaking change with a sign-off.**

## 0. Contract Inventory & Ownership

| # | Contract | Producer | Consumer(s) | Lock by | §  |
|---|---|---|---|---|---|
| C1 | **Normalized Signal** (raw ingest) | System 1 (4 sub-agents) | SAGE `ingest_signal()` | Day 2 | §3 |
| C2 | **Entity ontology** (11 node types) | SAGE | Graphiti extraction, all readers | Day 2 | §4 |
| C3 | **Edge ontology** + `edge_type_map` | SAGE | Graphiti extraction, all readers | Day 2 | §5 |
| C4 | **`RISK_STATE` edge** ⭐ | System 1 → SAGE writes | LangGraph monitor, S2–S5 | **Day 2–3** | §6 |
| C5 | **Output episodes** (Scenario/Procure/SPR) | Systems 2/3/4 | copilot, S5, each other | Day 3 | §7 |
| C6 | **PendingScenario / sandbox** | SAGE sandbox mgr | LangGraph promotion, S5 | Day 3 | §8 |
| C7 | **Read/Write API** signatures | SAGE | Systems 1–5 | Day 3–4 | §9 |

Every contract below carries a **`schema_version`** string. Bump it on any breaking change; consumers assert on major version at startup.

---

## 1. Design Principles (the rules every field obeys)

These are non-negotiable conventions. They exist so that 11 entity types and ~10 edge types stay internally consistent and so the extraction LLM behaves predictably.

1. **Pydantic v2, classes not instances.** `entity_types` / `edge_types` are passed as `dict[str, type[BaseModel]]` — the *class*, never an instance. (This is a known Graphiti footgun — see [issue #780](https://github.com/getzep/graphiti/issues/780).)
2. **Units live in the field name or the description, never implied.** `throughput_mbpd`, `capacity_mmt`, `added_days`. A bare `capacity` is forbidden. When in doubt, suffix the unit.
3. **Docstrings and `Field(description=...)` are LLM prompts.** Graphiti feeds them to the extraction model verbatim. Write them as instructions to a smart analyst, with a disambiguating example. This is the single biggest lever on entity-resolution quality (Hormuz vs "the Strait").
4. **Reserved names are banned.** Custom attributes may **not** use: `uuid`, `name`, `group_id`, `labels`, `created_at`, `summary`, `attributes`, `name_embedding`. (These belong to Graphiti's `EntityNode`/`EntityEdge`.) Use `event_time` not `created_at`, `display_name` not `name`.
5. **Identity attributes are `Optional` with `None` default.** Fields the LLM may not find in a given episode must be `Optional[...] = Field(None, ...)`. Required-without-default fields cause extraction to fail or hallucinate. **Only mark a field required if it is definitionally always present.** In practice: almost everything is `Optional`.
6. **Bounded scores are `0..1` floats.** All risk/severity/confidence/compatibility scores are normalized `0.0–1.0` unless the field name says otherwise (e.g. `yield_pct` is 0–100). State the range in the description.
7. **Bitemporal is Graphiti's job, not a field.** Do not add your own `valid_from`/`valid_to` columns. Pass `reference_time` to `add_episode()` (= "valid in world"); Graphiti records `created_at` (= "recorded") itself. The only domain time field allowed is event-semantic (e.g. `GeoEvent.event_time`).
8. **Geo is dual-encoded.** Store raw `location_lat` / `location_lon` (floats) **and** `h3_cells` (list of H3 index strings, res 5 default) on anything spatial. Lat/lon for rendering; H3 for the AIS join and the heatmap.
9. **Speculative data is tagged and isolated.** Anything produced by the sandbox carries `status: "speculative"` and a `confidence`. It is **never** written as a `RISK_STATE` on a live node (§6.5, §8).

---

## 2. Connection & Bootstrap Contract (C0)

> Corrects the legacy `Graphiti(uri=..., graph_name=...)` form. Graphiti ≥ 0.17 takes a driver object.

```python
# sage/kb/connection.py
import os
from graphiti_core import Graphiti
from graphiti_core.driver.falkordb_driver import FalkorDriver

SCHEMA_VERSION = "1.0.0"          # bump on any breaking ontology/contract change
GRAPH_NAME     = "sage"           # FalkorDB multi-tenant graph; MUST be non-None

def build_graphiti() -> Graphiti:
    driver = FalkorDriver(
        host=os.environ.get("FALKORDB_HOST", "falkordb"),
        port=int(os.environ.get("FALKORDB_PORT", "6379")),
        username=os.environ.get("FALKORDB_USERNAME") or None,
        password=os.environ.get("FALKORDB_PASSWORD"),
        database=GRAPH_NAME,
    )
    # LLM + embedder clients (Bedrock Nova) configured here per KB spec §2.
    return Graphiti(graph_driver=driver)

async def bootstrap(g: Graphiti) -> None:
    # idempotent; run once at startup. Safe to re-run.
    await g.build_indices_and_constraints()
```

**Invariants:**
- `database` (a.k.a. graph name) is **`"sage"`** everywhere. A `None` graph name silently falls back to `default_db` and splits your data across two graphs — a classic lost afternoon.
- One process owns writes (the SAGE core). Readers may open their own `Graphiti` against the same `database`.
- `build_indices_and_constraints()` is idempotent — call it on every boot; it's cheap and protects against a half-initialized graph.

---

## 3. Contract C1 — The Normalized Signal (raw ingest)

**The single most-used contract.** All four System-1 sub-agents emit this exact shape onto the Redis queue; SAGE's `ingest_signal()` is the only consumer. If this drifts, sensing and the KB desync silently.

It is a JSON object (validated by a Pydantic model on both ends). **Raw signals are never written to Graphiti directly** — they are triage input; only *synthesized* episodes reach `add_episode()` (KB spec §1, key rule).

```python
# sage/contracts/signal.py
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

SignalSource = Literal["ais", "gdelt", "news", "sanctions", "price"]
Priority     = Literal["HIGH", "MED", "LOW"]   # sub-agent's *suggested* priority; SAGE triage may override

class NormalizedSignal(BaseModel):
    """One observation from one sensing sub-agent, normalized to a common shape."""
    schema_version: str = "1.0.0"
    signal_id: str = Field(..., description="ULID/UUID, unique per emitted signal")
    source: SignalSource = Field(..., description="Which sub-agent produced this")
    observed_at: datetime = Field(..., description="When the event was observed in the world (UTC). Maps to Graphiti reference_time.")
    ingested_at: datetime = Field(..., description="When the sub-agent emitted it (UTC)")

    # --- routing hints ---
    priority_hint: Priority = Field("LOW", description="Sub-agent's escalation hint. Sanctions adds & BOCD breakpoints = HIGH and bypass triage.")
    force_synthesis: bool = Field(False, description="True bypasses the similarity gate (sanctions diffs, changepoints, dark-vessel gaps).")

    # --- where & who ---
    entity_refs: list[str] = Field(default_factory=list,
        description="display_names of entities this signal is about, e.g. ['Strait of Hormuz','NIOC']. Best-effort; SAGE resolves to nodes.")
    h3_cells: list[str] = Field(default_factory=list, description="H3 cell ids (res 5) the signal touches, if spatial")
    lat: Optional[float] = None
    lon: Optional[float] = None

    # --- payload ---
    summary: str = Field(..., description="One-line human-readable description of the observation")
    payload: dict = Field(default_factory=dict,
        description="Source-specific structured fields. Shape defined per-source in §3.1. Kept open so sub-agents evolve without breaking the envelope.")

    # --- raw provenance ---
    source_url: Optional[str] = None
    raw_ref: Optional[str] = Field(None, description="Pointer (S3 key / DB id) to the verbatim raw record for audit")
```

### 3.1 Per-source `payload` shapes (sub-schemas)

The envelope is stable; `payload` is typed per source so sub-agents can evolve independently. SAGE validates `payload` against the matching model after dispatch on `source`.

| `source` | `payload` model | Key fields |
|---|---|---|
| `ais` | `AisPayload` | `mmsi`, `vessel_name?`, `gap_hours?`, `dark_vessel: bool`, `anomaly_score: 0..1`, `sar_confirmed?: bool` |
| `gdelt` / `news` | `EventPayload` | `actor`, `action`, `target?`, `tone: float`, `severity: 0..1`, `goldstein?: float` |
| `sanctions` | `SanctionsPayload` | `list: Literal['OFAC','EU','UN']`, `change: Literal['add','remove']`, `subject`, `subject_type: Literal['vessel','entity','person']`, `effective_date` |
| `price` | `PricePayload` | `instrument: Literal['BZ=F','CL=F',...]`, `price`, `changepoint: bool`, `regime?: Literal['calm','stressed']`, `war_risk_premium?: float` |

> **Rule:** a sub-agent that adds a field puts it in `payload` and bumps the *payload* sub-model only. The envelope `schema_version` bumps only when the envelope changes — which should be approximately never.

---

## 4. Contract C2 — Entity Ontology (11 node types)

Passed to `add_episode(entity_types={...})`. The first 9 are the live supply-chain ontology; the last 2 are sandbox/output bookkeeping types (kept here so there is *one* registry).

> **Why explicit types:** without them the LLM invents labels and "Strait of Hormuz" / "Hormuz Strait" / "the Strait" become three nodes. Strong docstrings + a disambiguating example collapse them.

### 4.1 Registry

```python
# sage/schema/entities.py  — import ENTITY_TYPES wherever add_episode is called
ENTITY_TYPES: dict[str, type[BaseModel]] = {
    "Corridor": Corridor, "Supplier": Supplier, "Refinery": Refinery,
    "CrudeGrade": CrudeGrade, "Port": Port, "SPRCavern": SPRCavern,
    "Vessel": Vessel, "GeoEvent": GeoEvent, "Authority": Authority,
    "PendingScenario": PendingScenario, "ScenarioOutput": ScenarioOutput,
}
```

### 4.2 Definitions

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

class Corridor(BaseModel):
    """A maritime chokepoint or shipping lane that crude oil transits
    (e.g. 'Strait of Hormuz', 'Bab-el-Mandeb', 'Suez Canal').
    A risk-bearing transit node — NOT a port and NOT a country."""
    throughput_mbpd: Optional[float] = Field(None, description="Current crude throughput, million barrels/day")
    choke_severity: Optional[float] = Field(None, description="Structural importance 0..1; Hormuz≈0.95, Suez≈0.6")
    location_lat: Optional[float] = Field(None, description="Representative centre latitude")
    location_lon: Optional[float] = Field(None, description="Representative centre longitude")
    h3_cells: list[str] = Field(default_factory=list, description="H3 res-5 cell ids covering the lane")

class Supplier(BaseModel):
    """A crude-oil producing/exporting organisation or national oil company
    (e.g. 'Saudi Aramco', 'NIOC', 'ADNOC'). The selling counterparty, not a country."""
    country: Optional[str] = Field(None, description="Home country ISO name")
    daily_export_mbpd: Optional[float] = Field(None, description="Typical crude export volume, million bbl/day")
    sanctioned: Optional[bool] = Field(None, description="True if currently on any tracked sanctions list")

class Refinery(BaseModel):
    """An oil refinery that processes specific crude grades into products
    (e.g. 'Jamnagar', 'Mangaluru', 'Paradip'). A demand/processing node."""
    capacity_mbpd: Optional[float] = Field(None, description="Crude distillation capacity, million bbl/day")
    inventory_days: Optional[float] = Field(None, description="Days of crude inventory on hand")
    location_lat: Optional[float] = Field(None, description="Latitude")
    location_lon: Optional[float] = Field(None, description="Longitude")

class CrudeGrade(BaseModel):
    """A specific grade/assay of crude oil defined by API gravity and sulphur
    (e.g. 'Arab Medium', 'Bonny Light', 'Urals'). Determines refinery economics."""
    api_gravity: Optional[float] = Field(None, description="API gravity (degrees); higher = lighter")
    sulfur_pct: Optional[float] = Field(None, description="Sulphur content, weight %; <0.5 sweet, >0.5 sour")
    origin: Optional[str] = Field(None, description="Producing field/region")

class Port(BaseModel):
    """A loading or discharge oil terminal (e.g. 'Vadinar', 'Yanbu', 'Sikka').
    A physical transfer point with a berth and a draft limit. NOT a corridor."""
    location_lat: Optional[float] = Field(None, description="Latitude")
    location_lon: Optional[float] = Field(None, description="Longitude")
    draft_m: Optional[float] = Field(None, description="Max vessel draft, metres")
    congestion: Optional[float] = Field(None, description="Congestion 0..1; 0 clear, 1 gridlocked")

class SPRCavern(BaseModel):
    """A strategic petroleum reserve storage site (e.g. 'Vizag','Mangaluru','Padur').
    Government-held emergency crude storage, drawn down in a supply crisis."""
    capacity_mmt: Optional[float] = Field(None, description="Total storage capacity, million metric tonnes")
    current_fill_mmt: Optional[float] = Field(None, description="Current stored volume, million metric tonnes")
    location: Optional[str] = Field(None, description="Site name/location")

class Vessel(BaseModel):
    """An individual oil tanker identified by MMSI (e.g. 'MT Destiny').
    A moving asset, possibly part of a shadow fleet."""
    mmsi: Optional[str] = Field(None, description="Maritime MMSI identifier")
    dwt: Optional[float] = Field(None, description="Deadweight tonnage")
    flag: Optional[str] = Field(None, description="Flag state")
    operator: Optional[str] = Field(None, description="Operating company / beneficial owner")
    sanctioned: Optional[bool] = Field(None, description="True if on a tracked sanctions list")

class GeoEvent(BaseModel):
    """A discrete geopolitical or security event affecting the supply chain
    (e.g. 'IRGC naval exercise', 'Houthi missile strike'). A point-in-time occurrence."""
    actor: Optional[str] = Field(None, description="Primary actor")
    action: Optional[str] = Field(None, description="What happened, verb phrase")
    severity: Optional[float] = Field(None, description="Severity 0..1")
    event_time: Optional[datetime] = Field(None, description="When the event occurred (UTC). NOT a row timestamp.")

class Authority(BaseModel):
    """A sanctioning or regulatory body (e.g. 'OFAC','EU','UN').
    The issuer of sanctions, referenced by SANCTIONED_BY edges."""
    jurisdiction: Optional[str] = Field(None, description="e.g. 'US','EU','UN'")

# --- bookkeeping / output types (see §7, §8) ---
class PendingScenario(BaseModel):
    """A SPECULATIVE projected future forked by the Anticipatory Sandbox.
    Explicitly not ground truth. Promoted to ScenarioOutput only on threshold crossing."""
    confidence: Optional[float] = Field(None, description="P(threshold crossing) 0..1 from trajectory model")
    projected_crossing_hours: Optional[float] = Field(None, description="Projected hours until risk_score>0.7")
    status: Literal["speculative", "promoted", "expired"] = "speculative"
    scenario_ref: Optional[str] = Field(None, description="Sandbox run id linking to staged S3/S4 outputs")

class ScenarioOutput(BaseModel):
    """A CONFIRMED cascade/recommendation result for an entity. Ground truth."""
    scenario_id: Optional[str] = Field(None, description="Stable id for this scenario run")
    status: Literal["confirmed", "speculative"] = "confirmed"
```

> **Note on output payloads.** The rich, numeric outputs of Systems 2/3/4 (gap timelines, ranked routes, drawdown schedules) are **not** modelled as entity attributes — they live in the episode body + structured edges (§7). The entity types above are deliberately thin; they are anchors, not blobs.

---

## 5. Contract C3 — Edge Ontology + `edge_type_map`

Edge types are Pydantic models too. `edge_type_map` keys are **tuples of entity-type-name strings**; the special key `("Entity","Entity")` is a wildcard fallback. Unmapped pairs degrade to generic `RELATES_TO`.

> **Known footgun:** custom edge *attributes* may not extract on the very first time an edge type appears ([issue #1111](https://github.com/getzep/graphiti/issues/1111)). Mitigation: warm the graph once at bootstrap with a tiny seed episode that exercises each edge type, and assert attributes are present in the Day-4 smoke test.

### 5.1 Edge models

```python
# sage/schema/edges.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class ExportsVia(BaseModel):
    """Supplier ships crude through this Corridor."""
    volume_mbpd: Optional[float] = Field(None, description="Volume on this lane, million bbl/day")

class Feeds(BaseModel):
    """Corridor feeds traffic into this Port."""

class Supplies(BaseModel):
    """Port supplies crude to this Refinery."""

class ConfiguredFor(BaseModel):
    """Refinery is configured to process this CrudeGrade."""
    yield_pct: Optional[float] = Field(None, description="Product yield, 0..100 %")
    compatibility: Optional[float] = Field(None, description="Processing compatibility 0..1")

class SanctionedBy(BaseModel):
    """Vessel/Supplier is sanctioned by this Authority."""
    list_name: Optional[str] = Field(None, description="'OFAC'/'EU'/'UN'")
    effective_date: Optional[datetime] = Field(None, description="When the sanction took effect")

class BypassRoute(BaseModel):
    """Alternative routing from Supplier to Port avoiding a blocked corridor."""
    cost_premium: Optional[float] = Field(None, description="Added landed cost, USD/bbl")
    added_days: Optional[float] = Field(None, description="Extra transit days vs primary route")

class FeedsReserve(BaseModel):
    """Refinery draws from / refills this SPRCavern."""

class RiskState(BaseModel):                       # ⭐ see §6 — the locked contract
    """Current fused risk assessment for an entity, with factor breakdown."""
    score: float = Field(..., description="Fused risk 0..1")
    band: str = Field(..., description="'calm'|'watch'|'elevated'|'action'|'critical'")
    factor_ais: float = Field(0.0, description="AIS/dark-vessel contribution 0..1")
    factor_gdelt: float = Field(0.0, description="News/GDELT tone contribution 0..1")
    factor_price: float = Field(0.0, description="Price/war-risk-premium contribution 0..1")
    factor_sanctions: float = Field(0.0, description="Sanctions contribution 0..1")
    rationale: Optional[str] = Field(None, description="One-line driver explanation from System 1")
    model_version: Optional[str] = Field(None, description="System-1 fusion model version that produced this")

class AffectsScenario(BaseModel):
    """Links an entity to a PendingScenario/ScenarioOutput about it."""
    confidence: Optional[float] = Field(None, description="0..1")
```

### 5.2 The map

```python
# sage/schema/edges.py
EDGE_TYPES: dict[str, type[BaseModel]] = {
    "EXPORTS_VIA": ExportsVia, "FEEDS": Feeds, "SUPPLIES": Supplies,
    "CONFIGURED_FOR": ConfiguredFor, "SANCTIONED_BY": SanctionedBy,
    "BYPASS_ROUTE": BypassRoute, "FEEDS_RESERVE": FeedsReserve,
    "RISK_STATE": RiskState, "AFFECTS_SCENARIO": AffectsScenario,
}

EDGE_TYPE_MAP: dict[tuple[str, str], list[str]] = {
    ("Supplier", "Corridor"):    ["EXPORTS_VIA"],
    ("Corridor", "Port"):        ["FEEDS"],
    ("Port", "Refinery"):        ["SUPPLIES"],
    ("Refinery", "CrudeGrade"):  ["CONFIGURED_FOR"],
    ("Vessel", "Authority"):     ["SANCTIONED_BY"],
    ("Supplier", "Authority"):   ["SANCTIONED_BY"],
    ("Supplier", "Port"):        ["BYPASS_ROUTE"],
    ("Refinery", "SPRCavern"):   ["FEEDS_RESERVE"],
    # RISK_STATE & AFFECTS_SCENARIO are attached to many node types → wildcard:
    ("Entity", "Entity"):        ["RISK_STATE", "AFFECTS_SCENARIO"],
}
```

> `RISK_STATE` is mapped via the `("Entity","Entity")` wildcard because risk attaches to corridors, refineries, suppliers, ports — i.e. nearly everything. The wildcard means "valid between any pair" so the monitor never misses one.

---

## 6. ⭐ Contract C4 — The `RISK_STATE` Edge (LOCK FIRST)

> **This is the contract the autonomous loop runs on.** System 1 computes the score; SAGE stores it; the LangGraph monitor and Systems 2–5 read it. Get it exactly right and lock it **Day 2–3** with sign-off from whoever owns System 1 fusion and the monitor. If `score` and the factor fields below change names later, the monitor, the UI colour bands, the scenario trigger, and the sandbox all break at once.

### 6.1 Responsibility split (unchanged from KB spec §5)

| Step | Component | Responsibility |
|---|---|---|
| **Compute** | System 1 fusion | Produces `score` + factor breakdown. The KB never computes this. |
| **Store** | SAGE | Writes `RiskState` edge with `reference_time = observed_at`. |
| **Read** | LangGraph monitor | Polls every 30s; fires bands. |
| **Read** | Systems 2–5 | Context, display, scenario input. |

### 6.2 Canonical JSON shape (what `get_risk_scores()` returns per edge)

```json
{
  "schema_version": "1.0.0",
  "entity": "Strait of Hormuz",
  "entity_uuid": "…graphiti node uuid…",
  "score": 0.62,
  "band": "elevated",
  "factors": { "ais": 0.41, "gdelt": 0.55, "price": 0.30, "sanctions": 0.00 },
  "rationale": "3 dark-vessel gaps near Larak + war-risk premium breakpoint",
  "model_version": "fusion-2026.02",
  "valid_at": "2026-02-23T11:04:00Z",
  "recorded_at": "2026-02-23T11:04:03Z"
}
```

`valid_at` ← Graphiti edge `valid_at` (from `reference_time`); `recorded_at` ← Graphiti `created_at`. The read wrapper flattens the `RiskState.factor_*` attributes into the nested `factors` object for consumers; the underlying edge stores them flat (§5.1) because Graphiti attributes are flat.

### 6.3 Threshold bands (single source of truth)

| Band string | Condition | Fires | UI colour |
|---|---|---|---|
| `calm` | `score < 0.25` | — | phosphor green |
| `watch` | `0.25 ≤ score < 0.45` | — | cyan |
| `elevated` | `0.45 ≤ score < 0.70` | sandbox fork if `P(cross<24h) > 0.5` | amber |
| `action` | `0.70 ≤ score < 0.90` | promote sandbox / fire System 2 on live state | red |
| `critical` | `score ≥ 0.90` | immediate human escalation | pulsing red |

> The `band` is computed by **SAGE at write time** from `score` and embedded in the edge, so every reader agrees on the bucket without re-implementing the thresholds. These numbers live in one constant (`sage/contracts/bands.py`) and nowhere else.

### 6.4 How SAGE writes it

The score is stated **in the synthesized episode text** (so embeddings capture it) **and** carried structurally by the `RiskState` edge:

```python
episode_text = f"""{entity} — risk assessment {valid_at:%Y-%m-%d %H:%M}Z.
Current risk score: {score:.2f} ({band.upper()}).
Factor breakdown: AIS {f_ais:.2f}, GDELT {f_gdelt:.2f}, price {f_price:.2f}, sanctions {f_sanc:.2f}.
{narrative_synthesis_prose}"""

await g.add_episode(
    name=f"{slug}_risk_{valid_at:%Y%m%dT%H%M%SZ}",
    episode_body=episode_text,
    source=EpisodeType.text,
    source_description="SAGE synthesis",
    reference_time=valid_at,                 # bitemporal valid time
    entity_types=ENTITY_TYPES,
    edge_types=EDGE_TYPES,
    edge_type_map=EDGE_TYPE_MAP,
)
```

### 6.5 Isolation rule
A `PendingScenario`'s projected risk is **never** written as a `RISK_STATE` on a live node. Speculative risk lives only inside the sandbox/`PendingScenario` (§8). Violating this contaminates ground truth and the monitor will fire on a future that hasn't happened.

---

## 7. Contract C5 — Output Episodes (Systems 2/3/4)

Systems 2–4 don't store blobs on entities; they call a SAGE write wrapper that creates a typed **output episode** linked back to the triggering scenario. The episode body is human-readable prose (for copilot/citation); the machine-readable result rides in the `data` field, validated by these models.

```python
# sage/contracts/outputs.py
from pydantic import BaseModel, Field
from typing import Optional, Literal

Status = Literal["speculative", "confirmed"]

class ScenarioOutputData(BaseModel):           # System 2 → write_scenario()
    schema_version: str = "1.0.0"
    scenario_id: str
    trigger_entity: str
    status: Status
    confidence: float = Field(..., description="0..1")
    gap_mbpd: float = Field(..., description="Projected supply gap, million bbl/day")
    gap_duration_days: float
    feedstock_gap_timeline: list[float] = Field(..., description="Per-day refinery feedstock gap, mbpd")
    price_impact_low: float = Field(..., description="USD/bbl, low band")
    price_impact_high: float = Field(..., description="USD/bbl, high band")
    spr_depletion_days: float = Field(..., description="Days of SPR cover remaining at projected draw")
    gdp_proxy_impact_pct: Optional[float] = None
    assumptions: dict = Field(default_factory=dict, description="Labelled, sourced, editable ARIO params")

class ProcurementRecData(BaseModel):           # System 3 → write_procurement()
    schema_version: str = "1.0.0"
    scenario_id: str
    status: Status
    ranked: list["ProcurementOption"]

class ProcurementOption(BaseModel):
    supplier: str
    grade: str
    route_via: str = Field(..., description="Corridor/Port the route uses, e.g. 'Yanbu bypass'")
    landed_cost_usd_bbl: float
    lead_time_days: float
    grade_compatibility: float = Field(..., description="0..1 vs target refinery")
    corridor_risk: float = Field(..., description="0..1")
    topsis_score: float = Field(..., description="0..1 multi-objective rank score")
    rationale: str = Field(..., description="Nova-Pro one-paragraph, cited")

class SPRScheduleData(BaseModel):              # System 4 → write_spr_schedule()
    schema_version: str = "1.0.0"
    scenario_id: str
    status: Status
    daily_plan: list["SPRDay"]
    prob_above_buffer: float = Field(..., description="P(reserve stays > 3-day buffer), 0..1")
    policy_memo: str = Field(..., description="Nova-Pro rationale memo")

class SPRDay(BaseModel):
    day: int
    action: Literal["draw", "hold", "refill"]
    volume_mmt: float
    reserve_after_mmt: float
    days_cover_after: float
```

**Linkage rule:** every output episode references its `scenario_id` and is connected to the trigger entity by an `AFFECTS_SCENARIO` edge, so `get_subgraph(entity)` and the copilot can retrieve the full chain (signal → scenario → procurement → SPR) in one hop.

---

## 8. Contract C6 — Sandbox / `PendingScenario`

The sandbox forks an in-memory subgraph; its only persisted footprint is a `PendingScenario` node (entity type, §4.2) plus the staged S3/S4 outputs tagged `status="speculative"`.

| Field | Meaning |
|---|---|
| `confidence` | `P(risk_score>0.7 within 24h)` from the trajectory model |
| `projected_crossing_hours` | ETA to threshold |
| `status` | `speculative` → `promoted` (on real crossing) → `expired` (TTL passed, no crossing) |
| `scenario_ref` | links to the speculative `ScenarioOutputData`/`ProcurementRecData`/`SPRScheduleData` |

**Promotion contract (LangGraph monitor):** when a live `RISK_STATE.score` crosses `0.70` for an entity that has a `speculative` `PendingScenario`:
1. set `PendingScenario.status = "promoted"`,
2. flip the linked output episodes' `status` from `"speculative"` → `"confirmed"`,
3. refresh stale numeric params with live values,
4. emit a `scenario.promoted` LangGraph event for System 5.

**Expiry contract:** a `PendingScenario` older than its TTL (default 72h) with no crossing → `status="expired"`; its speculative outputs are detached, not deleted (kept for audit).

---

## 9. Contract C7 — Read/Write API

> Thin typed wrapper over Graphiti. Other systems call **these signatures only** — never raw `graphiti.search()`. **Lock the signatures Week 1; implement bodies Week 2.** Stubs return typed empties so the team can integrate against them on Day 4.

### 9.1 Write API

```python
# sage/api/write.py   (all async)
async def ingest_signal(sig: NormalizedSignal) -> IngestResult: ...
    # System 1. THE entry point. triage → (synthesis | extract-only | store) → add_episode → risk propagation.

async def write_scenario(data: ScenarioOutputData) -> EpisodeRef: ...          # System 2
async def write_procurement(data: ProcurementRecData) -> EpisodeRef: ...       # System 3
async def write_spr_schedule(data: SPRScheduleData) -> EpisodeRef: ...          # System 4
async def write_pending(p: PendingScenarioData) -> EpisodeRef: ...              # Sandbox (isolated, speculative)
async def promote_pending(scenario_ref: str) -> EpisodeRef: ...                 # Monitor (§8 promotion)

class IngestResult(BaseModel):
    signal_id: str
    decision: Literal["synthesized", "extracted", "stored", "dropped"]
    episode_uuid: Optional[str] = None
    risk_updated: bool = False
```

### 9.2 Read API

```python
# sage/api/read.py   (all async)
async def get_subgraph(entity: str, hops: int = 2) -> SubgraphView: ...         # System 2
async def get_available_suppliers(risk_max: float = 0.4) -> list[SupplierView]: ...   # System 3 (excludes sanctioned)
async def get_grade_specs(refinery: str) -> list[GradeSpecView]: ...            # System 3
async def get_routes(risk_max: float = 0.5) -> list[CorridorView]: ...          # System 3
async def get_spr_state() -> list[SPRCavernView]: ...                           # System 4
async def get_risk_scores() -> list[RiskScoreView]: ...                         # Monitor / System 5  (shape = §6.2)
async def copilot_query(q: str) -> CopilotAnswer: ...                           # System 5 (EA-GraphRAG routed)
async def get_wiki_page(entity: str) -> WikiPage: ...                           # System 5 (narrative page on node click)
```

**Return-type rule:** every reader returns a typed Pydantic `*View` model, never a raw Graphiti `EntityNode`/`EntityEdge`. Consumers depend on the `View`, so the team is insulated from Graphiti internal changes. `CopilotAnswer` always carries `citations: list[EpisodeRef]`.

---

## 10. Versioning & Change Governance

- Every contract object carries `schema_version` (SemVer). **Major** bump = breaking (field renamed/removed, type changed). **Minor** = additive (new optional field). **Patch** = docs/description only.
- Consumers assert the **major** version at startup against `SCHEMA_VERSION` and fail loud on mismatch.
- A breaking change requires: (1) edit here, (2) bump major, (3) ping the affected owners in §0, (4) note it in §11 changelog.
- **After Day 4, the §6 `RISK_STATE` contract is frozen for the hackathon.** Anything else can take a minor bump; that one cannot move without a team huddle.

---

## 11. Build Order (maps to KB spec §8)

| Day | Deliverable | "Done" = |
|---|---|---|
| 1 | C0 connection (§2) | `bootstrap()` runs, toy `add_episode`+`search` works on FalkorDB |
| 2 | C2 entities + C3 edges (§4,§5) as Pydantic | imports clean; seed episode extracts all types in FalkorDB browser |
| 2–3 | **C4 `RISK_STATE` (§6) — sign-off** | monitor reads `get_risk_scores()` shape; System-1 owner agrees field names |
| 1–2 | C1 signal (§3) — sign-off | all 4 sub-agents emit valid `NormalizedSignal` |
| 3 | C5 outputs (§7) + C6 sandbox (§8) | stubbed writers create linked episodes |
| 3–4 | C7 API stubs (§9) | every signature importable, returns typed empty; team builds against them |
| 4–5 | E2E smoke | real Hormuz signal → synthesis → `RISK_STATE` queryable → `/wiki` written → output episodes linked |

> **🚧 Gate.** The team cannot parallelise until C1–C4 and the C7 signatures are locked and circulated. The Week-1 deliverable is **a stable contract, not a working KB.** Stability beats perfection.

---

## 12. Changelog

| Version | Date | Change |
|---|---|---|
| 1.0.0 | 2026-06-28 | Initial lock. Connection corrected to `FalkorDriver`/`graph_driver`. Added C1 normalized-signal contract, `band`+`rationale`+`model_version` on `RiskState`, output-episode data models (C5), sandbox promotion/expiry contract (C6), typed `*View` return rule (C7), versioning governance. |
