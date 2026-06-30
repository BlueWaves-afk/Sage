"""
Context bundle loader, validator, and episode generator.

A bundle directory looks like:

    india-energy-2026.context/
    ├── manifest.yaml          # metadata, source registry, estimation methods
    ├── nodes/*.csv            # one CSV per node type
    └── edges/*.csv            # one CSV per edge type

Every CSV row MUST carry a `tier` (real|derived|estimated) and a `source` that
resolves to either manifest.sources or manifest.estimation_methods. This is the
"no unsourced data" guarantee — validate_bundle() fails the build otherwise.

The loader turns the structured rows into Graphiti episodes (prose that states
every property explicitly) so the same add_episode() write path used everywhere
else extracts the typed node/edge fields. See data/CONTEXT_BUNDLE_SCHEMA.md.
"""
from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

log = logging.getLogger(__name__)

VALID_TIERS = {"real", "derived", "estimated"}


class BundleValidationError(Exception):
    """Raised when a bundle has unsourced rows, bad tiers, or missing files."""


@dataclass
class ContextBundle:
    path:        Path
    manifest:    dict[str, Any]
    node_rows:   dict[str, list[dict]] = field(default_factory=dict)   # type -> rows
    edge_rows:   dict[str, list[dict]] = field(default_factory=dict)   # type -> rows
    narratives:  dict[str, dict] = field(default_factory=dict)         # entity_id -> {body, frontmatter}

    # ── metadata ──────────────────────────────────────────────────────────────
    @property
    def bundle_id(self) -> str:
        return self.manifest.get("bundle_id", self.path.name)

    @property
    def schema_version(self) -> str:
        return str(self.manifest.get("schema_version", "?"))

    def summary(self) -> dict[str, Any]:
        """Counts by node/edge type and by provenance tier."""
        tier_counts: dict[str, int] = {"real": 0, "derived": 0, "estimated": 0}
        for rows in list(self.node_rows.values()) + list(self.edge_rows.values()):
            for r in rows:
                tier_counts[r.get("tier", "estimated")] = tier_counts.get(r.get("tier", "estimated"), 0) + 1
        return {
            "bundle_id":   self.bundle_id,
            "schema":      self.schema_version,
            "nodes":       {t: len(rows) for t, rows in self.node_rows.items()},
            "edges":       {t: len(rows) for t, rows in self.edge_rows.items()},
            "narratives":  len(self.narratives),
            "by_tier":     tier_counts,
        }

    def all_entity_ids(self) -> list[str]:
        """Every entity_id declared in the facts node CSVs (ordered, de-duped)."""
        seen: list[str] = []
        for rows in self.node_rows.values():
            for r in rows:
                eid = r.get("entity_id")
                if eid and eid not in seen:
                    seen.append(eid)
        return seen

    def _connected_names(self, entity_id: str) -> list[str]:
        """Canonical names of entities linked to this one by any edge (both directions)."""
        names: list[str] = []
        for rows in self.edge_rows.values():
            for r in rows:
                other = None
                if r.get("src_entity_id") == entity_id:
                    other = r.get("dst_entity_id")
                elif r.get("dst_entity_id") == entity_id:
                    other = r.get("src_entity_id")
                if other:
                    nm = _cname(other)
                    if nm not in names:
                        names.append(nm)
        return names

    def _entity_facts(self, entity_id: str) -> str:
        """Compact 'key=value' string of an entity's structured facts (for LLM grounding)."""
        meta = {"entity_id", "canonical_name", "tier", "source", "as_of", "notes"}
        for rows in self.node_rows.values():
            for r in rows:
                if r.get("entity_id") == entity_id:
                    return ", ".join(f"{k}={v}" for k, v in r.items() if k not in meta and v)
        return ""

    def _read_source(self, entity_id: str) -> str:
        """Cached source evidence for an entity (sources/<entity_id>.md), if present."""
        src_dir = self.path / self.manifest.get("sources_dir", "sources")
        f = src_dir / f"{entity_id}.md"
        if f.is_file():
            return f.read_text(encoding="utf-8").strip()
        return ""

    async def _grounded_author(self, entity_id: str, canonical: str, etype: str) -> str:
        """
        Write a SOURCE-GROUNDED narrative: Nova Pro summarises the cached source
        material (sources/<entity_id>.md, fetched from real URLs) + the structured
        facts into a factual page with [[wikilinks]]. Strictly RAG — the model is
        told to use ONLY the provided material, which prevents hallucination.
        """
        from knowledge.synthesis import _call_nova_pro
        rels = self._connected_names(entity_id)
        facts = self._entity_facts(entity_id)
        source_text = self._read_source(entity_id)
        rel_hint = ", ".join(rels) if rels else "(none in this bundle)"

        prompt = (
            f"You are writing a factual foundational intelligence page for the {etype} "
            f'"{canonical}" in an oil supply-chain knowledge base.\n\n'
            f"STRICT GROUNDING RULES:\n"
            f"- Use ONLY the SOURCE MATERIAL and STRUCTURED FACTS below.\n"
            f"- Do NOT add any figure, date, name, or claim that is not present in them.\n"
            f"- If the material is thin, keep the page short. Never speculate.\n"
            f"- Reference related tracked entities as [[Canonical Name]] wikilinks where the "
            f"material supports it. Candidates: {rel_hint}.\n"
            f"- 2-4 short sections with ## headers. No preamble — start at the first ## header.\n\n"
            f"STRUCTURED FACTS: {facts or 'n/a'}\n\n"
            f"SOURCE MATERIAL:\n{source_text}\n"
        )
        return await _call_nova_pro(prompt, canonical)

    async def _llm_author(self, entity_id: str, canonical: str, etype: str) -> str:
        """
        Facts-only authoring (no source material). Lower-grounding fallback used when
        no sources/<entity_id>.md exists. Constrained to the structured facts so it
        cannot invent figures, but prose framing comes from the model.
        """
        from knowledge.synthesis import _call_nova_pro
        rels = self._connected_names(entity_id)
        facts = self._entity_facts(entity_id)
        prompt = (
            f"Write a concise, factual foundational intelligence page for the {etype} "
            f'"{canonical}" in an oil supply-chain knowledge base.\n'
            f"Use 2-3 short sections with ## headers (e.g. Profile, Role, Risk).\n"
            f"Reference these related tracked entities as [[Canonical Name]] wikilinks where "
            f"relevant: {', '.join(rels) if rels else '(none in this bundle)'}.\n"
            f"Known structured facts (do not contradict, do not invent new figures): {facts or 'n/a'}.\n"
            f"Do not introduce specific figures or dates beyond the facts above. "
            f"No preamble — start with the first ## header."
        )
        return await _call_nova_pro(prompt, canonical)

    def _foundational_stub(self, entity_id: str, canonical: str, etype: str) -> str:
        """
        Deterministic foundational page for an entity with no hand-authored narrative.
        Built from the facts + graph relationships so even auto-pages carry [[wikilinks]].
        """
        rels = self._connected_names(entity_id)
        rel_lines = "\n".join(f"- [[{n}]]" for n in rels) or "- (no structural relationships in this bundle)"
        return (
            f"## Profile\n"
            f"[[{canonical}]] is a {etype} tracked in the {self.bundle_id} context bundle. "
            f"Structured attributes (capacity, assay, throughput, etc.) are carried on its graph "
            f"node; see the facts layer for sourced values.\n\n"
            f"## Relations\n{rel_lines}\n\n"
            f"_Foundational stub — auto-generated from facts. Replace with a hand-authored "
            f"narrative in narratives/{entity_id}.md to enrich._\n"
        )

    # ── episode generation (facts layer) ──────────────────────────────────────
    def to_episodes(self) -> list[dict]:
        """
        Render the FACTS layer as structural episodes for add_episode().
        Structured ground-truth values (capacity, assay, throughput, …) — written
        directly, NOT reconciled by the LLM. One episode per node/edge type.
        """
        episodes: list[dict] = []
        for ntype, rows in self.node_rows.items():
            body = " ".join(_NODE_FORMATTERS[ntype](r) for r in rows)
            episodes.append({
                "name":        f"ctx-{self.bundle_id}-node-{ntype.lower()}",
                "body":        f"Structural reference data for {ntype} entities. {body}",
                "source_desc": f"Context bundle {self.bundle_id} — {ntype}",
            })
        for etype, rows in self.edge_rows.items():
            body = " ".join(_EDGE_FORMATTERS[etype](r) for r in rows)
            episodes.append({
                "name":        f"ctx-{self.bundle_id}-edge-{etype.lower()}",
                "body":        f"Structural supply-chain relationships ({etype}). {body}",
                "source_desc": f"Context bundle {self.bundle_id} — {etype}",
            })
        return episodes

    # ── instantiation (the SAGE.from_pretrained step) ─────────────────────────
    async def instantiate(
        self,
        graphiti,
        reference_time=None,
        author_missing_with_llm: bool = False,
        canonicalize: bool = True,
        on_progress=None,
    ) -> dict[str, int]:
        """
        Load the bundle's foundational knowledge into all three stores.

        Phase 1 — FACTS: structured ground-truth → structural episodes → add_episode().
                  Deterministic graph attributes; the LLM does not reconcile known numbers.
        Phase 2 — NARRATIVES: per-entity prose → render_wiki_page() → write_wiki_page()
                  (wiki store) + add_episode() of the body (episodic + semantic + vector).
                  This is the SAME synthesis path System 1 uses for live signals — it
                  resolves [[wikilinks]], builds links_out (relations), and reconciles.
                  Entities without a hand-authored narrative get a foundational stub
                  generated from their facts + relationships, so Store 3 is fully covered.

        Returns {facts, narratives} episode counts.
        """
        from datetime import datetime, timezone
        from graphiti_core.nodes import EpisodeType
        from knowledge.schema.entities import ENTITY_TYPES
        from knowledge.schema.edges import EDGE_TYPES, EDGE_TYPE_MAP
        from knowledge.synthesis import render_wiki_page, write_wiki_page
        from knowledge.registry import REGISTRY

        ref = reference_time or datetime.now(timezone.utc)

        # ── Phase 1: facts → graph attributes ──────────────────────────────────
        fact_eps = self.to_episodes()
        facts_written = 0
        for i, ep in enumerate(fact_eps, 1):
            if on_progress:
                on_progress("facts", ep["name"], i, len(fact_eps))
            try:
                await graphiti.add_episode(
                    name=ep["name"], episode_body=ep["body"], source=EpisodeType.text,
                    source_description=ep["source_desc"], reference_time=ref,
                    entity_types=ENTITY_TYPES, edge_types=EDGE_TYPES, edge_type_map=EDGE_TYPE_MAP,
                )
                facts_written += 1
                log.info("  facts: %s", ep["name"])
            except Exception as exc:
                log.warning("  facts FAILED (%s): %s", ep["name"], exc)

        # ── Phase 2: narratives → synthesis path → wiki + reconciled episode ───
        eids = self.all_entity_ids()
        narr_written = 0
        for i, entity_id in enumerate(eids, 1):
            entry = REGISTRY.get(entity_id)
            canonical = entry.canonical_name if entry else entity_id
            etype = entry.entity_type if entry else "Unknown"

            # Precedence: hand-authored prose > source-grounded synthesis >
            #             facts-only LLM > deterministic stub.
            authored = self.narratives.get(entity_id)
            has_source = bool(self._read_source(entity_id))
            if authored:
                body, authored_flag = authored["body"], "authored"
            elif author_missing_with_llm and has_source:
                if on_progress:
                    on_progress("synthesizing", f"{canonical} (grounded)", i, len(eids))
                body, authored_flag = await self._grounded_author(entity_id, canonical, etype), "grounded"
            elif author_missing_with_llm:
                if on_progress:
                    on_progress("synthesizing", f"{canonical} (facts-only)", i, len(eids))
                body, authored_flag = await self._llm_author(entity_id, canonical, etype), "llm-authored"
            else:
                body, authored_flag = self._foundational_stub(entity_id, canonical, etype), "stub"

            if on_progress:
                on_progress("narrative", f"{canonical} ({authored_flag})", i, len(eids))

            try:
                # render_wiki_page builds frontmatter, resolves [[wikilinks]], rebuilds links_out
                page = render_wiki_page(canonical, body, entity_id=entity_id, entity_type=etype)
                write_wiki_page(canonical, page)                       # Store 3 (wiki)
                await graphiti.add_episode(                            # Stores 1 & 2 (episodic + semantic + vector)
                    name=f"ctx-{self.bundle_id}-wiki-{entity_id}",
                    episode_body=_strip_frontmatter(page),
                    source=EpisodeType.text,
                    source_description=f"Context bundle {self.bundle_id} — narrative ({authored_flag})",
                    reference_time=ref,
                    entity_types=ENTITY_TYPES, edge_types=EDGE_TYPES, edge_type_map=EDGE_TYPE_MAP,
                )
                narr_written += 1
                log.info("  narrative (%s): %s", authored_flag, entity_id)
            except Exception as exc:
                log.warning("  narrative FAILED (%s): %s", entity_id, exc)

        # ── Phase 3: canonicalize — dedup edges + merge alias-variant nodes ────
        dedup = {"edges_removed": 0, "nodes_merged": 0}
        if canonicalize:
            if on_progress:
                on_progress("canonicalizing", "dedup edges + merge alias nodes", len(eids), len(eids))
            from knowledge.context.dedup import canonicalize_graph, reconcile_edge_attributes
            dedup = await canonicalize_graph(graphiti)
            # Overwrite LLM-extracted edge numerics with exact facts values (ARIO needs these).
            dedup["edges_reconciled"] = await reconcile_edge_attributes(self)

        return {"facts": facts_written, "narratives": narr_written, **dedup}


