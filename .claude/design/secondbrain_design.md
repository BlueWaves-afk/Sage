# SAGE — Second Brain Wiki Design Specification
## Obsidian-Style Wikilinks Over the Enforced Wiki Format

**Owner:** Knowledge Layer  
**Status:** Normative — extends `system1_interaction.md §5` (wiki format) and `system1_interaction.md §10` (entity resolution)  
**Companion specs:**
- [`system1_interaction.md`](./system1_interaction.md) — base wiki format + entity resolution
- [`SAGE_Schema_and_Contracts_Spec.md`](./SAGE_Schema_and_Contracts_Spec.md) — C2/C3 entity + edge ontology
- [`system2_designspec.md`](./system2_designspec.md) — downstream consumer of wiki links

---

## 1. Why Wikilinks Are Not Redundant With the Graphiti Graph

You already have a knowledge graph in Graphiti. The wikilink graph is a second, complementary graph — not a duplicate — because it captures something the Graphiti graph cannot.

| Property | Graphiti Graph | Wikilink Graph |
|---|---|---|
| **What it holds** | Typed, computable relationships (`EXPORTS_VIA`, `RISK_STATE`) with numeric attributes | Narrative, associative context — the "why" behind relationships |
| **Who reads it** | Machines: System 2 ARIO, monitor, procurement ranker | Humans: analysts, copilot, visualization renderer |
| **Edge types** | Formal, enumerated in C3 schema | Open-ended: historical analogies, causal prose, implicit associations |
| **Example** | `Hormuz --RISK_STATE {score:0.67}--> RiskAssessment` | `"pattern echoes the [[2019 Tanker Attacks]]"` |
| **Editable** | No — Graphiti manages its own writes | Yes — team members can manually edit wiki pages |
| **Visualization** | FalkorDB browser (`:3000`), geospatial overlay with edge types | Obsidian graph view (free, zero work), geospatial globe with wikilink edges |

The wikilink graph holds the interpretive layer that never becomes a formal typed edge. A historical precedent comparison (`[[2019 Tanker Attacks]]`), a qualitative exposure note (`crude bound for [[Jamnagar Refinery]] is most exposed`), a contradicting source reference (`[[AIS Anomaly — Larak Cluster]] is the leading indicator`) — these are the connective tissue of analyst reasoning that makes an assessment rich and navigable. Graphiti computes; the wiki explains.

**Having both is the architecture's strength, not its duplication.** Graphiti is the substrate for System 2–4 computation. The wikilink graph is the substrate for System 5 copilot citation, the human-readable intelligence layer, and the demo's Obsidian-style visualization.

---

## 2. The Enforced Second Brain Wiki Format

This extends the base format from `system1_interaction.md §5`. The additions are: `links_out` in frontmatter, `[[wikilinks]]` throughout prose sections, and a **Relations** section as machine-readable link metadata.

