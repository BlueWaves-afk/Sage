"""
System 3 — Adaptive Procurement Orchestrator.

Triggered in parallel with System 4 by a new ScenarioOutput.
  1. Reads non-sanctioned suppliers (risk < 0.4) from KB
  2. Reads refinery's configured grade specs
  3. Reads open corridors (risk < 0.5) + bypass edges from bundle
  4. Scores grade compatibility for each supplier × spec
  5. Routes each supplier to minimum-cost open corridor
  6. Builds ProcurementOption list, applies TOPSIS ranking
  7. Nova Pro writes one-paragraph rationale for top-3 options
  8. Writes ProcurementRecData to KB (episode + wiki)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Literal


def _load_economics_params() -> dict:
    defaults = {"supplier_risk_max_filter": 0.4, "corridor_risk_max_filter": 0.5}
    bundle_path = os.environ.get("SAGE_BUNDLE_PATH", "")
    if not bundle_path:
        return defaults
    try:
        from knowledge.context.loader import load_bundle
        ep = load_bundle(bundle_path).economics_params
        return {k: float(ep.get(k, {"value": v})["value"]) for k, v in defaults.items()}
    except Exception:
        return defaults

from contracts.outputs import ProcurementOption, ProcurementRecData
from knowledge.api.read import get_available_suppliers, get_grade_specs, get_routes
from knowledge.api.write import write_procurement

from alt_procurement_agent.grade import best_compatibility
from alt_procurement_agent.routing import solve as solve_routes
from alt_procurement_agent.rank import rank as topsis_rank

log = logging.getLogger(__name__)

Status = Literal["speculative", "confirmed"]

# Compiled fallbacks used only when the bundle can't be loaded. The authoritative
# values are sourced live from the bundle by the loaders below — nothing here is the
# source of truth; these mirror crude_grades.csv / bypass_routes.csv for offline safety.
_DEFAULT_SUPPLIER_GRADE: dict[str, tuple[float, float]] = {
    "Saudi Arabia":         (32.8, 1.96), "Iraq":                 (27.9, 3.00),
    "United Arab Emirates": (40.2, 0.79), "Kuwait":               (31.0, 2.55),
    "Qatar":                (36.0, 1.40), "Russia":               (31.3, 1.30),
    "Nigeria":              (38.0, 0.37), "United States":        (40.0, 0.40),
    "Brazil":               (29.0, 0.40), "Venezuela":            (16.0, 2.50),
    "Kazakhstan":           (45.0, 0.55), "Angola":               (32.0, 0.13),
}
_DEFAULT_BYPASS_EDGES = [
    {"src": "Saudi Aramco", "via_corridor": "Suez Canal",        "cost_premium": 2.50, "added_days": 10.0},
    {"src": "ADNOC",         "via_corridor": "Cape of Good Hope", "cost_premium": 1.20, "added_days": 2.0},
]

# Which corridor a bypass destination PORT feeds into, for corridor-risk lookup.
# (bypass_routes.csv models supplier->port; the router is corridor-based, so this
# maps the physical bypass port to the downstream corridor whose risk applies.)
_BYPASS_PORT_CORRIDOR = {
    "Yanbu":    "Suez Canal",         # Petroline -> Red Sea -> Suez
    "Fujairah": "Cape of Good Hope",  # ADCOP -> Gulf of Oman (open ocean, low risk)
}


def _bundle_path() -> str:
    return os.environ.get("SAGE_BUNDLE_PATH",
                          os.environ.get("SAGE_CONTEXT_BUNDLE", "data/india-energy-2026.context"))


def _load_supplier_grades() -> dict[str, tuple[float, float]]:
    """
    Representative crude assay (API, sulfur) per supplier country, sourced from the
    bundle's crude_grades.csv (real assays). First grade per origin = the marker grade
    (e.g. Arab Light for Saudi Arabia). Falls back to the compiled mirror if unavailable.
    """
    try:
        from knowledge.context.loader import load_bundle
        out: dict[str, tuple[float, float]] = {}
        for row in load_bundle(_bundle_path()).node_rows.get("CrudeGrade", []):
            country = (row.get("origin") or "").strip()
            if country and country not in out:
                out[country] = (float(row["api_gravity"]), float(row["sulfur_pct"]))
        return out or _DEFAULT_SUPPLIER_GRADE
    except Exception:
        return _DEFAULT_SUPPLIER_GRADE


def _bundle_supplier_facts() -> dict[str, dict]:
    """Provenance-backed supplier facts keyed by canonical supplier name."""
    from knowledge.context.loader import load_bundle

    facts: dict[str, dict] = {}
    for row in load_bundle(_bundle_path()).node_rows.get("Supplier", []):
        if str(row.get("sanctioned", "false")).lower() == "true":
            continue
        name = str(row.get("canonical_name") or "").strip()
        if name:
            facts[name] = row
    return facts


def _verified_suppliers(suppliers: list) -> list:
    """Drop extraction noise and restore missing attributes from the active bundle."""
    facts = _bundle_supplier_facts()
    verified = []
    for supplier in suppliers:
        fact = facts.get(supplier.display_name)
        if fact is None:
            continue
        verified.append(
            supplier.model_copy(
                update={
                    "country": str(fact.get("country") or "") or None,
                    "daily_export_mbpd": float(fact["daily_export_mbpd"]),
                }
            )
        )
    return verified


def _candidate_compatibility(
    country: str,
    api_gravity: float,
    sulfur_pct: float,
    grade_specs: list,
) -> float:
    candidate_grade = _grade_name(country)
    exact = next((spec for spec in grade_specs if spec.grade == candidate_grade), None)
    if exact is not None and exact.compatibility is not None:
        return float(exact.compatibility)
    assay_specs = [spec.model_copy(update={"compatibility": None}) for spec in grade_specs]
    return best_compatibility(api_gravity, sulfur_pct, assay_specs)


def _load_bypass_edges() -> list[dict]:
    """
    Bypass routes sourced from the bundle's bypass_routes.csv — resolves supplier/port
    entity_ids to canonical names and maps the bypass port to its downstream corridor
    for risk lookup. cost_premium / added_days come straight from the bundle.
    """
    try:
        from knowledge.context.loader import load_bundle
        from knowledge.registry import canonical_name
        out: list[dict] = []
        for row in load_bundle(_bundle_path()).edge_rows.get("BYPASS_ROUTE", []):
            src_port = canonical_name(row["dst_entity_id"]) or row["dst_entity_id"]
            out.append({
                "src":          canonical_name(row["src_entity_id"]) or row["src_entity_id"],
                "via_corridor": _BYPASS_PORT_CORRIDOR.get(src_port, "Suez Canal"),
                "cost_premium": float(row["cost_premium"]),
                "added_days":   float(row["added_days"]),
            })
        return out or _DEFAULT_BYPASS_EDGES
    except Exception:
        return _DEFAULT_BYPASS_EDGES


async def run(
    scenario_id: str,
    trigger_refinery: str,
    status: Status = "confirmed",
    gap_mbpd: float = 0.5,
) -> str:
    """
    Full procurement run. Returns scenario_id on completion.
    `gap_mbpd` from ScenarioOutputData scopes how much volume to source.
    """
    ep = _load_economics_params()
    supplier_risk_max = ep["supplier_risk_max_filter"]
    corridor_risk_max = ep["corridor_risk_max_filter"]

    suppliers = _verified_suppliers(
        await get_available_suppliers(risk_max=supplier_risk_max)
    )
    grade_specs = await get_grade_specs(trigger_refinery)
    # Fetch ALL corridors here (not pre-filtered) — solve_routes() below applies
    # corridor_risk_max itself using each corridor's real risk_score. Pre-filtering
    # here was a real bug: a corridor excluded for being too risky (e.g. Hormuz at
    # 0.92 during a live crisis) would then be MISSING from `corridors`, and
    # solve_routes()'s "not in KB yet" fallback treated "missing" as "safe, risk=0.1"
    # — silently routing crude back through the very corridor that's in crisis.
    corridors  = await get_routes(risk_max=1.1)

    if not suppliers:
        log.warning("[procurement] no non-sanctioned suppliers returned from KB")

    # Bundle-sourced supplier assays + bypass routes (no hardcoded values).
    supplier_grades = _load_supplier_grades()
    bypass_edges    = _load_bypass_edges()

    # Destination-port congestion (async graph read) — fetched here and passed
    # into the sync solver. Best-effort: no congestion on any error.
    try:
        from knowledge.api.read import get_port_congestion
        port_congestion = await get_port_congestion()
    except Exception:
        port_congestion = {}

    # Route each supplier to their best open corridor
    routes = solve_routes(
        suppliers, corridors, bypass_edges,
        risk_max=corridor_risk_max, port_congestion=port_congestion,
    )

    options: list[ProcurementOption] = []
    for supplier in suppliers:
        route = routes.get(supplier.display_name)
        if route is None:
            continue  # all routes blocked for this supplier

        country = supplier.country or ""
        api, sulfur = supplier_grades.get(country, (32.0, 1.8))
        compat = _candidate_compatibility(country, api, sulfur, grade_specs)

        options.append(ProcurementOption(
            supplier=supplier.display_name,
            grade=_grade_name(country),
            route_via=route.corridor,
            landed_cost_usd_bbl=route.landed_cost_usd_bbl,
            lead_time_days=route.lead_time_days,
            grade_compatibility=compat,
            corridor_risk=route.corridor_risk,
            congestion_delay_days=route.congestion_delay_days,
            tanker_availability=route.tanker_availability,
            tanker_availability_note=route.tanker_availability_note,
            topsis_score=0.0,      # populated by topsis_rank
            rationale="",          # populated below for top-3
            episode_citations=[],
        ))

    ranked = topsis_rank(options)

    for opt in ranked:
        opt.rationale = _deterministic_rationale(opt)

    data = ProcurementRecData(
        scenario_id=scenario_id,
        status=status,
        target_refinery=trigger_refinery,
        ranked=ranked,
    )
    await write_procurement(data)
    log.info("[procurement] wrote %d ranked options for %s (scenario %s)",
             len(ranked), trigger_refinery, scenario_id)
    if ranked:
        asyncio.create_task(
            _enrich_rationales(data, trigger_refinery, gap_mbpd),
            name=f"procurement-rationale-{scenario_id}",
        )
    return scenario_id


def _deterministic_rationale(opt: ProcurementOption) -> str:
    extra = ""
    if opt.congestion_delay_days > 0.05:
        extra += f" Port congestion adds {opt.congestion_delay_days:.1f}d berth wait."
    if opt.tanker_availability < 0.8:
        extra += f" {opt.tanker_availability_note}."
    return (
        f"{opt.supplier} ({opt.grade}) via {opt.route_via}: "
        f"TOPSIS {opt.topsis_score:.2f}, cost ${opt.landed_cost_usd_bbl:.2f}/bbl, "
        f"{opt.lead_time_days:.0f}d lead, compatibility {opt.grade_compatibility:.2f}.{extra}"
    )


async def _enrich_rationales(
    data: ProcurementRecData,
    refinery: str,
    gap_mbpd: float,
) -> None:
    try:
        enriched = await asyncio.gather(*(
            asyncio.wait_for(_nova_rationale(opt, refinery, gap_mbpd), timeout=25)
            for opt in data.ranked[:3]
        ))
        for opt, rationale in zip(data.ranked[:3], enriched):
            opt.rationale = rationale
        await write_procurement(data)
    except Exception as exc:
        log.warning("[procurement] rationale enrichment skipped: %s", exc)


async def _nova_rationale(opt: ProcurementOption, refinery: str, gap_mbpd: float) -> str:
    try:
        from knowledge.synthesis import _call_nova_pro
        congestion_note = (
            f"Destination-port congestion adds {opt.congestion_delay_days:.1f}d berth wait. "
            if opt.congestion_delay_days > 0.05 else ""
        )
        prompt = (
            f"You are SAGE's procurement analyst. Write ONE concise paragraph (4-6 sentences) "
            f"explaining why {opt.supplier} ({opt.grade}) routed via {opt.route_via} "
            f"is a strong option to bridge a {gap_mbpd:.2f} mbpd supply gap at {refinery}.\n"
            f"TOPSIS score: {opt.topsis_score:.2f}. "
            f"Landed cost: ${opt.landed_cost_usd_bbl:.2f}/bbl. "
            f"Lead time: {opt.lead_time_days:.0f} days. "
            f"Grade compatibility: {opt.grade_compatibility:.2f}/1.0. "
            f"Corridor risk: {opt.corridor_risk:.2f}/1.0. "
            f"{congestion_note}"
            f"Tanker availability: {opt.tanker_availability_note}. "
            f"Score breakdown: {opt.score_breakdown}.\n"
            f"Be specific about the grade's processing characteristics, the route's risk profile, "
            f"and any trade-offs (e.g. longer lead time offset by lower cost, or high compatibility "
            f"offsetting a slightly elevated corridor risk). Mention port congestion and tanker "
            f"availability if they materially affect lead time. Do not use bullet points."
        )
        return await _call_nova_pro(prompt, opt.supplier)
    except Exception as exc:
        log.warning("[procurement] Nova Pro rationale failed for %s: %s", opt.supplier, exc)
        return (
            f"{opt.supplier} ({opt.grade}) via {opt.route_via}: "
            f"TOPSIS {opt.topsis_score:.2f}, cost ${opt.landed_cost_usd_bbl:.2f}/bbl, "
            f"{opt.lead_time_days:.0f}d lead time, compatibility {opt.grade_compatibility:.2f}."
        )


_DEFAULT_GRADE_NAME = {
    "Saudi Arabia": "Arab Light", "Iraq": "Basrah Medium", "United Arab Emirates": "Murban",
    "Kuwait": "Kuwait Export Crude", "Qatar": "Qatar Marine", "Russia": "Urals",
    "Nigeria": "Bonny Light", "United States": "WTI Midland", "Brazil": "Tupi",
    "Venezuela": "Merey", "Kazakhstan": "CPC Blend", "Angola": "Cabinda",
}


def _load_grade_names() -> dict[str, str]:
    """Marker grade NAME per origin country, sourced from crude_grades.csv (first per origin)."""
    try:
        from knowledge.context.loader import load_bundle
        out: dict[str, str] = {}
        for row in load_bundle(_bundle_path()).node_rows.get("CrudeGrade", []):
            country = (row.get("origin") or "").strip()
            if country and country not in out:
                out[country] = row.get("canonical_name", "Unknown Grade")
        return out or _DEFAULT_GRADE_NAME
    except Exception:
        return _DEFAULT_GRADE_NAME


def _grade_name(country: str) -> str:
    return _load_grade_names().get(country, "Unknown Grade")


# ── Worker service loop ───────────────────────────────────────────────────────
# Entry point for the standalone `python -m alt_procurement_agent.runner`
# container. Consumes procurement jobs from a Redis queue so the container is a
# stable, horizontally-scalable worker instead of a process that imports and
# exits. Idle = blocking pop (stable). The in-process path in
# orchestration/graph.py stays the default; enqueue a JSON job to
# PROCUREMENT_JOB_QUEUE to offload a run here.
#
# Job shape: {"scenario_id": str, "trigger_refinery": str,
#             "status": "confirmed"|"speculative", "gap_mbpd": float,
#             "result_key": str|null}

PROCUREMENT_JOB_QUEUE = os.environ.get("PROCUREMENT_JOB_QUEUE", "sage:procurement_jobs")
_HEARTBEAT_KEY        = "sage:worker:procurement:heartbeat"


_kb_ready = False


async def _ensure_kb() -> None:
    """Lazily init the KB the first time a real job arrives. The slim worker
    image may not carry the full KB stack; a worker with no jobs never needs it
    and stays a stable idle consumer."""
    global _kb_ready
    if not _kb_ready:
        from knowledge.connection import init as kb_init
        await kb_init()
        _kb_ready = True


async def _serve() -> None:
    import redis.asyncio as aioredis
    from redis.exceptions import TimeoutError as RedisTimeoutError

    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    # socket_timeout=None so the blocking BLPOP isn't cut short by a read timeout.
    client = aioredis.from_url(redis_url, decode_responses=True, socket_timeout=None)
    log.info("alt_procurement_agent worker started (idle-ready); queue=%s", PROCUREMENT_JOB_QUEUE)

    try:
        while True:
            try:
                res = await client.blpop(PROCUREMENT_JOB_QUEUE, timeout=5)
            except (RedisTimeoutError, asyncio.TimeoutError):
                res = None
            try:
                await client.set(_HEARTBEAT_KEY,
                                 datetime.now(timezone.utc).isoformat(), ex=30)
            except Exception:
                pass
            if not res:
                continue
            try:
                _, raw = res
                job = json.loads(raw)
                await _ensure_kb()
                scenario_id = await run(
                    scenario_id=job["scenario_id"],
                    trigger_refinery=job["trigger_refinery"],
                    status=job.get("status", "confirmed"),
                    gap_mbpd=float(job.get("gap_mbpd", 0.5)),
                )
                result_key = job.get("result_key")
                if result_key:
                    await client.rpush(result_key, json.dumps({"scenario_id": scenario_id}))
                    await client.expire(result_key, 120)
                log.info("procurement job complete: %s", scenario_id)
            except Exception as exc:
                log.error("procurement worker job failed: %s", exc)
                await asyncio.sleep(1)
    finally:
        await client.aclose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(_serve())