# ── prose formatters (one fact per sentence → reliable LLM extraction) ────────

def _cname(entity_id: str) -> str:
    """Resolve entity_id → canonical name via the registry."""
    from knowledge.registry import REGISTRY
    entry = REGISTRY.get(entity_id)
    return entry.canonical_name if entry else entity_id


def _fmt_corridor(r: dict) -> str:
    return (f"{r['canonical_name']} (Corridor) has throughput_mbpd of {r['throughput_mbpd']} "
            f"and choke_severity {r['choke_severity']}, located at latitude {r['location_lat']}, "
            f"longitude {r['location_lon']}.")


def _fmt_supplier(r: dict) -> str:
    sanc = "is sanctioned" if str(r["sanctioned"]).lower() == "true" else "is not sanctioned"
    return (f"{r['canonical_name']} (Supplier) is based in country {r['country']}, has "
            f"daily_export_mbpd of {r['daily_export_mbpd']}, and {sanc}.")


def _fmt_refinery(r: dict) -> str:
    return (f"{r['canonical_name']} (Refinery) has capacity_mbpd of {r['capacity_mbpd']} "
            f"and inventory_days of {r['inventory_days']}, located at latitude {r['location_lat']}, "
            f"longitude {r['location_lon']}.")


def _fmt_crude_grade(r: dict) -> str:
    return (f"{r['canonical_name']} (CrudeGrade) has api_gravity {r['api_gravity']} and "
            f"sulfur_pct {r['sulfur_pct']}, origin {r['origin']}.")