```markdown
---
entity_id: corridor_hormuz
entity_type: Corridor
risk_score: 0.67
risk_band: ELEVATED
factors:
  ais: 0.31
  gdelt: 0.19
  price: 0.12
  sanctions: 0.05
last_updated: 2026-02-23T14:42:00Z
valid_at: 2026-02-23T14:00:00Z
source_episodes:
  - ep_8841
  - ep_8843
  - ep_8847
coordinates:
  lat: 26.5
  lon: 56.4
links_out:
  - refinery_jamnagar
  - port_vadinar
  - supplier_nioc
  - event_2019_tanker_attacks
  - event_ais_larak_cluster
---

# Strait of Hormuz

## Current Assessment

Surface traffic is reported normal per Reuters, but AIS dark-vessel gaps near
Larak Island and a rising war-risk premium indicate elevated risk. Crude bound
for [[Jamnagar Refinery]] and [[Vadinar Port]] carries the highest exposure.
The vessel-shadowing pattern is consistent with the [[2019 Tanker Attacks]]
precursor signature.

## Contradiction Note

Reuters' "normal throughput" reflects lagging official vessel-reporting data.
The [[AIS Anomaly — Larak Cluster]] is the leading indicator here: shadow-fleet
vessels suppress AIS reporting, so the two sources measure different populations.

## Historical Pattern

81% feature-vector overlap with the [[2019 Tanker Attacks]] precursor window
(vessel pre-positioning, GDELT tone drop, war-risk premium rise in the same
3-day sequence). That event produced a 14-day partial closure.

## Affected Entities

- [[Jamnagar Refinery]] — HIGH exposure; 42% of crude arrives via Hormuz; 14-day inventory buffer
- [[Vadinar Port]] — primary discharge terminal for Gulf crude; congestion will spike on rerouting
- [[NIOC]] — operator of three pre-positioned vessels; owns [[MT Destiny]] and two shadow-fleet tankers

## Signal Basis

- [[AIS Anomaly — Larak Cluster]] — 4 dark-vessel gaps, H3 cells 8a2a1072b59ffff, 14:30 UTC [ep_8841]
- [[GDELT — Persian Gulf Tone Drop]] — Reuters event, tone -4.2, severity 0.72 [ep_8843]
- Brent BOCD breakpoint — war-risk premium 0.41%, regime STRESSED [ep_8847]

## Relations

| Relation | Entity | Type | Strength |
|---|---|---|---|
| feeds crude to | [[Jamnagar Refinery]] | supply_dependency | high |
| feeds crude to | [[Vadinar Port]] | supply_dependency | high |
| pre-positioned by | [[NIOC]] | threat_actor | medium |
| historical_precedent | [[2019 Tanker Attacks]] | analogy | high |
| detected_by | [[AIS Anomaly — Larak Cluster]] | signal_source | high |
```

---

## 3. Format Rules — What the Synthesis Prompt Must Enforce

### 3.1 Wikilink rules

1. **Every tracked-entity mention in prose is a wikilink.** If a tracked entity (registry entity_id) appears by name in any body section, it is written as `[[Canonical Name]]`. No bare entity names.
2. **Wikilinks use the canonical display name as link text.** `[[Jamnagar Refinery]]` not `[[Jamnagar]]`, `[[NIOC]]` not `[[National Iranian Oil Company]]`. The display text is the `canonical_name` from the registry.
3. **Events and signal episodes can be wikilinked.** Historical precedent events and named signal clusters get their own pages and are linked as `[[2019 Tanker Attacks]]`, `[[AIS Anomaly — Larak Cluster]]`. These are GeoEvent entity pages.
4. **`links_out` mirrors every wikilink.** Every entity_id that appears in `[[...]]` in the prose must also appear in `links_out`. The synthesis post-processor enforces this automatically (§6).
5. **No dangling links.** A wikilink to a non-existent registry entity is either normalized to the canonical name (if a near-match exists) or removed. No `[[Unknown Entity]]` in clean pages.
6. **Minimum 2 wikilinks per page.** A page with no outgoing links is a sign that synthesis failed to find the relevant entities. Treat it as a synthesis failure and retry.

### 3.2 Section rules (unchanged from base format, restated for completeness)

| Section | When present | Wikilinks required? |
|---|---|---|
| `## Current Assessment` | Always — 2-3 sentences | Yes — entity names in assessment are linked |
| `## Contradiction Note` | When sources disagree | Yes — link both sources |
| `## Historical Pattern` | When precedent exists | Yes — link the historical event page |
| `## Affected Entities` | Always for elevated+ | Yes — bulleted, every entity is a link |
| `## Signal Basis` | Always | Yes — signal cluster pages if they exist |
| `## Relations` | Always | N/A — this IS the structured link table |

### 3.3 Relations section rules

The Relations table is the machine-readable mirror of the narrative links. Relation types are drawn from a controlled vocabulary:

| Relation type | Meaning |
|---|---|
| `supply_dependency` | This entity depends on the linked entity for crude supply |
| `threat_actor` | The linked entity poses a threat to this corridor/supplier |
| `historical_precedent` | The linked event is a historical analogy for the current situation |
| `bypass_option` | The linked corridor/port is an alternative routing option |
| `signal_source` | The linked event/episode is the signal that drove this assessment |
| `sanctions_link` | The linked authority sanctioned an actor connected to this entity |
| `owned_by` | The linked entity owns or operates vessels/assets at this entity |

