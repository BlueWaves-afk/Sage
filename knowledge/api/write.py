"""
C7 — Write API. The only entry points for writing to the knowledge base.

IMPORT BOUNDARY: agents import from here only. None of them import graphiti_core directly.

Write path (single-path rule):
  ingest_signal() is the only function that calls add_episode().
  All other writes (write_scenario, write_procurement, write_spr_schedule,
  write_pending, write_risk_state) build an episode body and call ingest_signal()
  with force_synthesis=True — so everything flows through one code path.

  Exception: write_risk_state() calls add_episode() directly (after ingest_signal
  has already processed the signal). This avoids a synthesis recursion but still
  uses the shared ENTITY_TYPES / EDGE_TYPES contracts.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel

from contracts.bands import score_to_band
from contracts.outputs import ProcurementRecData, ScenarioOutputData, SPRScheduleData
from contracts.signal import NormalizedSignal, Priority, SignalSource
from knowledge.schema.edges import EDGE_TYPE_MAP, EDGE_TYPES
from knowledge.schema.entities import ENTITY_TYPES
from knowledge.triage import TriageDecision, triage

import asyncio
import time

log = logging.getLogger(__name__)

# Limit concurrent FalkorDB writes — Graphiti's add_episode is ~8-12s and issues
# dozens of sub-queries; running >2 in parallel saturates the queue and causes
# timeouts that drop real ingest signals.
_FALKOR_WRITE_SEM = asyncio.Semaphore(2)

# Per-entity synthesis cooldown — prevents repeated Nova Pro wiki synthesis for
# the same entity within a short window. Continuous news ingestion can fire 20+
# signals/cycle for entities like "United States", each triggering a full synthesis
# call. Downgrade to "extract" if the entity was synthesized within this window.
_SYNTH_COOLDOWN_S: int = int(__import__("os").environ.get("SAGE_SYNTH_COOLDOWN_S", "1800"))
_last_synth: dict[str, float] = {}  # entity → monotonic time of last synthesis


# ---------------------------------------------------------------------------
# Return types
# ---------------------------------------------------------------------------

class EpisodeRef(BaseModel):
    episode_uuid: str
    scenario_id: Optional[str] = None


async def _add_episode(g, **kwargs) -> None:
    """Semaphore-gated wrapper so concurrent add_episode calls don't saturate FalkorDB."""
    async with _FALKOR_WRITE_SEM:
        await g.add_episode(**kwargs)


# ---------------------------------------------------------------------------
# Structured output cache (Redis)
# ---------------------------------------------------------------------------
# Graph episodes hold the non-lossy prose; for the API/frontend we also cache the
# exact structured model_dump() so /api/scenario, /api/procurement, /api/spr-schedule
# can return full-fidelity JSON without re-parsing episode text. Best-effort, never
# blocks the KB write — same discipline as the pub/sub publish.
_OUTPUT_TTL_S = 24 * 3600


async def _cache_output(kind: str, scenario_id: str, data: BaseModel) -> None:
    """Cache a structured output under sage:<kind>:<id> and sage:<kind>:latest."""
    import json
    import os
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"),
                                   decode_responses=True)
        try:
            payload = json.dumps(data.model_dump(), default=str)
            await client.set(f"sage:{kind}:{scenario_id}", payload, ex=_OUTPUT_TTL_S)
            await client.set(f"sage:{kind}:latest", payload, ex=_OUTPUT_TTL_S)
        finally:
            await client.aclose()
    except Exception as exc:
        log.warning("Output cache failed for %s:%s (non-fatal): %s", kind, scenario_id, exc)


async def _demo_running() -> bool:
    """True while a demo replay is active (Redis flag set by demo_ignite).

    Pipeline output writers (scenario/procurement/SPR) use this to skip the heavy
    graphiti add_episode path — Nova entity extraction + Titan embed + a fulltext
    dedup search that TIMES OUT on the loaded graph. During a demo we still write
    the Redis output cache (what /api/scenario|procurement|spr read), so every
    panel populates instantly; only the durable graph episode is deferred.
    """
    import os
    try:
        import redis.asyncio as aioredis
        from knowledge.demo_control import DEMO_FLAG_KEY
        client = aioredis.from_url(
            os.environ.get("REDIS_URL", "redis://redis:6379/0"), decode_responses=True
        )
        try:
            return (await client.get(DEMO_FLAG_KEY)) == "1"
        finally:
            await client.aclose()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Scenario Library (Feature A) — durable index + meta card, separate from the
# 24h full-payload cache above so the library survives payload expiry.
# ---------------------------------------------------------------------------

_META_TTL_S = 30 * 24 * 3600   # 30 days


async def write_scenario_index(scenario_id: str, meta: dict) -> None:
    """
    Record a scenario run in the durable library index. Best-effort, never
    blocks the caller — same discipline as `_cache_output`.

    meta keys: trigger_entity, origin (auto|user|preset), label, gap_mbpd,
    price_impact_high, gdp_proxy_impact_pct, spr_depletion_days, created_at.
    """
    import os
    import time
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"),
                                   decode_responses=True)
        try:
            await client.zadd("sage:scenario:index", {scenario_id: time.time()})
            # Redis hashes need string values.
            safe_meta = {k: ("" if v is None else str(v)) for k, v in meta.items()}
            key = f"sage:scenario:meta:{scenario_id}"
            await client.hset(key, mapping=safe_meta)
            await client.expire(key, _META_TTL_S)
        finally:
            await client.aclose()
    except Exception as exc:
        log.warning("write_scenario_index failed for %s (non-fatal): %s", scenario_id, exc)


async def write_custom_preset(slug: str, preset: dict) -> None:
    """Persist a user-promoted scenario as a named preset (curated, no TTL)."""
    import os
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"),
                                   decode_responses=True)
        try:
            safe = {k: ("" if v is None else str(v)) for k, v in preset.items()}
            await client.hset(f"sage:preset:custom:{slug}", mapping=safe)
            await client.sadd("sage:preset:custom:index", slug)
        finally:
            await client.aclose()
    except Exception as exc:
        log.warning("write_custom_preset failed for %s (non-fatal): %s", slug, exc)


