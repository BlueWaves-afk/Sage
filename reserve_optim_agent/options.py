"""
Real-options valuation for SPR drawdown timing.

Models the decision to draw down NOW vs WAIT as an irreversible investment.
If there is a meaningful probability the crisis resolves soon, waiting retains
option value — drawing is costly to reverse (refilling at spot costs ~12% premium).

Binomial tree: two scenarios over [resolution_days]:
  - Up branch (p = p_crisis_resolves): crisis ends → no drawdown needed → save cost
  - Down branch (1-p): crisis continues → must draw anyway, but now urgency is higher

Option value of waiting = E[NPV(wait)] - NPV(draw now)
  Positive → defer drawdown
  Negative → draw now (crisis likely to persist, delay just worsens unmet demand)

Sources:
  IEA Energy Supply Security 2014, §5.3 (SPR release decision framework)
  Dixit & Pindyck 1994, "Investment Under Uncertainty" (real options framing)
"""
from __future__ import annotations
import os


def _load_options_params() -> dict:
    """Load option valuation defaults from bundle economics_params."""
    defaults = {
        "baseline_brent_usd_per_bbl":            80.0,
        "daily_consumption_mmt":                 0.56,
        "option_demand_destruction_during_wait": 0.30,
    }
    bundle_path = os.environ.get("SAGE_BUNDLE_PATH", "")
    if not bundle_path:
        return defaults
    try:
        from knowledge.context.loader import load_bundle
        ep = load_bundle(bundle_path).economics_params
        return {k: float(ep.get(k, {"value": v})["value"]) for k, v in defaults.items()}
    except Exception:
        return defaults


def option_value_of_waiting(
    p_crisis_resolves: float,
    resolution_days: float,
    refill_cost_premium: float,
    gap_mbpd: float,
    price_per_bbl: float | None = None,
    daily_consumption_mmt: float | None = None,
) -> float:
    """
    Returns option value (USD/MMT equivalent) of delaying the drawdown decision
    by `resolution_days`, given probability `p_crisis_resolves` that the crisis
    ends within that window.

    Positive → waiting has value (delay drawdown)
    Negative → draw now (crisis likely to persist)

    Args:
        p_crisis_resolves:    P(crisis resolved within resolution_days)
        resolution_days:      observation window before committing to a drawdown
        refill_cost_premium:  fraction above current price to refill later (e.g. 0.12)
        gap_mbpd:             supply gap triggering the decision
        price_per_bbl:        current Brent price (USD/bbl)
        daily_consumption_mmt: India daily crude consumption (MMT/day)
    """
    if gap_mbpd <= 0 or resolution_days <= 0:
        return 0.0

    p = _load_options_params()
    if price_per_bbl is None:
        price_per_bbl = p["baseline_brent_usd_per_bbl"]
    if daily_consumption_mmt is None:
        daily_consumption_mmt = p["daily_consumption_mmt"]

    _BBL_TO_MMT = 0.000000109

    # Volume needed over the resolution window (MMT)
    gap_mmt_per_day = gap_mbpd * _BBL_TO_MMT * 1e6
    volume_needed   = gap_mmt_per_day * resolution_days

    # Cost of drawing down now: price × volume
    cost_draw_now = price_per_bbl / (_BBL_TO_MMT * 1e6) * volume_needed

    # If we wait and crisis resolves: no drawdown needed → save cost_draw_now
    # But we bear unmet_demand cost during wait window (partial shortfall)
    demand_destruction_frac = p["option_demand_destruction_during_wait"]
    unmet_cost_wait = cost_draw_now * demand_destruction_frac

    # If we wait and crisis continues: must draw at the end of window anyway,
    # plus refill premium on what we eventually draw
    refill_penalty  = cost_draw_now * refill_cost_premium

    # NPV(draw now): just cost_draw_now
    npv_draw_now = cost_draw_now

    # E[NPV(wait)]: p_resolve × (unmet_cost_wait + 0) + (1-p_resolve) × (unmet_cost_wait + cost_draw_now + refill_penalty)
    npv_wait = (
        p_crisis_resolves       * unmet_cost_wait
        + (1 - p_crisis_resolves) * (unmet_cost_wait + cost_draw_now + refill_penalty)
    )

    # Option value = savings from waiting (negative = draw now saves money)
    option_val = npv_draw_now - npv_wait
    return round(option_val, 2)


def waiting_recommendation(option_val: float, threshold: float = 0.0) -> str:
    """Human-readable recommendation from option value."""
    if option_val > threshold:
        return f"WAIT: delaying drawdown saves ~${option_val:,.0f}/MMT equivalent — crisis likely to resolve."
    return f"DRAW NOW: waiting would cost ~${abs(option_val):,.0f}/MMT more — crisis likely to persist."
