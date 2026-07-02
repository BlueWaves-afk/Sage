"""
Maritime routing: cost-matrix approach over India's actual supply corridors.

For each supplier, selects the minimum landed-cost open corridor to an Indian
port, incorporating:
  - Base voyage cost + lead time by region (sourced from Clarkson/Baltic Exchange norms)
  - Bypass-route premiums from EXPORTS_VIA + BYPASS_ROUTE bundle edges (Yanbu +$2.5, +10d;
    Fujairah +$1.2, +2d)
  - Corridor-risk war-risk insurance premium (~$0.8/bbl per 0.5 risk unit)
  - Corridor closure: routes with risk > risk_max are excluded entirely

OR-Tools MILP upgrade path: system3_design.md §3.2 — drop-in for large-fleet allocation.

Sources: Clarkson Research VLCC rate norms; Baltic Exchange Dirty Tanker Index;
IEA Oil Supply Security 2014 (Table 4.2 bypass capacity/cost).
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from knowledge.api.read import CorridorView

# Fallback routing params used when no bundle is loaded (SAGE_BUNDLE_PATH unset).
# Sources: Clarkson Research VLCC rate norms 2024; Baltic Exchange VLCC routes.
_DEFAULT_BASE_COST: dict[str, float] = {
    "Saudi Arabia":    1.80,
    "Iraq":            1.80,
    "United Arab Emirates": 1.85,
    "Kuwait":          1.80,
    "Qatar":           1.85,
    "Iran":            1.85,
    "Russia":          3.20,
    "Nigeria":         3.80,
    "United States":   5.20,
    "Brazil":          4.60,
    "Venezuela":       5.50,
    "Kazakhstan":      3.50,
    "Angola":          4.00,
}

_DEFAULT_BASE_DAYS: dict[str, float] = {
    "Saudi Arabia":    20.0,
    "Iraq":            22.0,
    "United Arab Emirates": 22.0,
    "Kuwait":          21.0,
    "Qatar":           22.0,
    "Iran":            22.0,
    "Russia":          28.0,
    "Nigeria":         26.0,
    "United States":   35.0,
    "Brazil":          32.0,
    "Venezuela":       38.0,
    "Kazakhstan":      26.0,
    "Angola":          28.0,
}

_DEFAULT_CORRIDOR: dict[str, str] = {
    "Saudi Arabia":    "Strait of Hormuz",
    "Iraq":            "Strait of Hormuz",
    "United Arab Emirates": "Strait of Hormuz",
    "Kuwait":          "Strait of Hormuz",
    "Qatar":           "Strait of Hormuz",
    "Iran":            "Strait of Hormuz",
    "Russia":          "ESPO Pipeline",
    "Nigeria":         "Suez Canal",
    "United States":   "Cape of Good Hope",
    "Brazil":          "Cape of Good Hope",
    "Venezuela":       "Cape of Good Hope",
    "Kazakhstan":      "Suez Canal",
    "Angola":          "Cape of Good Hope",
}

_DEFAULT_WAR_RISK_PER_UNIT = 0.80  # USD/bbl per 0.5 risk unit above 0.3


def _load_routing_bundle():
    """Return (base_cost, base_days, war_risk) dicts from bundle, or defaults."""
    bundle_path = os.environ.get("SAGE_BUNDLE_PATH", "")
    if not bundle_path:
        return _DEFAULT_BASE_COST, _DEFAULT_BASE_DAYS, _DEFAULT_WAR_RISK_PER_UNIT
    try:
        from knowledge.context.loader import load_bundle
        b = load_bundle(bundle_path)
        rp = b.routing_params

        base_cost: dict[str, float] = {}
        base_days: dict[str, float] = {}
        for country in _DEFAULT_BASE_COST:
            cost_row = rp.get(f"vlcc_cost_usd_bbl|{country}")
            days_row = rp.get(f"lead_time_days|{country}")
            base_cost[country] = float(cost_row["value"]) if cost_row else _DEFAULT_BASE_COST[country]
            base_days[country] = float(days_row["value"]) if days_row else _DEFAULT_BASE_DAYS[country]

        war_row = rp.get("war_risk_premium_per_half_unit")
        war_risk = float(war_row["value"]) if war_row else _DEFAULT_WAR_RISK_PER_UNIT
        return base_cost, base_days, war_risk
    except Exception:
        return _DEFAULT_BASE_COST, _DEFAULT_BASE_DAYS, _DEFAULT_WAR_RISK_PER_UNIT


@dataclass
class RouteOption:
    supplier: str
    corridor: str
    is_bypass: bool
    landed_cost_usd_bbl: float
    lead_time_days: float
    corridor_risk: float


def solve(
    suppliers: list,               # list[SupplierView]
    corridors: list[CorridorView],
    bypass_edges: list[dict],       # [{src, via_corridor, cost_premium, added_days}]
    risk_max: float = 0.5,
) -> dict[str, RouteOption]:
    """
    For each non-sanctioned supplier, returns the lowest landed-cost open route.

    Routing params (VLCC costs, lead times, war-risk premium) are read from the
    bundle at SAGE_BUNDLE_PATH if set; falls back to compiled defaults otherwise.

    Returns {supplier_display_name → RouteOption}.
    """
    base_cost, base_days, war_risk_per_unit = _load_routing_bundle()
    corridor_by_name = {c.display_name: c for c in corridors}

    result: dict[str, RouteOption] = {}
    for supplier in suppliers:
        country = supplier.country or ""
        sup_base_cost = base_cost.get(country, 4.0)
        sup_base_days = base_days.get(country, 28.0)
        default_corr_name = _DEFAULT_CORRIDOR.get(country, "Suez Canal")

        candidates: list[RouteOption] = []

        # Default corridor option
        corr = corridor_by_name.get(default_corr_name)
        if corr is not None:
            risk = corr.risk_score or 0.0
            if risk <= risk_max:
                war_premium = max(0.0, (risk - 0.3)) / 0.5 * war_risk_per_unit
                candidates.append(RouteOption(
                    supplier=supplier.display_name,
                    corridor=default_corr_name,
                    is_bypass=False,
                    landed_cost_usd_bbl=round(sup_base_cost + war_premium, 2),
                    lead_time_days=sup_base_days,
                    corridor_risk=risk,
                ))
        else:
            # Corridor not in KB yet (e.g. Cape of Good Hope has no risk score) — allow
            candidates.append(RouteOption(
                supplier=supplier.display_name,
                corridor=default_corr_name,
                is_bypass=False,
                landed_cost_usd_bbl=round(sup_base_cost, 2),
                lead_time_days=sup_base_days,
                corridor_risk=0.1,
            ))

        # Bypass routes from BYPASS_ROUTE edges
        for edge in bypass_edges:
            if edge.get("src") != supplier.display_name:
                continue
            bypass_corr_name = edge.get("via_corridor", "Suez Canal")
            bypass_corr = corridor_by_name.get(bypass_corr_name)
            bypass_risk = (bypass_corr.risk_score or 0.0) if bypass_corr else 0.1
            if bypass_risk > risk_max:
                continue
            war_premium = max(0.0, (bypass_risk - 0.3)) / 0.5 * war_risk_per_unit
            candidates.append(RouteOption(
                supplier=supplier.display_name,
                corridor=bypass_corr_name,
                is_bypass=True,
                landed_cost_usd_bbl=round(sup_base_cost + edge.get("cost_premium", 0.0) + war_premium, 2),
                lead_time_days=sup_base_days + edge.get("added_days", 0.0),
                corridor_risk=bypass_risk,
            ))

        if candidates:
            result[supplier.display_name] = min(candidates, key=lambda r: r.landed_cost_usd_bbl)

    return result