async def delete_custom_preset(slug: str) -> bool:
    """Remove a user-promoted preset. Returns True if it existed."""
    import os
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"),
                                   decode_responses=True)
        try:
            existed = bool(await client.exists(f"sage:preset:custom:{slug}"))
            await client.delete(f"sage:preset:custom:{slug}")
            await client.srem("sage:preset:custom:index", slug)
            return existed
        finally:
            await client.aclose()
    except Exception as exc:
        log.warning("delete_custom_preset failed for %s (non-fatal): %s", slug, exc)
        return False


# ---------------------------------------------------------------------------
# Scenario calibration store (Feature B) — bounded, per-corridor, visible
# correction factors applied on top of raw ARIO output.
# ---------------------------------------------------------------------------

async def write_calibration_factor(entity: str, gap_x: float, price_x: float, n: int) -> None:
    """Persist a learned per-corridor correction factor (bounded 0.5-1.5)."""
    import os
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"),
                                   decode_responses=True)
        try:
            gap_x = max(0.5, min(1.5, gap_x))
            price_x = max(0.5, min(1.5, price_x))
            await client.hset(f"sage:calib:params:{entity}", mapping={
                "gap_x": str(gap_x), "price_x": str(price_x), "n": str(n),
            })
            await client.sadd("sage:calib:index", entity)
        finally:
            await client.aclose()
    except Exception as exc:
        log.warning("write_calibration_factor failed for %s (non-fatal): %s", entity, exc)


async def get_calibration_factor(entity: str) -> tuple[float, float]:
    """Read the learned (gap_x, price_x) for a corridor; (1.0, 1.0) if unlearned."""
    import os
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"),
                                   decode_responses=True)
        try:
            h = await client.hgetall(f"sage:calib:params:{entity}")
            if not h:
                return (1.0, 1.0)
            return (float(h.get("gap_x", 1.0)), float(h.get("price_x", 1.0)))
        finally:
            await client.aclose()
    except Exception:
        return (1.0, 1.0)


class IngestResult(BaseModel):
    signal_id: str
    decision: Literal["synthesized", "extracted", "stored", "dropped"]
    episode_uuid: Optional[str] = None
    risk_updated: bool = False


# ---------------------------------------------------------------------------
# Raw-signal provenance block (appended to every synthesized episode)
# ---------------------------------------------------------------------------

def _render_raw_signal(signal: NormalizedSignal) -> str:
    """Render the verbatim raw signal as a provenance block.

    Appended to the synthesized episode body so Store 1 (episodes) holds the
    non-lossy ground truth — the exact signal that produced the assessment —
    alongside the derived prose. Every derived fact can be traced back here.
    """
    import json

    payload = json.dumps(signal.payload, default=str, sort_keys=True) if signal.payload else "{}"
    lines = [
        "--- RAW SIGNAL (provenance, non-lossy) ---",
        f"signal_id: {signal.signal_id}",
        f"source: {signal.source} | priority: {signal.priority_hint} | "
        f"observed_at: {signal.observed_at.isoformat()}",
        f"entity_refs: {', '.join(signal.entity_refs)}",
        f"summary: {signal.summary}",
        f"payload: {payload[:2000]}",
    ]
    if signal.source_url:
        lines.append(f"source_url: {signal.source_url}")
    if signal.raw_ref:
        lines.append(f"raw_ref: {signal.raw_ref}")
    return "\n".join(lines)


async def _force_india_brief() -> None:
    """Force-refresh the India situation brief after a Systems 2/3/4 output lands."""
    try:
        from knowledge.context.india_brief import refresh_india_brief
        await refresh_india_brief(force=True)
    except Exception as exc:
        log.debug("[india_brief] force refresh non-fatal: %s", exc)


async def _stamp_episode_url(g, episode_name: str, url: str) -> None:
    """Stamp source_url on an Episodic node after add_episode() commits."""
    try:
        await g.driver.execute_query(
            "MATCH (e:Episodic {name:$name}) SET e.source_url = $url",
            name=episode_name, url=url,
        )
    except Exception as exc:
        log.warning("source_url stamp failed for episode %s: %s", episode_name, exc)


# ---------------------------------------------------------------------------
# C7.1 — Main ingest entry point
# ---------------------------------------------------------------------------