Strength is `high` / `medium` / `low` — the synthesis LLM assesses this.

---

## 4. Synthesis Prompt — Updated to Enforce Wikilinks

The synthesis prompt in `knowledge/synthesis.py:SYNTH_PROMPT` must be updated. The critical additions are the wikilink instruction and the Relations section template.

```python
SYNTH_PROMPT = """\
You maintain the intelligence page for {entity} (entity_id: {entity_id}).
A new signal has arrived. You must produce an updated wiki page in the EXACT
schema below — including frontmatter, wikilinks, and the Relations table.

CANONICAL ENTITY REGISTRY (use these names for wikilinks — no other variants):
{registry_excerpt}

CURRENT PAGE:
{current_page}

NEW SIGNAL:
Source: {source} | Priority: {priority} | Observed: {observed_at}
{signal_summary}

Produce the updated page in EXACTLY this format. Do not add extra sections.
Do not change the frontmatter field names. Do not skip the Relations table.

---
entity_id: {entity_id}
entity_type: {entity_type}
risk_score: {risk_score}
risk_band: {risk_band}
factors:
  ais: {factor_ais}
  gdelt: {factor_gdelt}
  price: {factor_price}
  sanctions: {factor_sanctions}
last_updated: {last_updated}
valid_at: {valid_at}
source_episodes: {source_episodes}
coordinates: {coordinates}
links_out: [FILL THIS with entity_ids of every [[wikilink]] you write below]
---

# {canonical_name}

## Current Assessment
[2-3 sentences. EVERY mention of a tracked entity is a [[Canonical Name]] wikilink.
The assessed risk level is {risk_score} out of 1.0 ({risk_band} band), with AIS
contributing {factor_ais}, GDELT {factor_gdelt}, price {factor_price}, sanctions
{factor_sanctions}. Do NOT use "Current risk score:" or "Factor breakdown:" labels.]

## Contradiction Note
[Only if sources disagree. Explain WHY. Link both disagreeing sources as [[...]].
Omit this section entirely if sources are consistent.]

## Historical Pattern
[If a precedent exists, write it with a [[historical event]] wikilink and state
feature-overlap percentage. Omit if no clear precedent.]

## Affected Entities
[Bulleted. Every entity is a [[Canonical Name]] link. State exposure level and reason.]

## Signal Basis
[One line per signal. Name signal clusters as [[Signal Cluster Name]] if they have pages.]

## Relations
| Relation | Entity | Type | Strength |
|---|---|---|---|
[One row per [[wikilink]] above. Use controlled vocabulary for Type. No extra rows.]

RULES:
1. Every tracked entity mentioned in prose appears as [[Canonical Name]] — no exceptions.
2. links_out contains the entity_id of EVERY entity linked in prose — not the display name.
3. The Relations table has exactly one row per unique linked entity.
4. Do NOT write prose risk labels like "Current risk score:" — write in sentences only.
5. Do NOT invent wikilinks to non-registry entities. If unsure, write the name in plain text.
6. Minimum 2 wikilinks in the page. If the signal doesn't mention 2 tracked entities, note
   at least the most affected downstream entity based on the current page context.\
"""
```

### 4.1 Registry excerpt injected into prompt

The prompt receives a `registry_excerpt` — a compact list of all canonical entity names so the LLM knows exactly which names to use as wikilink text:

```python
def _build_registry_excerpt() -> str:
    from knowledge.registry import REGISTRY
    lines = ["entity_id → canonical_name (type):"]
    for eid, entry in REGISTRY.items():
        lines.append(f"  {eid} → [[{entry.canonical_name}]] ({entry.entity_type})")
    return "\n".join(lines)
```

This is passed as `registry_excerpt` in the prompt format call. Keeps the LLM anchored to exact canonical names.

---

## 5. Post-Processing — Wikilink Normalizer

The synthesis LLM will occasionally write `[[Jamnagar]]` instead of `[[Jamnagar Refinery]]`, or link an alias instead of the canonical name. The normalizer runs on every synthesis output before the page is accepted:

```python
# knowledge/wikilink_processor.py
import re
import yaml
from knowledge.registry import REGISTRY, ALIAS_TO_ENTITY, canonical_name as get_canonical

_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def normalize_wikilinks(page_content: str) -> str:
    """
    1. Find all [[...]] in the page body.
    2. Resolve each link text against the registry (alias lookup + canonical check).
    3. Replace [[alias]] with [[Canonical Name]].
    4. Rebuild links_out in frontmatter from the resolved set.
    5. Remove dangling links (no registry match) — replace with plain text.
    Returns the cleaned page content.
    """
    if not page_content.startswith("---"):
        return page_content   # no frontmatter — can't normalize safely

    end = page_content.index("---", 3)
    fm_text = page_content[3:end]
    body    = page_content[end + 3:]
    fm      = yaml.safe_load(fm_text) or {}

    resolved_ids: list[str] = []

    def _replace(match: re.Match) -> str:
        link_text = match.group(1).strip()
        # Try exact alias lookup
        entity_id = ALIAS_TO_ENTITY.get(link_text.lower())
        if entity_id:
            resolved_ids.append(entity_id)
            return f"[[{get_canonical(entity_id)}]]"
        # Not in registry — remove wikilink, keep plain text
        return link_text

    normalized_body = _WIKILINK_RE.sub(_replace, body)

    # Deduplicate and sort links_out
    seen: list[str] = []
    for eid in resolved_ids:
        if eid not in seen:
            seen.append(eid)
    fm["links_out"] = seen

    new_fm = yaml.dump(fm, default_flow_style=False, allow_unicode=True)
    return f"---\n{new_fm}---\n{normalized_body}"


def validate_page(page_content: str) -> list[str]:
    """
    Returns a list of validation errors. Empty list = page is valid and accepted.
    """
    errors: list[str] = []

    if not page_content.startswith("---"):
        errors.append("Missing frontmatter")
        return errors

    try:
        end = page_content.index("---", 3)
        fm  = yaml.safe_load(page_content[3:end]) or {}
    except Exception as exc:
        errors.append(f"Malformed frontmatter YAML: {exc}")
        return errors

    for required in ("entity_id", "entity_type", "risk_score", "risk_band",
                     "factors", "last_updated", "valid_at", "links_out"):
        if required not in fm:
            errors.append(f"Missing required frontmatter field: {required}")

    if "factors" in fm:
        for factor in ("ais", "gdelt", "price", "sanctions"):
            if factor not in fm.get("factors", {}):
                errors.append(f"Missing factor: {factor}")

    links = fm.get("links_out", [])
    if len(links) < 2:
        errors.append(f"Minimum 2 wikilinks required; found {len(links)}")

    body = page_content[page_content.index("---", 3) + 3:]
    wikilinks_in_prose = _WIKILINK_RE.findall(body)
    if not wikilinks_in_prose:
        errors.append("No [[wikilinks]] found in page body")

    return errors


def parse_links_out(page_content: str) -> list[str]:
    """
    Extract links_out from page frontmatter. Used by visualization renderer
    and copilot to build the wikilink edge list without regexing prose.
    """
    if not page_content.startswith("---"):
        return []
    try:
        end = page_content.index("---", 3)
        fm  = yaml.safe_load(page_content[3:end]) or {}
        return fm.get("links_out", [])
    except Exception:
        return []
```

---

## 6. Updated `render_wiki_page()` — Wikilinks + `links_out`

The current `render_wiki_page()` in `knowledge/synthesis.py` must pass through the normalizer and validator before returning. The caller (`ingest_signal()`) receives the validated content.