def _fmt_port(r: dict) -> str:
    return (f"{r['canonical_name']} (Port) has draft_m of {r['draft_m']} and congestion "
            f"{r['congestion']}, located at latitude {r['location_lat']}, longitude {r['location_lon']}.")


def _fmt_spr(r: dict) -> str:
    return (f"{r['canonical_name']} (SPRCavern) has capacity_mmt of {r['capacity_mmt']} and "
            f"current_fill_mmt of {r['current_fill_mmt']}, location {r['location']}.")


def _fmt_authority(r: dict) -> str:
    return f"{r['canonical_name']} (Authority) has jurisdiction {r['jurisdiction']}."


def _fmt_geoevent(r: dict) -> str:
    return (f"{r['canonical_name']} (GeoEvent): actor {r.get('actor','')}, "
            f"action {r.get('action','')}, severity {r.get('severity','')}, "
            f"event_time {r.get('event_time','')}.")


def _fmt_exports_via(r: dict) -> str:
    return (f"{_cname(r['src_entity_id'])} (Supplier) EXPORTS_VIA {_cname(r['dst_entity_id'])} "
            f"(Corridor) at volume_mbpd {r['volume_mbpd']}.")


def _fmt_feeds(r: dict) -> str:
    return (f"{_cname(r['src_entity_id'])} (Corridor) FEEDS {_cname(r['dst_entity_id'])} (Port) "
            f"with throughput_share_pct {r['throughput_share_pct']}.")


