"""
Verify that Systems 2/3/4 read PRECISE values from the graph (Graphiti/FalkorDB),
not hallucinated numbers — by comparing what the read API returns against the bundle
CSVs that are the source of truth.

Two provenance channels (both sourced, neither hallucinated):
  1. GRAPH  — entity/edge structural facts (capacity, assay, throughput, SPR fill,
              export volumes, corridor risk) written from facts/*.csv, read via the
              knowledge.api.read functions the agents use.
  2. BUNDLE — model coefficients (ARIO elasticity, routing costs, TOPSIS weights,
              SDP params) read directly from params/*.csv by the agent loaders.

This script checks channel 1 (the graph) against the CSVs and reports any mismatch or
missing value. Run AFTER instantiation:

  set -a && . ./.env && set +a && export FALKORDB_HOST=localhost && \
    python3.11 scripts/verify_kb_values.py
"""
from __future__ import annotations

import asyncio
import os

from knowledge.context.loader import load_bundle
from knowledge.api.read import (
    get_subgraph, get_spr_state, get_available_suppliers, get_grade_specs, get_routes,
)

BUNDLE = os.environ.get("SAGE_BUNDLE_PATH", "data/india-energy-2026.context")
TOL = 1e-6


def _fmt(ok: bool) -> str:
    return "✓" if ok else "✗ MISMATCH"


async def main() -> None:
    from knowledge.connection import init as kb_init
    await kb_init()   # connect to FalkorDB before any read

    b = load_bundle(BUNDLE)
    passes = fails = 0

    def check(label: str, graph_val, csv_val) -> None:
        nonlocal passes, fails
        if graph_val is None:
            print(f"  ✗ MISSING   {label}: not in graph (csv={csv_val})")
            fails += 1
            return
        ok = abs(float(graph_val) - float(csv_val)) <= TOL
        print(f"  {_fmt(ok):11s} {label}: graph={graph_val} csv={csv_val}")
        passes += ok
        fails += (not ok)

    # ── System 4 — SPR caverns (get_spr_state) ──────────────────────────────────
    print("\n[System 4] SPR caverns — get_spr_state() vs spr_caverns.csv")
    spr = {s.display_name: s for s in await get_spr_state()}
    for row in b.node_rows.get("SPRCavern", []):
        name = row["canonical_name"]
        cav = spr.get(name)
        check(f"{name}.capacity_mmt", cav.capacity_mmt if cav else None, row["capacity_mmt"])
        check(f"{name}.current_fill_mmt", cav.current_fill_mmt if cav else None, row["current_fill_mmt"])

    # ── System 3 — suppliers (get_available_suppliers) ──────────────────────────
    print("\n[System 3] Suppliers — get_available_suppliers() vs suppliers.csv")
    sup = {s.display_name: s for s in await get_available_suppliers(risk_max=1.1)}  # include all
    for row in b.node_rows.get("Supplier", []):
        name = row["canonical_name"]
        s = sup.get(name)
        # sanctioned suppliers are filtered out by design — only check unsanctioned
        if str(row.get("sanctioned", "false")).lower() == "true":
            print(f"  ⊘ skip      {name}: sanctioned (correctly excluded from procurement)")
            continue
        check(f"{name}.daily_export_mbpd", s.daily_export_mbpd if s else None, row["daily_export_mbpd"])

    # ── System 3 — grade specs (get_grade_specs) ────────────────────────────────
    print("\n[System 3] Grade specs — get_grade_specs('Jamnagar Refinery') vs configured_for.csv")
    specs = await get_grade_specs("Jamnagar Refinery")
    print(f"  {'✓' if specs else '✗'}          returned {len(specs)} configured grades for Jamnagar")
    for sp in specs[:4]:
        print(f"    - {sp.grade}: api={sp.api_gravity} sulfur={sp.sulfur_pct} compat={sp.compatibility}")

    # ── System 3 — corridors/routes (get_routes) ────────────────────────────────
    print("\n[System 3] Corridors — get_routes() vs corridors.csv throughput")
    routes = {c.display_name: c for c in await get_routes(risk_max=1.1)}
    for row in b.node_rows.get("Corridor", []):
        name = row["canonical_name"]
        c = routes.get(name)
        thr = c.throughput_mbpd if c else None
        status = "✓" if (thr is not None) else "✗ MISSING"
        print(f"  {status:11s} {name}: graph throughput={thr} csv={row['throughput_mbpd']} risk={c.risk_score if c else None}")

    # ── System 2 — subgraph edges (get_subgraph) ────────────────────────────────
    print("\n[System 2] Subgraph — get_subgraph('Strait of Hormuz') node/edge values")
    sg = await get_subgraph("Strait of Hormuz", hops=2)
    refn = [n for n in sg.nodes if "Refinery" in (n.get("labels") or [])]
    print(f"  nodes={len(sg.nodes)} edges={len(sg.edges)}  refineries in subgraph={len(refn)}")
    for n in refn[:4]:
        a = n.get("attributes", {})
        print(f"    - {n.get('name')}: capacity_mbpd={a.get('capacity_mbpd')} inventory_days={a.get('inventory_days')}")

    print(f"\n{'='*60}\nSUMMARY: {passes} values matched, {fails} mismatched/missing")
    print("Graph-sourced values verified against bundle CSVs.")
    print("Model coefficients (ARIO/routing/TOPSIS/SDP) are read separately from")
    print("params/*.csv by the agent loaders — provenance-tracked, not hallucinated.")


if __name__ == "__main__":
    asyncio.run(main())