async def ingest_signal(signal: NormalizedSignal) -> IngestResult:
    """
    Main entry point for all raw signals from sensory_agent.

    Flow:
      1. Triage gate → decision in {synthesize, extract, store, drop}
      2. synthesize: call synthesis.synthesize() per entity_ref → episode text
      3. extract: build minimal episode text without wiki update
      4. store: write raw signal text as episode (no entity extraction)
      5. drop: discard (very low priority, no entity_refs)
      6. Call graphiti.add_episode() with full ontology types
      7. Return IngestResult

    Note: risk_score is NOT written here — call write_risk_state() separately
    after the fusion model aggregates all signals for an entity.
    """
    from graphiti_core.nodes import EpisodeType
    from knowledge.connection import _get_graphiti
    from knowledge.synthesis import synthesize

    g = _get_graphiti()
    decision, similarity = await triage(signal)

    episode_uuid: Optional[str] = None
    risk_updated = False

    if decision == "drop":
        return IngestResult(
            signal_id=signal.signal_id,
            decision="dropped",
        )

    if decision == "synthesize":
        from knowledge.synthesis import write_wiki_page
        from knowledge.wikilink_processor import validate_page as _validate_page

        # Full narrative synthesis per entity_ref. persist=False defers the wiki
        # write until the graph write succeeds, so the stores can't drift.
        # synthesize() now returns a complete page with frontmatter + wikilinks.
        entity_refs = signal.entity_refs or [signal.summary[:60]]
        entity_texts: list[tuple[str, str]] = []
        now_mono = time.monotonic()

        for entity in entity_refs:
            last = _last_synth.get(entity, 0.0)
            if now_mono - last < _SYNTH_COOLDOWN_S and not signal.force_synthesis:
                # Cooldown active — extract entity facts but skip expensive Nova Pro synthesis.
                log.debug("Synthesis cooldown active for '%s' (%.0fs remaining), downgrading to extract",
                          entity, _SYNTH_COOLDOWN_S - (now_mono - last))
                decision = "extract"
                continue
            text = await synthesize(signal=signal, entity=entity, persist=False)
            entity_texts.append((entity, text))
            _last_synth[entity] = now_mono

        # Episode body: strip frontmatter so Graphiti gets clean prose (not YAML).
        # Provenance block is appended so Store 1 holds the non-lossy ground truth.
        def _body_only(page: str) -> str:
            if not page.startswith("---"):
                return page
            try:
                return page[page.index("---", 3) + 3:].strip()
            except ValueError:
                return page

        # If all entity_refs were on cooldown, fall through to extract path.
        if not entity_texts:
            decision = "extract"
        else:
            synth_join   = "\n\n---\n\n".join(_body_only(text) for _, text in entity_texts)
            episode_body = f"{synth_join}\n\n{_render_raw_signal(signal)}"
            episode_name = f"{signal.source}_{signal.signal_id}"

        if entity_texts:
            # ── Consistency gate ──────────────────────────────────────────────
            # The graph write is the atomic boundary we control: the wiki is only
            # persisted AFTER add_episode succeeds. If add_episode raises, no wiki
            # page is written, so the /wiki store and the graph never diverge.
            try:
                await _add_episode(g,
                    name=episode_name,
                    episode_body=episode_body,
                    source=EpisodeType.text,
                    source_description=f"SAGE synthesis | source={signal.source}",
                    reference_time=signal.observed_at,
                    entity_types=ENTITY_TYPES,
                    edge_types=EDGE_TYPES,
                    edge_type_map=EDGE_TYPE_MAP,
                )
                # Graphiti doesn't return the episode UUID directly in add_episode();
                # we generate a stable one from signal_id for downstream reference
                episode_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, signal.signal_id))
                # Stamp source_url as a first-class property so the intelligence/evidence
                # feeds can render a clickable citation without parsing body text.
                if signal.source_url:
                    await _stamp_episode_url(g, episode_name, signal.source_url)
            except Exception as exc:
                log.error("add_episode failed for signal %s: %s", signal.signal_id, exc)
                raise

            # Graph write committed — validate and persist wiki pages.
            # Hard validation errors keep the old page; soft warnings pass through.
            for entity, text in entity_texts:
                errors = _validate_page(text)
                if errors:
                    log.warning(
                        "Wiki page for '%s' failed validation (keeping old page): %s",
                        entity, errors,
                    )
                else:
                    write_wiki_page(entity, text)

            return IngestResult(
                signal_id=signal.signal_id,
                decision="synthesized",
                episode_uuid=episode_uuid,
                risk_updated=risk_updated,
            )

    if decision == "extract":
        # Entity extraction only — no wiki update, cheaper episode
        episode_body = (
            f"[EXTRACT] {signal.source.upper()} signal | "
            f"{signal.observed_at.strftime('%Y-%m-%d %H:%M UTC')} | "
            f"entities: {', '.join(signal.entity_refs)} | "
            f"{signal.summary}"
        )
        extract_name = f"extract_{signal.signal_id}"
        try:
            await _add_episode(g,
                name=extract_name,
                episode_body=episode_body,
                source=EpisodeType.text,
                source_description=f"SAGE extract | source={signal.source}",
                reference_time=signal.observed_at,
                entity_types=ENTITY_TYPES,
                edge_types=EDGE_TYPES,
                edge_type_map=EDGE_TYPE_MAP,
            )
            episode_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, signal.signal_id))
            if signal.source_url:
                await _stamp_episode_url(g, extract_name, signal.source_url)
        except Exception as exc:
            log.error("add_episode (extract) failed for signal %s: %s", signal.signal_id, exc)
            raise

        return IngestResult(
            signal_id=signal.signal_id,
            decision="extracted",
            episode_uuid=episode_uuid,
        )

    # decision == "store" — raw storage, no Graphiti extraction
    # Still write to Graphiti as a plain text episode (for audit + retrieval)
    # but skip entity_types / edge_types so extraction doesn't run
    raw_name = f"raw_{signal.signal_id}"
    try:
        await _add_episode(g,
            name=raw_name,
            episode_body=f"[RAW] {signal.source} | {signal.observed_at.isoformat()} | {signal.summary}",
            source=EpisodeType.text,
            source_description=f"SAGE raw | source={signal.source}",
            reference_time=signal.observed_at,
        )
        episode_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, signal.signal_id))
        if signal.source_url:
            await _stamp_episode_url(g, raw_name, signal.source_url)
    except Exception as exc:
        log.warning("Raw store failed for signal %s (non-fatal): %s", signal.signal_id, exc)

    return IngestResult(
        signal_id=signal.signal_id,
        decision="stored",
        episode_uuid=episode_uuid,
    )


# ---------------------------------------------------------------------------
# C7.1 — Risk state write (called by sensory_agent after fusion aggregation)
# ---------------------------------------------------------------------------

async def _exec_cypher(g, query: str, params: dict) -> None:
    """Execute a write Cypher against FalkorDB via the Graphiti driver."""
    try:
        await g.driver.execute_query(query, **params)
    except Exception as exc:
        log.warning("RISK_STATE cypher failed: %s", exc)