```python
# knowledge/synthesis.py (updated render_wiki_page)
from knowledge.wikilink_processor import normalize_wikilinks, validate_page
import logging

log = logging.getLogger(__name__)


def render_wiki_page(
    entity: str,
    synthesized_text: str,                # raw LLM output (may have alias wikilinks)
    entity_id: str | None = None,         # from registry
    entity_type: str = "Unknown",
    risk_score: float = 0.0,
    risk_band: str = "calm",
    factors: dict | None = None,
    valid_at: str | None = None,
    source_episodes: list[str] | None = None,
    coordinates: dict | None = None,
) -> str:
    """
    Render a validated, normalized wiki page.
    - Normalizes [[alias]] → [[Canonical Name]] via registry
    - Rebuilds links_out from resolved wikilinks
    - Validates required fields; falls back to previous page on failure
    """
    import yaml
    from datetime import datetime, timezone

    stamp   = datetime.now(timezone.utc).isoformat()
    slug    = entity.lower().replace(" ", "_").replace("/", "-")
    eid     = entity_id or f"{entity_type.lower()}_{slug}"

    # If the LLM already returned a full page with frontmatter, normalize it
    if synthesized_text.strip().startswith("---"):
        raw = synthesized_text
    else:
        # LLM returned only prose — wrap it in the schema
        fm = {
            "entity_id":       eid,
            "entity_type":     entity_type,
            "risk_score":      round(risk_score, 4),
            "risk_band":       risk_band.upper(),
            "factors":         factors or {"ais": 0.0, "gdelt": 0.0, "price": 0.0, "sanctions": 0.0},
            "last_updated":    stamp,
            "valid_at":        valid_at or stamp,
            "source_episodes": source_episodes or [],
            "links_out":       [],
            "coordinates":     coordinates or {},
        }
        frontmatter = yaml.dump(fm, default_flow_style=False, allow_unicode=True)
        raw = f"---\n{frontmatter}---\n\n# {entity}\n\n{synthesized_text}"

    # Normalize wikilinks and rebuild links_out
    normalized = normalize_wikilinks(raw)

    # Validate
    errors = validate_page(normalized)
    if errors:
        log.warning("Wiki page for '%s' failed validation: %s", entity, errors)
        # Return the normalized content anyway — caller decides whether to persist
        # (ingest_signal gates persistence on no validation errors)

    return normalized
```

---

## 7. Updated `ingest_signal()` — Validation Gate

`ingest_signal()` in `knowledge/api/write.py` must refuse to write a wiki page that fails validation. This prevents malformed pages from drifting into the wiki store:

```python
# In knowledge/api/write.py → ingest_signal(), synthesize branch
for entity, text in entity_texts:
    from knowledge.wikilink_processor import validate_page
    page_content = render_wiki_page(entity, text, ...)
    errors = validate_page(page_content)
    if errors:
        log.warning("Wiki page rejected for '%s': %s — keeping previous page", entity, errors)
        # Don't write the page; the graph episode is already committed.
        # The old wiki page is stale but consistent.
    else:
        write_wiki_page(entity, page_content)
```

---

## 8. Visualization — Two Rendering Paths From the Same Data

The `links_out` frontmatter field and the `[[wikilinks]]` in prose drive both visualization paths. No extra data structures needed.

### 8.1 Path A — Obsidian native (development + backup demo)

Point Obsidian at the `/wiki` volume:

```bash
# On the dev machine or EC2 during development
# Mount /app/wiki as a local folder and open with Obsidian
# File → Open Vault → select /app/wiki
```

Obsidian parses `[[Canonical Name]]` links natively. The graph view shows every entity page as a node, every `[[...]]` as an edge, sized and colored by how many inbound links each page has. Pages with high in-degree (many entities linking to them) are naturally the structurally important nodes — Hormuz will be the most-linked page. This view is immediately available without any build work.

**Use this view to catch routing errors during development:** an entity page with zero outgoing links means synthesis failed to find related entities. An entity with zero incoming links may be an orphaned or misspelled page.

### 8.2 Path B — Geospatial renderer (product demo)

The frontend (`system5`) parses `links_out` from all wiki pages and draws edges between entity nodes at their geographic coordinates:

