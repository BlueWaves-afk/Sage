"""
Scenario parameterisation node (the bridge between System 1 signals and System 2).

When a risk threshold crosses, this LangGraph node reads the LIVE signal context
(current risk score + factor breakdown + recent signals) and asks the LLM to translate
it into System 2's scenario parameters — how bad is the disruption, how long, is it
escalating, is the bypass also compromised, what SPR stance. This is what makes the
scenario RESPONSIVE to the actual situation instead of always assuming full closure.

A deterministic heuristic fallback runs when the LLM is unavailable or System 1 hasn't
produced signals yet, so the path always yields sane parameters.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

log = logging.getLogger(__name__)

_HEURISTIC_DEFAULTS = {
    "heuristic_default_risk_score":        0.7,
    "heuristic_severity_lower_bound":      0.3,
    "heuristic_severity_width":            0.6,
    "heuristic_sanctions_factor_threshold": 0.5,
    "heuristic_disruption_days_if_sanctions": 30,
    "heuristic_disruption_days_if_normal": 14,
    "heuristic_escalation_score_threshold": 0.8,
    "heuristic_spr_aggressive_threshold":  0.9,
    "heuristic_max_disruption_days":       180,
    "heuristic_max_demand_destruction_pct": 0.30,
}


def _load_heuristic_params() -> dict:
    bundle_path = os.environ.get("SAGE_BUNDLE_PATH", "")
    if not bundle_path:
        return _HEURISTIC_DEFAULTS.copy()
    try:
        from knowledge.context.loader import load_bundle
        hp = load_bundle(bundle_path).heuristic_params
        return {k: float(hp.get(k, {"value": v})["value"]) for k, v in _HEURISTIC_DEFAULTS.items()}
    except Exception:
        return _HEURISTIC_DEFAULTS.copy()

_VALID_ESCALATION = {"constant", "escalating", "resolving"}
_VALID_SPR = {"aggressive", "moderate", "none"}


async def decide_scenario_params(entity: str, risk: Optional[object] = None) -> dict:
    """
    Returns the scenario dict for scenario_agent.runner.run(entity, scenario=...).
    `risk` is the RiskScoreView for the entity (from get_risk_scores); may be None.
    """
    if risk is None:
        risk = await _current_risk(entity)

    llm = await _llm_decide(entity, risk)
    if llm:
        return _sanitise(llm)
    return _heuristic(risk)


# ── LLM path ──────────────────────────────────────────────────────────────────

async def _llm_decide(entity: str, risk) -> Optional[dict]:
    try:
        from knowledge.synthesis import _call_nova_pro
        f = getattr(risk, "factors", {}) or {}
        prompt = (
            f"You are SAGE's scenario parameteriser. A risk threshold just crossed for the "
            f"oil corridor \"{entity}\".\n"
            f"Current fused risk: {getattr(risk,'score',0):.2f} (band {getattr(risk,'band','?')}).\n"
            f"Factor breakdown — AIS/dark-vessel {f.get('ais',0):.2f}, news/GDELT {f.get('gdelt',0):.2f}, "
            f"price/war-risk {f.get('price',0):.2f}, sanctions {f.get('sanctions',0):.2f}.\n"
            f"Rationale: {getattr(risk,'rationale','') or 'n/a'}.\n\n"
            f"Translate this into a physical disruption scenario. Reason about severity from the "
            f"factors (a naval exercise + a few dark vessels = partial 0.3-0.5; a declared closure = 1.0; "
            f"sustained sanctions widen duration; a Red Sea + Hormuz combo compromises the bypass).\n"
            f"Return ONLY JSON with these keys:\n"
            f'{{"disruption_fraction": 0..1, "disruption_days": int, '
            f'"escalation_profile": "constant|escalating|resolving", '
            f'"bypass_compromised_frac": 0..1, "spr_policy": "aggressive|moderate|none", '
            f'"demand_destruction_pct": 0..0.3, "rationale": "one sentence"}}'
        )
        raw = await _call_nova_pro(prompt, entity)
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw[start:end + 1])
    except Exception as exc:
        log.warning("scenario-param LLM failed for '%s': %s — heuristic fallback", entity, exc)
    return None


# ── Deterministic fallback ──────────────────────────────────────────────────────

def _heuristic(risk) -> dict:
    p = _load_heuristic_params()
    score = float(getattr(risk, "score", p["heuristic_default_risk_score"]) or p["heuristic_default_risk_score"])
    f = getattr(risk, "factors", {}) or {}
    frac = max(0.1, min(1.0, (score - p["heuristic_severity_lower_bound"]) / p["heuristic_severity_width"]))
    sanctions_heavy = float(f.get("sanctions", 0)) > p["heuristic_sanctions_factor_threshold"]
    return {
        "disruption_fraction": round(frac, 2),
        "disruption_days": int(p["heuristic_disruption_days_if_sanctions"]) if sanctions_heavy
                           else int(p["heuristic_disruption_days_if_normal"]),
        "escalation_profile": "escalating" if score < p["heuristic_escalation_score_threshold"] else "constant",
        "bypass_compromised_frac": 0.0,
        "spr_policy": "aggressive" if score >= p["heuristic_spr_aggressive_threshold"] else "moderate",
        "demand_destruction_pct": 0.0,
        "rationale": f"heuristic from risk {score:.2f}",
    }


async def _current_risk(entity: str):
    try:
        from knowledge.api.read import get_risk_scores
        scores = await get_risk_scores()
        return next((s for s in scores if s.entity == entity), None)
    except Exception:
        return None


def _sanitise(d: dict) -> dict:
    p = _load_heuristic_params()
    out = {}
    out["disruption_fraction"] = max(0.0, min(1.0, float(d.get("disruption_fraction", 1.0))))
    out["disruption_days"] = int(max(1, min(int(p["heuristic_max_disruption_days"]), d.get("disruption_days", 30))))
    out["escalation_profile"] = d.get("escalation_profile") if d.get("escalation_profile") in _VALID_ESCALATION else "constant"
    out["bypass_compromised_frac"] = max(0.0, min(1.0, float(d.get("bypass_compromised_frac", 0.0))))
    out["spr_policy"] = d.get("spr_policy") if d.get("spr_policy") in _VALID_SPR else "moderate"
    out["demand_destruction_pct"] = max(0.0, min(p["heuristic_max_demand_destruction_pct"], float(d.get("demand_destruction_pct", 0.0))))
    if d.get("rationale"):
        out["rationale"] = str(d["rationale"])[:200]
    return out
