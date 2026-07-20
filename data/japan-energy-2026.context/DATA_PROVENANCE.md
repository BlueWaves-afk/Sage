# Japan Energy Bundle — Data Provenance

This bundle demonstrates SAGE's **portability**: a second import-dependent economy
instantiated from the identical engine by swapping the context bundle. It is a
**focused, minimal bundle** (per CONTRIBUTING.md's "minimal 10-entity bundle" path),
scoped to prove multi-tenancy — not a full replacement for the India bundle's depth.

## Honesty tiers

Every row carries a `tier`:
- **real** — value published by an authoritative source (METI/ANRE, JOGMEC, EIA, IEA).
- **derived** — computed from a real aggregate via a documented method (e.g. per-refinery
  product flow derived from national consumption × supplier mix).
- **estimated** — no single authoritative per-entity figure; a documented approximation
  (per-plant refinery capacities, chokepoint severity weights, operating inventory days).

## What is Japan-real vs. shared methodology

| Layer | Source |
|---|---|
| Import dependence (~99% crude imported, ~94% from ME) | EIA-Japan / IEA-Japan — **real** |
| Supplier shares (Saudi ~40%, UAE ~38%, Kuwait ~8%, Qatar ~7%) | METI/ANRE 2023–24 — **real** |
| National stockpile ~145 days (total ~240 incl. private), JOGMEC | JOGMEC / IEA — **real** |
| Chokepoint throughput (Hormuz ~20 mbpd, Malacca ~16 mbpd) | EIA World Oil Transit Chokepoints — **real** |
| Daily crude throughput ~2.5 mbpd | EIA-Japan — **real** |
| Per-refinery capacities (ENEOS/Idemitsu/Cosmo) | operator disclosures, rounded — **estimated** (EST-refcap) |
| Per-base stockpile split (Kiire/Shibushi) | national total split — **derived** |
| Chokepoint severity weights | analyst-assigned 0–1 — **estimated** (EST-severity) |
| **Model params** (ARIO coefficients, TOPSIS weights, grade tolerances, routing method, IO structure) | **shared with the India bundle** — these are model *methodology*, not country data; documented as shared |

## Deliberately out of scope for this demonstrator
- Full IO/Leontief table specific to Japan's economy (reuses the India IO structure as a
  methodology placeholder — flagged here, not presented as Japan-specific).
- Domestic production fields (Japan has negligible domestic crude — ~0.1% self-sufficiency).
- Full narrative/source prose per entity (the India bundle carries these; this minimal
  bundle relies on structured facts + auto-synthesised pages).

The point of this bundle is **operational**: it loads through the same
`scripts/sage_instantiate.py` path with zero code changes, proving that onboarding a new
economy is a bundle swap. Depth parity with the India bundle would follow the same sourced
process.