def _fmt_supplies(r: dict) -> str:
    return (f"{_cname(r['src_entity_id'])} (Port) SUPPLIES {_cname(r['dst_entity_id'])} (Refinery) "
            f"with throughput_share_pct {r['throughput_share_pct']}.")


def _fmt_configured_for(r: dict) -> str:
    return (f"{_cname(r['src_entity_id'])} (Refinery) is CONFIGURED_FOR {_cname(r['dst_entity_id'])} "
            f"(CrudeGrade) with compatibility {r['compatibility']} and yield_pct {r['yield_pct']}.")


def _fmt_bypass(r: dict) -> str:
    return (f"{_cname(r['src_entity_id'])} (Supplier) has a BYPASS_ROUTE via {_cname(r['dst_entity_id'])} "
            f"(Port) with cost_premium {r['cost_premium']} and added_days {r['added_days']}.")


_NODE_FORMATTERS = {
    "Corridor":   _fmt_corridor,
    "Supplier":   _fmt_supplier,
    "Refinery":   _fmt_refinery,
    "CrudeGrade": _fmt_crude_grade,
    "Port":       _fmt_port,
    "SPRCavern":  _fmt_spr,
    "Authority":  _fmt_authority,
    "GeoEvent":   _fmt_geoevent,
}

_EDGE_FORMATTERS = {
    "EXPORTS_VIA":    _fmt_exports_via,
    "FEEDS":          _fmt_feeds,
    "SUPPLIES":       _fmt_supplies,
    "CONFIGURED_FOR": _fmt_configured_for,
    "BYPASS_ROUTE":   _fmt_bypass,
}