async def _write_risk_edge(g, entity, score, band, f_ais, f_gdelt, f_price,
                           f_sanctions, rationale, model_version, now, uuid_str) -> None:
    """
    Write the RISK_STATE edge deterministically as a RELATES_TO self-edge —
    the exact shape get_risk_scores() reads. Bitemporal: invalidate the prior
    current edge, then create the new one with invalid_at absent (= NULL = current).
    """
    now_iso = now.isoformat()
    # 1. Invalidate the previous current RISK_STATE edge for this entity.
    await _exec_cypher(g,
        "MATCH (e:Entity {name:$n})-[old:RELATES_TO]->(e) "
        "WHERE old.name='RISK_STATE' AND old.invalid_at IS NULL "
        "SET old.invalid_at=$now",
        {"n": entity, "now": now_iso})
    # 2. Create the new current RISK_STATE self-edge.
    # group_id/fact/episodes are set (not left null) because Graphiti's internal
    # EntityEdge hydration — triggered during add_episode's dedup/search sweep —
    # requires every RELATES_TO edge to carry all five EntityEdge-required fields,
    # or the whole ingest crashes with a pydantic ValidationError.
    fact_text = rationale or f"{entity} risk assessed at {float(score):.2f} ({band})"
    await _exec_cypher(g,
        "MATCH (e:Entity {name:$n}) WITH e LIMIT 1 "
        "CREATE (e)-[r:RELATES_TO {name:'RISK_STATE', score:$score, band:$band, "
        "factor_ais:$ais, factor_gdelt:$gdelt, factor_price:$price, "
        "factor_sanctions:$sanctions, rationale:$rat, model_version:$mv, "
        "valid_at:$now, created_at:$now, uuid:$uuid, "
        "group_id:'', episodes:[], fact:$fact}]->(e)",
        {"n": entity, "score": float(score), "band": band,
         "ais": float(f_ais), "gdelt": float(f_gdelt), "price": float(f_price),
         "sanctions": float(f_sanctions), "rat": rationale or "",
         "mv": model_version or "", "now": now_iso, "uuid": uuid_str, "fact": fact_text})


async def write_risk_state(
    entity: str,
    score: float,
    factor_ais: float = 0.0,
    factor_gdelt: float = 0.0,
    factor_price: float = 0.0,
    factor_sanctions: float = 0.0,
    rationale: Optional[str] = None,
    model_version: Optional[str] = None,
    observed_at: Optional[datetime] = None,
) -> EpisodeRef:
    """
    Write a RISK_STATE assessment for an entity.

    Called by sensory_agent coordinator after the fusion model aggregates
    all 4 signal streams for a 30-second evaluation tick.

    ISOLATION RULE: This function is for LIVE entities only. Speculative risk
    from the sandbox must NEVER call this function — use write_pending() instead.

    The risk score is embedded in the episode body so Graphiti extracts a
    RISK_STATE edge from the prose (per C4 §6.4 of schema spec).
    """
    from graphiti_core.nodes import EpisodeType
    from knowledge.connection import _get_graphiti
    from knowledge.synthesis import write_wiki_page, load_wiki_page

    g   = _get_graphiti()
    now = observed_at or datetime.now(timezone.utc)
    band = score_to_band(score)

    # Prose-only format intentional: structured "Field: Value" labels cause Nova Lite
    # to hallucinate HAS_RISK_SCORE / HAS_FACTOR_BREAKDOWN edges not in the schema.
    # Same data expressed as sentences; RISK_STATE edge is still extracted correctly.
    episode_text = (
        f"{entity} risk level is assessed at {score:.2f} out of 1.0 ({band} band) "
        f"as of {now.strftime('%Y-%m-%d %H:%M')}Z. "
        f"Signal contributions: AIS dark-vessel {factor_ais:.2f}, "
        f"GDELT conflict tone {factor_gdelt:.2f}, "
        f"price war-risk premium {factor_price:.2f}, "
        f"sanctions exposure {factor_sanctions:.2f}. "
        f"{rationale or 'No specific rationale provided.'}. "
        f"Fusion model: {model_version or 'unknown'}.\n"
    )

    episode_name = f"{entity.lower().replace(' ', '_')}_risk_{now.strftime('%Y%m%dT%H%M%SZ')}"
    sig_id       = f"risk_{entity}_{now.isoformat()}"
    episode_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, sig_id))

    # ── Consistency gate ──────────────────────────────────────────────────
    # Graph write first; the wiki risk block is appended only after it commits,
    # so a failed add_episode can't leave the wiki ahead of the graph.
    #
    # During demo mode, skip add_episode (Nova Micro + Titan embed, ~56s) so the
    # consumer is not blocked on every risk-state flush. The deterministic
    # RISK_STATE edge below is all that matters for the demo risk score to climb.
    from knowledge.demo_control import DEMO_FLAG_KEY as _DEMO_FLAG_KEY
    import redis.asyncio as _aioredis, os as _os
    _demo_r = _aioredis.from_url(
        _os.environ.get("REDIS_URL", "redis://redis:6379/0"), decode_responses=True
    )
    try:
        _demo_active = (await _demo_r.get(_DEMO_FLAG_KEY)) == "1"
    finally:
        await _demo_r.aclose()

    if not _demo_active:
        await _add_episode(g,
            name=episode_name,
            episode_body=episode_text,
            source=EpisodeType.text,
            source_description="SAGE risk state",
            reference_time=now,
            entity_types=ENTITY_TYPES,
            edge_types=EDGE_TYPES,
            edge_type_map=EDGE_TYPE_MAP,
        )

    # Deterministic RISK_STATE edge — DO NOT rely on LLM extraction for this.
    # RISK_STATE is a self-property (score/band/factors) with exact numeric values;
    # the extractor will not reliably produce a self-loop edge from prose. We write
    # it directly as a RELATES_TO self-edge (the shape get_risk_scores() reads), and
    # bitemporally invalidate the previous current edge.
    await _write_risk_edge(
        g, entity, score, band, factor_ais, factor_gdelt, factor_price,
        factor_sanctions, rationale, model_version, now, episode_uuid,
    )

    # Graph committed — update only the risk frontmatter fields in place.
    # Body prose and [[wikilinks]] are preserved; no appended blocks accumulate.
    #
    # Skipped during demo replay: load_wiki_page + write_wiki_page are SYNCHRONOUS
    # disk I/O that runs on every risk write. On the memory-constrained demo host
    # this blocks the asyncio event loop long enough that the ingest consumer's
    # Redis calls time out, so it falls into its 5s retry sleep and stops draining
    # the queue — the risk climb stalls. The frontend reads risk from the graph
    # (RISK_STATE edge, already written above), not the wiki, so the demo climb is
    # fully visible without touching the wiki files.
    if not _demo_active:
        from knowledge.wikilink_processor import update_frontmatter_risk
        current = load_wiki_page(entity)
        updated = update_frontmatter_risk(
            content=current,
            score=score,
            band=band,
            factors={
                "ais":       factor_ais,
                "gdelt":     factor_gdelt,
                "price":     factor_price,
                "sanctions": factor_sanctions,
            },
            valid_at=now.isoformat(),
            last_updated=now.isoformat(),
        )
        write_wiki_page(entity, updated)

    return EpisodeRef(episode_uuid=episode_uuid)


