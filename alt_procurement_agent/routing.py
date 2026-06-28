"""
Maritime routing optimizer.

OR-Tools MILP with asymmetric cost matrix (great-circle + weather + piracy + canal constraints).
RRNCO heuristic (arXiv 2503.16159, ICLR 2026) for large-instance asymmetric cases.
"""
from __future__ import annotations

from knowledge.api.read import CorridorView


def solve(
    suppliers: list[str],
    ports: list[str],
    corridors: list[CorridorView],
    volumes_mbpd: dict[str, float],
) -> dict[str, list[str]]:
    """
    Returns {supplier → [corridor, port]} optimal routing.
    Stub — implement OR-Tools MILP in Week 2.
    """
    # TODO: build asymmetric cost matrix (great-circle distance + piracy premium + canal fees + risk penalty)
    # TODO: formulate as MILP with OR-Tools CP-SAT solver
    # TODO: for large instances (>20 suppliers), fall back to RRNCO heuristic
    raise NotImplementedError
