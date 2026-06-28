"""
C2 — Entity ontology. 11 node types passed to graphiti.add_episode(entity_types=...).

Rules:
- Every field is Optional — required fields cause extraction failures or hallucinations.
- Units are in the field name (throughput_mbpd, capacity_mmt, added_days).
- Docstrings and Field descriptions are read by the extraction LLM — write them carefully.
- Reserved names banned: uuid, name, group_id, labels, created_at, summary, attributes, name_embedding.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Corridor(BaseModel):
    """A maritime chokepoint or shipping lane that crude oil transits
    (e.g. 'Strait of Hormuz', 'Bab-el-Mandeb', 'Suez Canal').
    A risk-bearing transit node — NOT a port and NOT a country."""
    throughput_mbpd: Optional[float] = Field(None, description="Current crude throughput, million barrels/day")
    choke_severity: Optional[float] = Field(None, description="Structural importance 0..1; Hormuz≈0.95, Suez≈0.6")
    location_lat: Optional[float] = Field(None, description="Representative centre latitude")
    location_lon: Optional[float] = Field(None, description="Representative centre longitude")
    h3_cells: list[str] = Field(default_factory=list, description="H3 res-5 cell ids covering this lane")


class Supplier(BaseModel):
    """A crude-oil producing/exporting organisation or national oil company
    (e.g. 'Saudi Aramco', 'NIOC', 'ADNOC'). The selling counterparty — NOT a country."""
    country: Optional[str] = Field(None, description="Home country ISO name")
    daily_export_mbpd: Optional[float] = Field(None, description="Typical crude export volume, million bbl/day")
    sanctioned: Optional[bool] = Field(None, description="True if currently on any tracked sanctions list")


class Refinery(BaseModel):
    """An oil refinery that processes specific crude grades into products
    (e.g. 'Jamnagar', 'Mangaluru', 'Paradip'). A demand/processing node — NOT a port."""
    capacity_mbpd: Optional[float] = Field(None, description="Crude distillation capacity, million bbl/day")
    inventory_days: Optional[float] = Field(None, description="Days of crude inventory currently on hand")
    location_lat: Optional[float] = Field(None, description="Latitude")
    location_lon: Optional[float] = Field(None, description="Longitude")


class CrudeGrade(BaseModel):
    """A specific grade/assay of crude oil defined by API gravity and sulphur content
    (e.g. 'Arab Medium', 'Bonny Light', 'Urals'). Determines refinery processing economics."""
    api_gravity: Optional[float] = Field(None, description="API gravity (degrees); higher = lighter")
    sulfur_pct: Optional[float] = Field(None, description="Sulphur content, weight %; <0.5 sweet, >0.5 sour")
    origin: Optional[str] = Field(None, description="Producing field or region")


class Port(BaseModel):
    """A loading or discharge oil terminal (e.g. 'Vadinar', 'Yanbu', 'Sikka').
    A physical transfer point with a berth and draft limit — NOT a corridor."""
    location_lat: Optional[float] = Field(None, description="Latitude")
    location_lon: Optional[float] = Field(None, description="Longitude")
    draft_m: Optional[float] = Field(None, description="Maximum vessel draft in metres")
    congestion: Optional[float] = Field(None, description="Port congestion 0..1; 0 clear, 1 gridlocked")


class SPRCavern(BaseModel):
    """A strategic petroleum reserve storage site (e.g. 'Vizag', 'Mangaluru', 'Padur').
    Government-held emergency crude storage drawn down during a supply crisis.
    India total: 5.33 MMT across three sites."""
    capacity_mmt: Optional[float] = Field(None, description="Total storage capacity, million metric tonnes")
    current_fill_mmt: Optional[float] = Field(None, description="Current stored volume, million metric tonnes")
    location: Optional[str] = Field(None, description="Site name and location")


class Vessel(BaseModel):
    """An individual oil tanker identified by MMSI (e.g. 'MT Destiny').
    A moving asset — may be part of a shadow fleet if flag-hopping or AIS-dark."""
    mmsi: Optional[str] = Field(None, description="Maritime MMSI identifier")
    dwt: Optional[float] = Field(None, description="Deadweight tonnage")
    flag: Optional[str] = Field(None, description="Flag state")
    operator: Optional[str] = Field(None, description="Operating company or beneficial owner")
    sanctioned: Optional[bool] = Field(None, description="True if on any tracked sanctions list")


class GeoEvent(BaseModel):
    """A discrete geopolitical or security event affecting the supply chain
    (e.g. 'IRGC naval exercise', 'Houthi missile strike'). A point-in-time occurrence — NOT an entity."""
    actor: Optional[str] = Field(None, description="Primary actor")
    action: Optional[str] = Field(None, description="What happened, verb phrase")
    severity: Optional[float] = Field(None, description="Severity 0..1")
    event_time: Optional[datetime] = Field(None, description="When the event occurred (UTC). NOT a row timestamp.")


class Authority(BaseModel):
    """A sanctioning or regulatory body (e.g. 'OFAC', 'EU', 'UN').
    The issuer of sanctions — referenced by SANCTIONED_BY edges on Vessel and Supplier nodes."""
    jurisdiction: Optional[str] = Field(None, description="e.g. 'US', 'EU', 'UN'")


class PendingScenario(BaseModel):
    """A SPECULATIVE projected future forked by the Anticipatory Sandbox.
    Explicitly not ground truth. Promoted to ScenarioOutput only on confirmed threshold crossing.
    Must NEVER be written as a RISK_STATE on a live node."""
    confidence: Optional[float] = Field(None, description="P(risk threshold crossing within 24h), 0..1")
    projected_crossing_hours: Optional[float] = Field(None, description="Estimated hours until risk_score > 0.7")
    status: Literal["speculative", "promoted", "expired"] = "speculative"
    scenario_ref: Optional[str] = Field(None, description="Sandbox run id linking to staged S3/S4 outputs")


class ScenarioOutput(BaseModel):
    """A CONFIRMED cascade/recommendation result anchored to an entity. Ground truth."""
    scenario_id: Optional[str] = Field(None, description="Stable id for this scenario run")
    status: Literal["confirmed", "speculative"] = "confirmed"


ENTITY_TYPES: dict[str, type] = {
    "Corridor": Corridor,
    "Supplier": Supplier,
    "Refinery": Refinery,
    "CrudeGrade": CrudeGrade,
    "Port": Port,
    "SPRCavern": SPRCavern,
    "Vessel": Vessel,
    "GeoEvent": GeoEvent,
    "Authority": Authority,
    "PendingScenario": PendingScenario,
    "ScenarioOutput": ScenarioOutput,
}