# ---------------------------------------------------------------------------
# C7.1 — System 2: Scenario output
# ---------------------------------------------------------------------------

async def write_scenario(data: ScenarioOutputData) -> EpisodeRef:
    """
    scenario_agent calls this after ARIO + IO + ABM cascade completes.
    Creates a linked ScenarioOutput episode + AFFECTS_SCENARIO edge back to trigger entity,
    AND (for confirmed/speculative scenarios) reconciles the result into the trigger
    entity's wiki page (Store 3), so the narrative reflects the latest modelled impact —
    not just System 1 news. Counterfactual sandbox forks never touch the live wiki
    (isolation rule — same as write_pending).
    """
    from graphiti_core.nodes import EpisodeType
    from knowledge.connection import _get_graphiti

    g   = _get_graphiti()
    now = datetime.now(timezone.utc)

    timeline_summary = ", ".join(f"day{i+1}:{v:.1f}" for i, v in enumerate(data.feedstock_gap_timeline[:7]))
    assumptions_text = "; ".join(
        f"{k}={v.get('value', v)} ({v.get('unit','')}, src:{v.get('source','')})"
        if isinstance(v, dict) else f"{k}={v}"
        for k, v in list(data.assumptions.items())[:5]
    )

    episode_body = (
        f"Scenario output {data.scenario_id} for {data.trigger_entity} "
        f"[{data.status.upper()}] — confidence {data.confidence:.0%}.\n"
        f"Supply gap: {data.gap_mbpd:.2f} mbpd for {data.gap_duration_days:.0f} days.\n"
        f"Feedstock gap timeline (first 7 days): [{timeline_summary}].\n"
        f"Price impact: ${data.price_impact_low:.0f}–${data.price_impact_high:.0f}/bbl.\n"
        f"SPR cover remaining at projected draw: {data.spr_depletion_days:.1f} days.\n"
        f"Key ARIO assumptions: {assumptions_text}.\n"
        f"GDP proxy impact: {data.gdp_proxy_impact_pct:.2f}%.\n"
        if data.gdp_proxy_impact_pct else ""
        f"Scenario triggered by: {data.trigger_entity}. "
        f"This ScenarioOutput AFFECTS_SCENARIO {data.scenario_id}."
    )

    _demo_active = await _demo_running()
    if not _demo_active:
        await _add_episode(g,
            name=f"scenario_{data.scenario_id}",
            episode_body=episode_body,
            source=EpisodeType.text,
            source_description="SAGE scenario output | System 2",
            reference_time=now,
            entity_types=ENTITY_TYPES,
            edge_types=EDGE_TYPES,
            edge_type_map=EDGE_TYPE_MAP,
        )

    episode_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"scenario_{data.scenario_id}"))

    # ── Wiki reconciliation (Store 3) ───────────────────────────────────────
    # Graph episode committed above — now fold the scenario result into the
    # narrative, same consistency-gate pattern as ingest_signal/write_risk_state:
    # never write the wiki ahead of a graph write that might have failed.
    # Skipped for counterfactual sandbox forks (isolation rule) and during demo
    # replay (synthesize() is another Bedrock call that would stall the pipeline).
    if data.status != "counterfactual" and not _demo_active:
        try:
            await _reconcile_scenario_into_wiki(data, now)
        except Exception as exc:
            log.warning(
                "Wiki reconciliation failed for scenario %s (graph episode still committed): %s",
                data.scenario_id, exc,
            )

    await _cache_output("scenario", data.scenario_id, data)
    # India brief always refreshes when a new scenario lands (force=True — no cooldown).
    import asyncio
    asyncio.create_task(_force_india_brief())
    return EpisodeRef(episode_uuid=episode_uuid, scenario_id=data.scenario_id)