```typescript
// system5/src/wiki_graph.ts
interface WikiNode {
  entity_id: string;
  canonical_name: string;
  entity_type: string;
  lat: number;
  lon: number;
  risk_score: number;
  risk_band: string;
}

interface WikiEdge {
  source_id: string;
  target_id: string;
}

async function buildWikiGraph(): Promise<{ nodes: WikiNode[]; edges: WikiEdge[] }> {
  const pages = await fetchAllWikiPages();   // GET /api/wiki
  const nodes: WikiNode[] = [];
  const edges: WikiEdge[] = [];

  for (const page of pages) {
    const fm = parseFrontmatter(page.content);
    if (!fm.coordinates?.lat) continue;      // skip non-geographic entities

    nodes.push({
      entity_id:     fm.entity_id,
      canonical_name: page.entity,
      entity_type:   fm.entity_type,
      lat:           fm.coordinates.lat,
      lon:           fm.coordinates.lon,
      risk_score:    fm.risk_score,
      risk_band:     fm.risk_band,
    });

    for (const target_id of (fm.links_out || [])) {
      edges.push({ source_id: fm.entity_id, target_id });
    }
  }

  return { nodes, edges };
}
```

This feeds the deck.gl `ArcLayer` (edges) and `ScatterplotLayer` (nodes) to render the geographic wikilink graph. The same dataset drives:
- **Nodes:** coloured by `risk_band` (green → cyan → amber → red → pulsing red)
- **Arc edges:** coloured by relation type (parsed from the Relations table) or uniform by risk
- **Node click:** loads the full wiki page prose via `get_wiki_page()` for the sidebar
- **Link click:** navigates to the linked entity's page

### 8.3 API endpoint for the renderer

The FastAPI gateway exposes:

```python
# api_gateway/routes/wiki.py
@router.get("/wiki")
async def list_wiki_pages() -> list[WikiPageSummary]:
    """Return all entity pages with frontmatter parsed — for graph renderer."""
    from knowledge.synthesis import WIKI_DIR, list_wiki_entities
    from knowledge.wikilink_processor import parse_links_out
    results = []
    for slug in list_wiki_entities():
        path = WIKI_DIR / f"{slug}.md"
        content = path.read_text()
        fm = _parse_frontmatter(content)
        results.append(WikiPageSummary(
            entity_id=fm.get("entity_id", slug),
            entity=fm.get("entity_id", slug).replace("_", " ").title(),
            risk_score=fm.get("risk_score", 0.0),
            risk_band=fm.get("risk_band", "calm"),
            entity_type=fm.get("entity_type", "Unknown"),
            coordinates=fm.get("coordinates", {}),
            links_out=fm.get("links_out", []),
        ))
    return results

@router.get("/wiki/{entity_id}")
async def get_wiki_page_by_id(entity_id: str) -> WikiPage:
    """Return full markdown content for sidebar display."""
    from knowledge.api.read import get_wiki_page
    return await get_wiki_page(entity_id.replace("_", " ").title())
```

---

## 9. GeoEvent and Signal Cluster Pages

Signal clusters and historical events get their own wiki pages so they can be linked with `[[...]]`. These are created by SAGE synthesis when a named event or anomaly cluster is significant enough to warrant its own page.

### 9.1 GeoEvent page format

```markdown
---
entity_id: event_ais_larak_cluster
entity_type: GeoEvent
risk_score: 0.0
risk_band: CALM
factors:
  ais: 0.0
  gdelt: 0.0
  price: 0.0
  sanctions: 0.0
last_updated: 2026-02-23T14:30:00Z
valid_at: 2026-02-23T14:30:00Z
source_episodes:
  - ep_8841
coordinates:
  lat: 26.1
  lon: 57.2
links_out:
  - corridor_hormuz
  - supplier_nioc
---

# AIS Anomaly — Larak Cluster

## Current Assessment

Four vessels with NIOC-linked signatures exhibited AIS dark gaps near Larak
Island between 08:00 and 14:30 UTC on 23 February 2026. The gaps are clustered
in H3 cells adjacent to the primary [[Strait of Hormuz]] transit lane.
Three vessels are operated by [[NIOC]]-linked shell companies.

## Signal Basis

- AIS stream, 4 gap events, H3 cells 8a2a1072b59ffff + 8a2a1072b4fffff [ep_8841]

## Relations

| Relation | Entity | Type | Strength |
|---|---|---|---|
| detected_in | [[Strait of Hormuz]] | signal_source | high |
| operated_by | [[NIOC]] | threat_actor | medium |
```

