"""
C1 — Normalized Signal contract.

All four sensory_agent sub-agents emit NormalizedSignal onto the Redis queue.
SAGE's ingest_signal() is the only consumer. Raw signals NEVER go to Graphiti directly.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

SignalSource = Literal["ais", "gdelt", "news", "sanctions", "price"]
Priority = Literal["HIGH", "MED", "LOW"]


class AisPayload(BaseModel):
    mmsi: Optional[str] = None
    vessel_name: Optional[str] = None
    gap_hours: Optional[float] = None
    dark_vessel: bool = False
    anomaly_score: float = Field(0.0, ge=0, le=1)
    sar_confirmed: Optional[bool] = None


class EventPayload(BaseModel):
    actor: Optional[str] = None
    action: Optional[str] = None
    target: Optional[str] = None
    tone: Optional[float] = None
    severity: float = Field(0.0, ge=0, le=1)
    goldstein: Optional[float] = None


class SanctionsPayload(BaseModel):
    list: Literal["OFAC", "EU", "UN"]
    change: Literal["add", "remove"]
    subject: str
    subject_type: Literal["vessel", "entity", "person"]
    effective_date: Optional[datetime] = None


class PricePayload(BaseModel):
    instrument: str  # e.g. 'BZ=F', 'CL=F'
    price: float
    changepoint: bool = False
    regime: Optional[Literal["calm", "stressed"]] = None
    war_risk_premium: Optional[float] = None


class NormalizedSignal(BaseModel):
    """
    Single observation from one sensory sub-agent, normalized to a common shape.
    Stable envelope — source-specific data lives in `payload`.
    """
    schema_version: str = "1.0.0"
    signal_id: str = Field(..., description="ULID/UUID, unique per emitted signal")
    source: SignalSource
    observed_at: datetime = Field(..., description="When the event occurred in the world (UTC). Maps to Graphiti reference_time.")
    ingested_at: datetime = Field(..., description="When the sub-agent emitted this (UTC)")

    priority_hint: Priority = Field("LOW", description="Sub-agent escalation hint. SAGE triage may override.")
    force_synthesis: bool = Field(False, description="Bypasses similarity gate — set True for sanctions adds, BOCD breakpoints, dark-vessel gaps")

    entity_refs: list[str] = Field(default_factory=list, description="Display names of entities this signal concerns")
    h3_cells: list[str] = Field(default_factory=list, description="H3 res-5 cell ids touched by this signal")
    lat: Optional[float] = None
    lon: Optional[float] = None

    summary: str = Field(..., description="One-line human-readable description")
    payload: dict = Field(default_factory=dict, description="Source-specific fields. Validated against per-source sub-model after dispatch on `source`.")

    source_url: Optional[str] = None
    raw_ref: Optional[str] = Field(None, description="Pointer to verbatim raw record in S3/DB for audit")
