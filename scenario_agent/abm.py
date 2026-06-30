"""
Agent-based model (ABM) of the disruption cascade.

Where ARIO/IO are equation-based and aggregate, the ABM simulates individual agents
(refineries) making decisions each day — draw inventory, compete for limited bypass
crude, ration output when supply can't be secured. The system cascade EMERGES from
these interactions, capturing heterogeneity and non-linearity the analytic models miss
(e.g. refineries competing for a shared, capacity-limited bypass pool → some secure
supply, others ration).

This is the plan's "ARIO + ABM + GNN surrogate": ARIO/IO for the analytic baseline,
ABM for emergent behavioural realism. Parameters come from the same sourced bundle.
"""
from __future__ import annotations

from dataclasses import dataclass, field

BBL_PER_TONNE = 7.33


@dataclass
class RefineryAgent:
    name:           str
    capacity_mbpd:  float
    exposure:       float          # fraction of feed via the disrupted corridor
    inventory_days: float
    inventory_mbbl: float = 0.0    # remaining crude inventory
    secured_bypass: float = 0.0    # mbpd of bypass crude secured today
    rationed_days:  int   = 0
    gap_timeline:   list[float] = field(default_factory=list)

    def daily_loss(self, disruption_fraction: float) -> float:
        return self.capacity_mbpd * self.exposure * disruption_fraction


@dataclass
class ABMResult:
    horizon_days:        int
    agents:              list[dict]            # per-refinery outcome
    system_gap_timeline: list[float]           # total daily rationing (mbpd)
    peak_system_gap:     float
    refineries_rationing: int                  # how many had to ration
    bypass_utilization:  float                 # avg fraction of bypass pool used
    days_to_stabilize:   float                 # first day system gap returns to ~0


def simulate(
    refineries: list[dict],
    bypass_capacity_mbpd: float = 4.0,
    bypass_ramp_days: float = 5.0,
    disruption_fraction: float = 1.0,
    disruption_days: int = 30,
    horizon_days: int = 45,
) -> ABMResult:
    """Run the agent simulation. refineries: [{name, capacity_mbpd, exposure, inventory_days}]."""
    agents = [
        RefineryAgent(
            name=r["name"], capacity_mbpd=float(r.get("capacity_mbpd", 0)),
            exposure=float(r.get("exposure", 0)), inventory_days=float(r.get("inventory_days", 22)),
            inventory_mbbl=float(r.get("inventory_days", 22)) * float(r.get("capacity_mbpd", 0)),
        )
        for r in refineries
    ]

    system_gap: list[float] = []
    bypass_used_frac: list[float] = []

    for t in range(horizon_days):
        active = t < disruption_days
        ramp = max(0.0, min(1.0, (t - bypass_ramp_days) / max(bypass_ramp_days, 1)))
        bypass_pool = bypass_capacity_mbpd * ramp          # shared, capacity-limited, ramps in

        # 1. Each agent computes its unmet feed after drawing inventory.
        needs = {}
        for a in agents:
            loss = a.daily_loss(disruption_fraction) if active else 0.0
            # draw own inventory first
            drawn = min(loss, a.inventory_mbbl)
            a.inventory_mbbl -= drawn
            needs[a.name] = max(0.0, loss - drawn)         # still short → wants bypass

        # 2. Agents COMPETE for the limited bypass pool (allocated proportionally to need).
        total_need = sum(needs.values())
        for a in agents:
            if total_need > 0 and bypass_pool > 0:
                a.secured_bypass = needs[a.name] / total_need * min(bypass_pool, total_need)
            else:
                a.secured_bypass = 0.0
            gap = max(0.0, needs[a.name] - a.secured_bypass)   # unmet → ration
            a.gap_timeline.append(round(gap, 4))
            if gap > 0.001:
                a.rationed_days += 1

        system_gap.append(round(sum(a.gap_timeline[-1] for a in agents), 4))
        bypass_used_frac.append(min(1.0, total_need / bypass_capacity_mbpd) if bypass_capacity_mbpd else 0.0)

    peak = max(system_gap) if system_gap else 0.0
    rationing = sum(1 for a in agents if a.rationed_days > 0)
    stabilize = next((float(i) for i, g in enumerate(system_gap) if i > 0 and g < 0.01
                      and all(x < 0.01 for x in system_gap[i:])), float(horizon_days))

    return ABMResult(
        horizon_days=horizon_days,
        agents=[
            {"name": a.name, "exposure": round(a.exposure, 3),
             "peak_gap_mbpd": round(max(a.gap_timeline) if a.gap_timeline else 0.0, 4),
             "rationed_days": a.rationed_days, "gap_timeline": a.gap_timeline}
            for a in sorted(agents, key=lambda x: -(max(x.gap_timeline) if x.gap_timeline else 0))
        ],
        system_gap_timeline=system_gap,
        peak_system_gap=round(peak, 4),
        refineries_rationing=rationing,
        bypass_utilization=round(sum(bypass_used_frac) / len(bypass_used_frac), 3) if bypass_used_frac else 0.0,
        days_to_stabilize=stabilize,
    )
