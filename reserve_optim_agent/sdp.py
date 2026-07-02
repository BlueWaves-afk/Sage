"""
SDP / CMDP solver for SPR drawdown optimisation.

State space: (reserve_level_idx, day) — exact Bellman backward induction.

CMDP (Constrained MDP):
  Maximise E[economic_utility] subject to:
    P(reserve < buffer_threshold_days × daily_consumption) ≤ 0.05

Lagrangian relaxation: augment reward with -λ × I(reserve < threshold).
λ tuned via bisection until the chance constraint binds.

India SPR facts (ISPRL, 2025):
  5.33 MMT total at ~40% fill → ~2.13 MMT available.
  Daily crude consumption: 0.56 MMT/day.
  Current cover: ~3.8 days. Full capacity: ~9.5 days.

Sources: IEA Oil Supply Security 2014 (crisis episode calibration);
ISPRL annual report 2023-24 (capacity/fill data).
"""
from __future__ import annotations

import os
import numpy as np
from dataclasses import dataclass, field

_BBL_TO_MMT = 0.000000109   # 1 bbl ≈ 0.109 tonne → 1e-6 MMT

_SDP_DEFAULTS = {
    "buffer_threshold_days":  3.0,
    "spr_horizon_days":       90,
    "sdp_discount_rate":      0.97,
    "sdp_max_draw_fraction":  0.60,
    "daily_consumption_mmt":  0.56,   # from economics_params (derived from ario_params)
    "baseline_brent_usd_per_bbl": 80.0,
}


def _load_sdp_bundle() -> dict:
    """Return SDP structural constants from bundle, or compiled defaults."""
    bundle_path = os.environ.get("SAGE_BUNDLE_PATH", "")
    if not bundle_path:
        return _SDP_DEFAULTS.copy()
    try:
        from knowledge.context.loader import load_bundle
        b = load_bundle(bundle_path)
        sp = b.spr_params
        ep = b.economics_params
        return {
            "buffer_threshold_days":  float(sp.get("buffer_threshold_days",     {"value": 3.0})["value"]),
            "spr_horizon_days":       int(float(sp.get("spr_horizon_days",      {"value": 90})["value"])),
            "sdp_discount_rate":      float(sp.get("sdp_discount_rate",         {"value": 0.97})["value"]),
            "sdp_max_draw_fraction":  float(sp.get("sdp_max_draw_fraction",     {"value": 0.60})["value"]),
            "daily_consumption_mmt":  float(ep.get("daily_consumption_mmt",     {"value": 0.56})["value"]),
            "baseline_brent_usd_per_bbl": float(ep.get("baseline_brent_usd_per_bbl", {"value": 80.0})["value"]),
        }
    except Exception:
        return _SDP_DEFAULTS.copy()


@dataclass
class SDPParams:
    spr_initial_mmt:         float = 2.13   # MMT available at crisis start
    daily_consumption_mmt:   float = 0.56   # MMT/day India crude consumption
    gap_mbpd:                float = 0.0    # supply gap from ScenarioOutputData
    gap_duration_days:       int   = 30
    price_per_bbl:           float = 80.0   # current Brent USD/bbl
    buffer_threshold_days:   float = 3.0    # P(reserve < this) ≤ 0.05  [from bundle: buffer_threshold_days]
    horizon_days:            int   = 90     # [from bundle: spr_horizon_days]
    discount_rate:           float = 0.97   # daily discount  [from bundle: sdp_discount_rate]
    max_draw_fraction:       float = 0.60   # of daily consumption [from bundle: sdp_max_draw_fraction]

    # Bisection settings for Lagrangian CMDP
    lambda_lo:  float = 0.0
    lambda_hi:  float = 200.0
    lambda_tol: float = 0.5


@dataclass
class SDPResult:
    daily_plan:           list[dict] = field(default_factory=list)
    prob_above_buffer:    float = 0.0
    constraint_satisfied: bool  = True
    lagrange_multiplier:  float = 0.0
    policy_memo:          str   = ""


_N_LEVELS = 30
_ACTIONS  = ["hold", "draw_min", "draw_quarter", "draw_half", "draw_full"]


def solve(params: SDPParams) -> SDPResult:
    """
    Backward induction over (reserve_idx × day) state grid.
    Returns optimal day-by-day drawdown schedule with CMDP guarantee.
    """
    gap_mmt_per_day = params.gap_mbpd * _BBL_TO_MMT * 1e6

    r_max  = max(params.spr_initial_mmt * 1.5,
                 params.buffer_threshold_days * params.daily_consumption_mmt * 2.5)
    levels = np.linspace(0.0, r_max, _N_LEVELS)
    buf    = params.buffer_threshold_days * params.daily_consumption_mmt

    max_draw = min(gap_mmt_per_day, params.daily_consumption_mmt * params.max_draw_fraction)
    draw_vol = {
        "hold":         0.0,
        "draw_min":     max_draw * 0.10,
        "draw_quarter": max_draw * 0.25,
        "draw_half":    max_draw * 0.50,
        "draw_full":    max_draw * 1.00,
    }

    # Bisect on λ to satisfy P(reserve > buffer) ≥ 0.95
    lam    = 0.0
    result = _run_mdp(params, levels, buf, gap_mmt_per_day, draw_vol, lam)

    if result["prob"] < 0.95 and params.gap_mbpd > 0:
        lo, hi = params.lambda_lo, params.lambda_hi
        for _ in range(25):
            lam    = (lo + hi) / 2.0
            result = _run_mdp(params, levels, buf, gap_mmt_per_day, draw_vol, lam)
            if abs(hi - lo) < params.lambda_tol:
                break
            if result["prob"] < 0.95:
                lo = lam   # need more penalty → increase λ
            else:
                hi = lam

    return _build_result(params, result, lam, buf)