async def _reconcile_scenario_into_wiki(data: ScenarioOutputData, now: datetime) -> None:
    """
    Builds a synthetic NormalizedSignal describing the scenario result and runs it
    through the same synthesize() reconciliation System 1 uses for news — so a
    second scenario run that supersedes/contradicts an earlier one produces a
    visible "## Contradiction Note", not a silent overwrite. Existing risk-score
    frontmatter is preserved (read from the current page) since this is a
    structural-cascade update, not a fusion-model risk re-score.
    """
    from contracts.signal import NormalizedSignal
    from knowledge.synthesis import synthesize, write_wiki_page, load_wiki_page
    from knowledge.wikilink_processor import parse_frontmatter, validate_page

    timeline_summary = ", ".join(
        f"day{i+1}:{v:.1f}" for i, v in enumerate(data.feedstock_gap_timeline[:7])
    )
    top_assumptions = "; ".join(
        f"{k}={v.get('value', v)}{v.get('unit','')}"
        if isinstance(v, dict) else f"{k}={v}"
        for k, v in list(data.assumptions.items())[:4]
    )
    top_nodes = sorted(
        data.node_impacts, key=lambda n: n.get("peak_gap_mbpd", 0), reverse=True
    )[:3]
    nodes_text = "; ".join(
        f"{n.get('node')} peak gap {n.get('peak_gap_mbpd', 0):.2f} mbpd from day {n.get('onset_day', '?')}"
        for n in top_nodes
    )

    summary = (
        f"System 2 scenario modelling ({data.status}) for {data.trigger_entity}: "
        f"projected supply gap {data.gap_mbpd:.2f} mbpd over {data.gap_duration_days:.0f} days "
        f"(timeline: {timeline_summary}). "
        f"Projected price impact ${data.price_impact_low:.0f}-${data.price_impact_high:.0f}/bbl, "
        f"SPR cover would last {data.spr_depletion_days:.1f} days at the projected draw rate"
        + (f", GDP impact {data.gdp_proxy_impact_pct:.2f}%" if data.gdp_proxy_impact_pct else "")
        + (f", inflation impact {data.inflation_impact_pct:.2f}%" if data.inflation_impact_pct else "")
        + f". Most-exposed nodes: {nodes_text}." if nodes_text else "."
    ) + f" Key assumptions: {top_assumptions}. Model confidence {data.confidence:.0%}."

    signal = NormalizedSignal(
        signal_id=f"scenario_{data.scenario_id}",
        source="scenario",
        observed_at=now,
        ingested_at=now,
        priority_hint="HIGH" if data.status == "confirmed" else "MED",
        force_synthesis=True,
        entity_refs=[data.trigger_entity],
        summary=summary,
        payload={"scenario_id": data.scenario_id, "status": data.status},
    )

    # Preserve the entity's existing risk-score frontmatter (this is a structural
    # cascade update, not a re-score) — read it back rather than reset to 0/calm.
    current_fm = parse_frontmatter(load_wiki_page(data.trigger_entity))
    risk = current_fm.get("risk") or {}
    factors = risk.get("factors") or {}

    page = await synthesize(
        signal=signal,
        entity=data.trigger_entity,
        risk_score=risk.get("score"),
        risk_band=risk.get("band"),
        factor_ais=factors.get("ais", 0.0),
        factor_gdelt=factors.get("gdelt", 0.0),
        factor_price=factors.get("price", 0.0),
        factor_sanctions=factors.get("sanctions", 0.0),
        rationale=f"System 2 scenario {data.scenario_id}",
        model_version="ario-io-abm",
        persist=False,
    )

    errors = validate_page(page)
    if errors:
        log.warning(
            "Scenario wiki page for '%s' failed validation (keeping old page): %s",
            data.trigger_entity, errors,
        )
        return
    write_wiki_page(data.trigger_entity, page)


# ---------------------------------------------------------------------------
# C7.1 — System 3: Procurement recommendation
# ---------------------------------------------------------------------------

async def write_procurement(data: ProcurementRecData) -> EpisodeRef:
    """
    alt_procurement_agent calls this after TOPSIS ranking completes.
    Creates a ranked procurement recommendation episode linked to the scenario.
    """
    from graphiti_core.nodes import EpisodeType
    from knowledge.connection import _get_graphiti

    g   = _get_graphiti()
    now = datetime.now(timezone.utc)

    # Build ranked summary for episode body
    ranked_lines = []
    for i, opt in enumerate(data.ranked[:5], 1):
        bd = opt.score_breakdown
        ranked_lines.append(
            f"  {i}. {opt.supplier} ({opt.grade}) via {opt.route_via}: "
            f"${opt.landed_cost_usd_bbl:.2f}/bbl, {opt.lead_time_days:.0f} days, "
            f"TOPSIS {opt.topsis_score:.3f} "
            f"[cost {bd.cost_score:.2f}, lead {bd.lead_time_score:.2f}, "
            f"grade {bd.grade_compatibility_score:.2f}, corridor {bd.corridor_risk_score:.2f}]"
        )

    episode_body = (
        f"Procurement recommendation {data.scenario_id} [{data.status.upper()}].\n"
        f"Target refinery: {data.target_refinery or 'all'}.\n"
        f"Top {min(len(data.ranked), 5)} ranked alternatives:\n"
        + "\n".join(ranked_lines)
        + f"\n\nThis procurement recommendation AFFECTS_SCENARIO {data.scenario_id}."
    )
    if data.ranked:
        episode_body += f"\nRationale for #1: {data.ranked[0].rationale}"

    _demo_active = await _demo_running()
    if not _demo_active:
        await _add_episode(g,
            name=f"procurement_{data.scenario_id}",
            episode_body=episode_body,
            source=EpisodeType.text,
            source_description="SAGE procurement recommendation | System 3",
            reference_time=now,
            entity_types=ENTITY_TYPES,
            edge_types=EDGE_TYPES,
            edge_type_map=EDGE_TYPE_MAP,
        )

    episode_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"procurement_{data.scenario_id}"))

    if data.status != "counterfactual" and data.target_refinery and not _demo_active:
        try:
            await _reconcile_procurement_into_wiki(data, now)
        except Exception as exc:
            log.warning("Procurement wiki reconciliation failed for %s: %s", data.scenario_id, exc)

    await _cache_output("procurement", data.scenario_id, data)
    import asyncio; asyncio.create_task(_force_india_brief())
    return EpisodeRef(episode_uuid=episode_uuid, scenario_id=data.scenario_id)


