"""
Shared contracts (C1–C7) — the common language every system imports from.
No imports from any other sage package. Zero circular-dependency risk.
"""
from contracts.signal import NormalizedSignal, SignalSource, Priority
from contracts.outputs import ScenarioOutputData, ProcurementRecData, SPRScheduleData
from contracts.bands import BANDS, score_to_band

__all__ = [
    "NormalizedSignal", "SignalSource", "Priority",
    "ScenarioOutputData", "ProcurementRecData", "SPRScheduleData",
    "BANDS", "score_to_band",
]