### 9.2 Historical precedent page format

```markdown
---
entity_id: event_2019_tanker_attacks
entity_type: GeoEvent
risk_score: 0.0
risk_band: CALM
...
links_out:
  - corridor_hormuz
  - supplier_aramco
---

# 2019 Tanker Attacks

## Current Assessment

In May–June 2019, four crude tankers were sabotaged in the Gulf of Oman near
the [[Strait of Hormuz]]. The attacks were attributed to IRGC naval forces.
[[Saudi Aramco]] vessels were among the targeted ships.

...
```

**When to create a GeoEvent page:** whenever a signal cluster is significant enough to be cited by more than one entity page, or when a historical event is referenced in synthesis. The synthesis LLM is instructed: *"If you reference a named event or signal cluster with `[[...]]`, and no page for it exists yet, produce a stub GeoEvent page after the main entity page — one paragraph Current Assessment only."*

---

## 10. Build Order

| Step | Deliverable | Done when |
|---|---|---|
| 1 | `knowledge/registry.py` built | All 20 seed entities present; H3_TO_ENTITY, ALIAS_TO_ENTITY, INSTRUMENT_TO_ENTITIES populated |
| 2 | `knowledge/wikilink_processor.py` built | `normalize_wikilinks()` and `validate_page()` pass unit tests |
| 3 | `SYNTH_PROMPT` updated with wikilink instruction + registry excerpt | Synthesis output contains at least 2 `[[...]]` per page |
| 4 | `render_wiki_page()` updated | Output has frontmatter + normalized links_out |
| 5 | Validation gate in `ingest_signal()` | Malformed pages rejected without crashing the ingest loop |
| 6 | `/wiki` endpoint in FastAPI | `GET /wiki` returns all pages with parsed frontmatter |
| 7 | Obsidian vault check | Open `/wiki` in Obsidian; graph view shows connected entities; no orphaned nodes |
| 8 | Frontend `buildWikiGraph()` | Nodes rendered at coordinates; arc edges drawn between linked entities |
| 9 | GeoEvent page creation | Signal cluster pages exist; historical event pages seeded manually |
| 10 | Demo dry-run | Hormuz risk rise produces updated wiki page with correct links; Obsidian + geospatial view both show new edges |

---

## 11. Key Invariants — What Must Always Be True

These are checked by `validate_page()` and by the smoke test:

1. **Every `links_out` entry is a valid registry entity_id.** No free-form strings.
2. **Every `[[...]]` in prose has a corresponding entry in `links_out`.** Normalizer enforces this.
3. **Every `links_out` entity has a wiki page** (or is queued for stub creation). No dangling edges in the visualization.
4. **Minimum 2 outgoing links per page.** A page with 0–1 links failed synthesis.
5. **`links_out` does not contain `entity_id` of the page itself.** Self-links are meaningless and break graph layout.
6. **Risk score in frontmatter matches the most recent `write_risk_state()` call.** The frontmatter update rule (§6.3 of `system1_interaction.md`) enforces this.
7. **`last_updated` timestamp is always later than `valid_at`.** `valid_at` is when the signal was true in the world; `last_updated` is when we wrote the page.

---

## 12. Wikilink Rendering Verification Checklist

Before demo:

- [ ] Open `/wiki` in Obsidian — graph view shows ≥ 10 nodes, ≥ 20 edges
- [ ] Hormuz node has the highest in-degree (most linked-to)
- [ ] No orphaned nodes (every node has at least 1 incoming link)
- [ ] `GET /api/wiki` returns all pages with `links_out` populated
- [ ] Geospatial renderer draws arc edges between entity nodes at correct coordinates
- [ ] Node click opens wiki sidebar with full prose including `[[...]]` rendered as hyperlinks
- [ ] Risk band colour matches `risk_band` frontmatter field on every node
- [ ] `validate_page()` returns empty error list for every page in `/wiki`
- [ ] Historical event pages (`event_2019_tanker_attacks`) exist and are linked from Hormuz
- [ ] Signal cluster pages (`event_ais_larak_cluster`) created on first AIS anomaly ingest