async def _reconcile_procurement_into_wiki(data: "ProcurementRecData", now: datetime) -> None:
    from contracts.signal import NormalizedSignal
    from knowledge.synthesis import synthesize, write_wiki_page, load_wiki_page
    from knowledge.wikilink_processor import parse_frontmatter, validate_page

    top = data.ranked[0] if data.ranked else None
    summary = (
        f"System 3 procurement analysis for {data.target_refinery}: "
        f"{len(data.ranked)} alternative crude sources ranked. "
        + (
            f"Top option: {top.supplier} ({top.grade}) via {top.route_via} — "
            f"${top.landed_cost_usd_bbl:.2f}/bbl, {top.lead_time_days:.0f} day lead time, "
            f"grade compatibility {top.grade_compatibility:.2f}, TOPSIS score {top.topsis_score:.2f}. "
            if top else ""
        )
        + (
            f"Alternative options: "
            + "; ".join(
                f"{o.supplier} via {o.route_via} (${o.landed_cost_usd_bbl:.2f}/bbl, TOPSIS {o.topsis_score:.2f})"
                for o in data.ranked[1:3]
            ) + "."
            if len(data.ranked) > 1 else ""
        )
    )

    signal = NormalizedSignal(
        signal_id=f"procurement_{data.scenario_id}",
        source="scenario",
        observed_at=now,
        ingested_at=now,
        priority_hint="HIGH" if data.status == "confirmed" else "MED",
        force_synthesis=True,
        entity_refs=[data.target_refinery],
        summary=summary,
        payload={"scenario_id": data.scenario_id, "system": "procurement"},
    )

    current_fm = parse_frontmatter(load_wiki_page(data.target_refinery))
    risk = current_fm.get("risk") or {}
    factors = risk.get("factors") or {}

    page = await synthesize(
        signal=signal,
        entity=data.target_refinery,
        risk_score=risk.get("score"),
        risk_band=risk.get("band"),
        factor_ais=factors.get("ais", 0.0),
        factor_gdelt=factors.get("gdelt", 0.0),
        factor_price=factors.get("price", 0.0),
        factor_sanctions=factors.get("sanctions", 0.0),
        rationale=f"System 3 procurement {data.scenario_id}",
        model_version="topsis-routing",
        persist=False,
    )
    if not validate_page(page):
        write_wiki_page(data.target_refinery, page)


# ---------------------------------------------------------------------------
# C7.1 — System 4: SPR drawdown schedule
# ---------------------------------------------------------------------------

async def write_spr_schedule(data: SPRScheduleData) -> EpisodeRef:
    """
    reserve_optim_agent calls this after SDP/CMDP solve completes.
    """
    from graphiti_core.nodes import EpisodeType
    from knowledge.connection import _get_graphiti

    g   = _get_graphiti()
    now = datetime.now(timezone.utc)

    # Summarise daily plan (first 7 days)
    plan_lines = [
        f"Day {d.day}: {d.action.upper()} {d.volume_mmt:.2f} MMT → "
        f"{d.reserve_after_mmt:.2f} MMT ({d.days_cover_after:.1f} days cover)"
        + (f" [{d.decision_driver}]" if d.decision_driver else "")
        for d in data.daily_plan[:7]
    ]

    constraint_str = (
        "✓ CMDP chance constraint satisfied"
        if data.constraint_satisfied
        else "⚠ CMDP chance constraint NOT satisfied"
    )

    episode_body = (
        f"SPR drawdown schedule {data.scenario_id} [{data.status.upper()}].\n"
        f"P(reserve > 3-day buffer): {data.prob_above_buffer:.1%}. {constraint_str}.\n"
        + (f"Lagrange multiplier: {data.lagrange_multiplier:.4f}.\n" if data.lagrange_multiplier else "")
        + (f"Option value of 5-day delay: ${data.option_value_of_waiting:.2f}/bbl.\n" if data.option_value_of_waiting else "")
        + "First 7 days of drawdown schedule:\n"
        + "\n".join(plan_lines)
        + f"\n\nPolicy memo: {data.policy_memo}"
        + f"\n\nThis SPR schedule AFFECTS_SCENARIO {data.scenario_id}."
    )

    _demo_active = await _demo_running()
    if not _demo_active:
        await _add_episode(g,
            name=f"spr_{data.scenario_id}",
            episode_body=episode_body,
            source=EpisodeType.text,
            source_description="SAGE SPR schedule | System 4",
            reference_time=now,
            entity_types=ENTITY_TYPES,
            edge_types=EDGE_TYPES,
            edge_type_map=EDGE_TYPE_MAP,
        )

    episode_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"spr_{data.scenario_id}"))

    if data.status != "counterfactual" and not _demo_active:
        try:
            await _reconcile_spr_into_wiki(data, now)
        except Exception as exc:
            log.warning("SPR wiki reconciliation failed for %s: %s", data.scenario_id, exc)

    await _cache_output("spr", data.scenario_id, data)
    import asyncio; asyncio.create_task(_force_india_brief())
    return EpisodeRef(episode_uuid=episode_uuid, scenario_id=data.scenario_id)


async def _reconcile_spr_into_wiki(data: "SPRScheduleData", now: datetime) -> None:
    from contracts.signal import NormalizedSignal
    from knowledge.synthesis import synthesize, write_wiki_page, load_wiki_page
    from knowledge.wikilink_processor import parse_frontmatter, validate_page

    total_draw  = sum(d.volume_mmt for d in data.daily_plan)
    draw_days   = sum(1 for d in data.daily_plan if d.action == "draw")
    end_reserve = data.daily_plan[-1].reserve_after_mmt if data.daily_plan else 0.0
    constraint  = "CMDP chance constraint satisfied" if data.constraint_satisfied else "CMDP chance constraint VIOLATED — current SPR fill insufficient to maintain emergency buffer through the projected gap"

    summary = (
        f"System 4 SPR optimisation for scenario {data.scenario_id}: "
        f"optimal drawdown over {draw_days} days, total release {total_draw:.3f} MMT. "
        f"Ending reserve {end_reserve:.2f} MMT. "
        f"P(reserve > 3-day emergency buffer) = {data.prob_above_buffer:.1%}. "
        f"{constraint}. "
        + (f"Real-options: option value of 5-day delay = ${data.option_value_of_waiting:.1f}/MMT equivalent. " if data.option_value_of_waiting else "")
        + f"Policy: {data.policy_memo[:300]}"
    )

    signal = NormalizedSignal(
        signal_id=f"spr_{data.scenario_id}",
        source="scenario",
        observed_at=now,
        ingested_at=now,
        priority_hint="HIGH" if data.status == "confirmed" else "MED",
        force_synthesis=True,
        entity_refs=["India SPR"],
        summary=summary,
        payload={"scenario_id": data.scenario_id, "system": "spr", "constraint_satisfied": data.constraint_satisfied},
    )

    current_fm = parse_frontmatter(load_wiki_page("India SPR"))
    risk = current_fm.get("risk") or {}
    factors = risk.get("factors") or {}

    page = await synthesize(
        signal=signal,
        entity="India SPR",
        risk_score=risk.get("score"),
        risk_band=risk.get("band"),
        factor_ais=factors.get("ais", 0.0),
        factor_gdelt=factors.get("gdelt", 0.0),
        factor_price=factors.get("price", 0.0),
        factor_sanctions=factors.get("sanctions", 0.0),
        rationale=f"System 4 SPR schedule {data.scenario_id}",
        model_version="sdp-cmdp",
        persist=False,
    )
    if not validate_page(page):
        write_wiki_page("India SPR", page)