# ── loading + validation ──────────────────────────────────────────────────────

def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _strip_frontmatter(page: str) -> str:
    """Return the body of a wiki page, dropping a leading --- YAML frontmatter block."""
    if not page.startswith("---"):
        return page
    try:
        return page[page.index("---", 3) + 3:].strip()
    except ValueError:
        return page


def _parse_narrative(text: str) -> dict:
    """Split a narrative .md into {frontmatter: dict, body: str}."""
    fm: dict = {}
    body = text
    if text.startswith("---"):
        try:
            end = text.index("---", 3)
            fm = yaml.safe_load(text[3:end]) or {}
            body = text[end + 3:].strip()
        except ValueError:
            pass
    return {"frontmatter": fm, "body": body}


def load_bundle(bundle_path: str | Path) -> ContextBundle:
    """Parse a bundle directory into a ContextBundle. Validates on load."""
    path = Path(bundle_path)
    manifest_file = path / "manifest.yaml"
    if not manifest_file.exists():
        raise BundleValidationError(f"No manifest.yaml in bundle: {path}")

    manifest = yaml.safe_load(manifest_file.read_text())

    bundle = ContextBundle(path=path, manifest=manifest)
    for spec in manifest.get("nodes", []):
        bundle.node_rows[spec["type"]] = _read_csv(path / spec["file"])
    for spec in manifest.get("edges", []):
        bundle.edge_rows[spec["type"]] = _read_csv(path / spec["file"])

    # Narratives — auto-discovered from narratives_dir/*.md (filename = entity_id)
    narr_dir = path / manifest.get("narratives_dir", "narratives")
    if narr_dir.is_dir():
        for md in sorted(narr_dir.glob("*.md")):
            parsed = _parse_narrative(md.read_text(encoding="utf-8"))
            eid = parsed["frontmatter"].get("entity_id") or md.stem
            bundle.narratives[eid] = parsed

    validate_bundle(bundle)
    return bundle


def validate_bundle(bundle: ContextBundle) -> None:
    """
    Enforce the provenance contract: every row has a valid tier and a `source`
    that resolves to manifest.sources or manifest.estimation_methods.
    Raises BundleValidationError listing every offending row.
    """
    m = bundle.manifest
    known_sources = set(m.get("sources", {}).keys()) | set(m.get("estimation_methods", {}).keys())
    errors: list[str] = []

    def _check(group: str, rows: list[dict]) -> None:
        for i, r in enumerate(rows):
            tier = (r.get("tier") or "").strip()
            src = (r.get("source") or "").strip()
            if tier not in VALID_TIERS:
                errors.append(f"{group} row {i}: invalid tier '{tier}' (must be {VALID_TIERS})")
            if not src:
                errors.append(f"{group} row {i}: missing source — no unsourced data allowed")
            elif src not in known_sources:
                errors.append(f"{group} row {i}: source '{src}' not in manifest sources/estimation_methods")

    for ntype, rows in bundle.node_rows.items():
        _check(f"node:{ntype}", rows)
    for etype, rows in bundle.edge_rows.items():
        _check(f"edge:{etype}", rows)

    if errors:
        raise BundleValidationError(
            f"Bundle '{bundle.bundle_id}' failed validation ({len(errors)} issues):\n  "
            + "\n  ".join(errors)
        )