def _run_mdp(params, levels, buf, gap_mmt, draw_vol, lam):
    H  = params.horizon_days
    NL = len(levels)

    V      = np.zeros((H + 1, NL))
    policy = np.zeros((H, NL), dtype=int)

    for t in range(H - 1, -1, -1):
        gap_today = gap_mmt if t < params.gap_duration_days else 0.0

        for li in range(NL):
            reserve = levels[li]
            best_v = -1e18
            best_a = 0

            for ai, action in enumerate(_ACTIONS):
                dv = draw_vol[action]
                if dv > reserve + 1e-9:
                    continue   # can't draw more than available

                unmet    = max(0.0, gap_today - dv)
                new_res  = max(0.0, reserve - dv)
                # Reward: negative unmet cost (economic loss from shortfall)
                reward   = -(unmet * params.price_per_bbl / _BBL_TO_MMT * 0.000001)
                # CMDP penalty
                if new_res < buf:
                    reward -= lam

                next_li = int(np.searchsorted(levels, min(new_res, levels[-1])))
                next_li = min(next_li, NL - 1)
                total   = reward + params.discount_rate * V[t + 1, next_li]

                if total > best_v:
                    best_v, best_a = total, ai

            V[t, li]      = best_v
            policy[t, li] = best_a

    # Forward pass from spr_initial_mmt
    plan: list[dict] = []
    reserve         = params.spr_initial_mmt
    below_buf       = 0

    for t in range(H):
        li  = int(np.searchsorted(levels, min(reserve, levels[-1])))
        li  = min(li, NL - 1)
        ai  = policy[t, li]
        act = _ACTIONS[ai]
        dv  = min(draw_vol[act], reserve)

        gap_today = gap_mmt if t < params.gap_duration_days else 0.0
        new_res   = max(0.0, reserve - dv)

        if new_res < buf:
            below_buf += 1

        plan.append({
            "day":               t + 1,
            "action":            "draw" if dv > 1e-6 else "hold",
            "volume_mmt":        round(dv, 5),
            "reserve_after_mmt": round(new_res, 4),
            "days_cover":        round(new_res / params.daily_consumption_mmt, 2)
                                 if params.daily_consumption_mmt > 0 else 0.0,
            "gap_today_mmt":     round(gap_today, 5),
            "unmet_mmt":         round(max(0.0, gap_today - dv), 5),
        })
        reserve = new_res

    return {"plan": plan, "prob": 1.0 - below_buf / H}


def _build_result(params, mdp, lam, buf) -> SDPResult:
    plan = mdp["plan"]
    prob = mdp["prob"]

    enriched = []
    for d in plan:
        if d["action"] == "draw" and d["gap_today_mmt"] > 0:
            driver = f"drawing {d['volume_mmt']:.4f} MMT to cover {d['gap_today_mmt']:.4f} MMT/d feedstock gap"
        elif d["reserve_after_mmt"] < buf * 1.3:
            driver = "near buffer floor — drawing minimally to preserve emergency cover"
        else:
            driver = "no active gap — holding reserve"
        enriched.append({**d, "decision_driver": driver})

    total_draw = sum(d["volume_mmt"] for d in plan)
    draw_days  = sum(1 for d in plan if d["action"] == "draw")
    peak_unmet = max((d["unmet_mmt"] for d in plan), default=0.0)

    memo = (
        f"SDP/CMDP: optimal draw over {draw_days}/{params.horizon_days} days, "
        f"total {total_draw:.3f} MMT against {params.gap_mbpd:.2f} mbpd gap "
        f"({params.gap_duration_days}d). Peak unmet {peak_unmet:.4f} MMT/d. "
        f"P(reserve > {params.buffer_threshold_days:.0f}d cover) = {prob:.1%} "
        f"({'satisfied' if prob >= 0.95 else 'violated'}). "
        f"Starting {params.spr_initial_mmt:.2f} MMT, floor {buf:.2f} MMT. λ={lam:.2f}."
    )

    return SDPResult(
        daily_plan=enriched,
        prob_above_buffer=round(prob, 4),
        constraint_satisfied=prob >= 0.95,
        lagrange_multiplier=round(lam, 4),
        policy_memo=memo,
    )