# ---------------------------------------------------------------------------
# C7.1 — Sandbox: PendingScenario (speculative, isolated)
# ---------------------------------------------------------------------------

async def write_pending(
    confidence: float,
    projected_crossing_hours: float,
    scenario_ref: str,
    entity: Optional[str] = None,
) -> EpisodeRef:
    """
    Sandbox calls this to persist a PendingScenario node.

    ISOLATION RULE: This write path NEVER writes a RISK_STATE edge on any live node.
    Speculative risk lives only inside the PendingScenario entity.
    """
    from graphiti_core.nodes import EpisodeType
    from knowledge.connection import _get_graphiti

    g   = _get_graphiti()
    now = datetime.now(timezone.utc)

    band = score_to_band(confidence)

    episode_body = (
        f"[SPECULATIVE] Sandbox PendingScenario {scenario_ref}.\n"
        f"Projected threshold crossing within {projected_crossing_hours:.0f} hours "
        f"with confidence {confidence:.0%} ({band}).\n"
        f"Status: speculative. This is a sandbox projection — NOT a RISK_STATE on any live node.\n"
        + (f"Trigger entity: {entity}.\n" if entity else "")
        + f"Scenario ref: {scenario_ref}. "
        f"This PendingScenario AFFECTS_SCENARIO {scenario_ref}."
    )

    # Skip entity extraction (entity_types=[]) — speculative sandbox notes don't need
    # Nova Pro extraction; storing the raw episode text is sufficient.
    await _add_episode(g,
        name=f"pending_{scenario_ref}",
        episode_body=episode_body,
        source=EpisodeType.text,
        source_description="SAGE sandbox | speculative",
        reference_time=now,
        entity_types=[],
        edge_types=[],
        edge_type_map={},
    )

    episode_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"pending_{scenario_ref}"))
    return EpisodeRef(episode_uuid=episode_uuid, scenario_id=scenario_ref)


# ---------------------------------------------------------------------------
# C7.1 — Sandbox promotion (called by LangGraph monitor on live crossing)
# ---------------------------------------------------------------------------

async def promote_pending(scenario_ref: str, entity: str = "") -> EpisodeRef:
    """
    Called by triggers.on_action() when live risk_score crosses ACTION_THRESHOLD
    and a speculative PendingScenario exists.

    Per C6 promotion contract:
      1. Write a 'promoted' episode (makes the crossing auditable in the graph)
      2. Record a TRUE POSITIVE feedback outcome
      3. Publish scenario.promoted to sage:events WebSocket channel
      4. Trigger Systems 2→3→4 re-run with status='confirmed' so speculative
         outputs are superseded by confirmed ones in the same graph hop

    Note: we supersede speculative episodes by running the agents again with
    status='confirmed' rather than trying to mutate existing episodes —
    Graphiti's bitemporal model means the new confirmed episode naturally
    invalidates the old speculative one via the deduplication pass.
    """
    import json
    import os

    from graphiti_core.nodes import EpisodeType
    from knowledge.connection import _get_graphiti

    g   = _get_graphiti()
    now = datetime.now(timezone.utc)

    episode_body = (
        f"Sandbox PendingScenario {scenario_ref} has been confirmed for {entity or 'entity'}. "
        f"Live risk score crossed the action threshold at {now.strftime('%Y-%m-%d %H:%M')}Z. "
        f"Speculative status promoted to confirmed. "
        f"Systems 2, 3, and 4 are re-running against live state to supersede speculative outputs. "
        f"This promoted scenario AFFECTS_SCENARIO {scenario_ref}."
    )

    # Promoted episodes record the crossing event — no entity extraction needed,
    # the crossing entity is already in the graph from the original ingest path.
    await _add_episode(g,
        name=f"promoted_{scenario_ref}",
        episode_body=episode_body,
        source=EpisodeType.text,
        source_description="SAGE sandbox promotion",
        reference_time=now,
        entity_types=[],
        edge_types=[],
        edge_type_map={},
    )

    episode_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"promoted_{scenario_ref}"))

    # Feedback: record TRUE POSITIVE outcome
    try:
        from knowledge.feedback import record_confirmed_outcome
        await record_confirmed_outcome(
            scenario_id=scenario_ref,
            entity=entity,
            predicted_confidence=0.0,
            predicted_crossing_hours=0.0,
            actual_crossing_hours=0.0,
            actual_peak_risk=0.0,
            feature_vector_at_prediction={},
        )
    except Exception as exc:
        log.warning("Feedback record failed for promotion %s (non-fatal): %s", scenario_ref, exc)

    # Publish scenario.promoted so the WebSocket gateway can notify the frontend
    try:
        import redis.asyncio as aioredis
        redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
        client = aioredis.from_url(redis_url, decode_responses=True)
        try:
            await client.publish("sage:events", json.dumps({
                "type": "scenario.promoted",
                "entity": entity,
                "scenario_ref": scenario_ref,
                "stage": "SCENARIO",
                "status": "promoted",
            }))
        finally:
            await client.aclose()
    except Exception as exc:
        log.warning("Redis publish failed for promotion %s (non-fatal): %s", scenario_ref, exc)

    # Notify triggers module so it can publish the full pipeline stage sequence
    try:
        from orchestration.triggers import on_sandbox_promoted
        await on_sandbox_promoted(entity, scenario_ref)
    except Exception as exc:
        log.warning("on_sandbox_promoted failed (non-fatal): %s", exc)

    return EpisodeRef(episode_uuid=episode_uuid, scenario_id=scenario_ref)
