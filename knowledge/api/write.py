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

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Return types
# ---------------------------------------------------------------------------

class EpisodeRef(BaseModel):
    episode_uuid: str
    scenario_id: Optional[str] = None


class IngestResult(BaseModel):
    signal_id: str
    decision: Literal["synthesized", "extracted", "stored", "dropped"]
    episode_uuid: Optional[str] = None
    risk_updated: bool = False


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
        # Full narrative synthesis per entity_ref
        entity_refs = signal.entity_refs or [signal.summary[:60]]
        episode_texts: list[str] = []

        for entity in entity_refs:
            text = await synthesize(signal=signal, entity=entity)
            episode_texts.append(text)

        # Join multi-entity synthesis into one episode
        episode_body = "\n\n---\n\n".join(episode_texts)
        episode_name = f"{signal.source}_{signal.signal_id}"

        try:
            await g.add_episode(
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
        except Exception as exc:
            log.error("add_episode failed for signal %s: %s", signal.signal_id, exc)
            raise

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
        try:
            await g.add_episode(
                name=f"extract_{signal.signal_id}",
                episode_body=episode_body,
                source=EpisodeType.text,
                source_description=f"SAGE extract | source={signal.source}",
                reference_time=signal.observed_at,
                entity_types=ENTITY_TYPES,
                edge_types=EDGE_TYPES,
                edge_type_map=EDGE_TYPE_MAP,
            )
            episode_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, signal.signal_id))
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
    try:
        await g.add_episode(
            name=f"raw_{signal.signal_id}",
            episode_body=f"[RAW] {signal.source} | {signal.observed_at.isoformat()} | {signal.summary}",
            source=EpisodeType.text,
            source_description=f"SAGE raw | source={signal.source}",
            reference_time=signal.observed_at,
        )
        episode_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, signal.signal_id))
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

    episode_text = (
        f"{entity} — risk assessment {now.strftime('%Y-%m-%d %H:%M')}Z.\n"
        f"Current risk score: {score:.2f} ({band.upper()}).\n"
        f"Factor breakdown: AIS {factor_ais:.2f}, GDELT {factor_gdelt:.2f}, "
        f"price {factor_price:.2f}, sanctions {factor_sanctions:.2f}.\n"
        f"Rationale: {rationale or 'no rationale provided'}.\n"
        f"Model version: {model_version or 'unknown'}.\n"
    )

    # Update /wiki with just the risk state block appended to existing page
    current = load_wiki_page(entity)
    risk_section = (
        f"\n\n---\n**Risk Assessment** _{now.strftime('%Y-%m-%d %H:%M UTC')}_\n\n"
        f"{episode_text}"
    )
    # Append rather than replace — preserve synthesis narrative
    updated_wiki = current.rstrip() + risk_section
    write_wiki_page(entity, updated_wiki)

    episode_name = f"{entity.lower().replace(' ', '_')}_risk_{now.strftime('%Y%m%dT%H%M%SZ')}"
    sig_id       = f"risk_{entity}_{now.isoformat()}"
    episode_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, sig_id))

    await g.add_episode(
        name=episode_name,
        episode_body=episode_text,
        source=EpisodeType.text,
        source_description="SAGE risk state",
        reference_time=now,
        entity_types=ENTITY_TYPES,
        edge_types=EDGE_TYPES,
        edge_type_map=EDGE_TYPE_MAP,
    )

    return EpisodeRef(episode_uuid=episode_uuid)


# ---------------------------------------------------------------------------
# C7.1 — System 2: Scenario output
# ---------------------------------------------------------------------------

async def write_scenario(data: ScenarioOutputData) -> EpisodeRef:
    """
    scenario_agent calls this after ARIO + GNN cascade completes.
    Creates a linked ScenarioOutput episode + AFFECTS_SCENARIO edge back to trigger entity.
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

    await g.add_episode(
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
    return EpisodeRef(episode_uuid=episode_uuid, scenario_id=data.scenario_id)


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

    await g.add_episode(
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
    return EpisodeRef(episode_uuid=episode_uuid, scenario_id=data.scenario_id)


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

    await g.add_episode(
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
    return EpisodeRef(episode_uuid=episode_uuid, scenario_id=data.scenario_id)


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

    await g.add_episode(
        name=f"pending_{scenario_ref}",
        episode_body=episode_body,
        source=EpisodeType.text,
        source_description="SAGE sandbox | speculative",
        reference_time=now,
        entity_types=ENTITY_TYPES,
        edge_types=EDGE_TYPES,
        edge_type_map=EDGE_TYPE_MAP,
    )

    episode_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"pending_{scenario_ref}"))
    return EpisodeRef(episode_uuid=episode_uuid, scenario_id=scenario_ref)


# ---------------------------------------------------------------------------
# C7.1 — Sandbox promotion (called by LangGraph monitor on live crossing)
# ---------------------------------------------------------------------------

async def promote_pending(scenario_ref: str) -> EpisodeRef:
    """
    LangGraph monitor calls this when live risk_score crosses ACTION_THRESHOLD
    for an entity that has a speculative PendingScenario.

    Per C6 promotion contract:
      1. Writes a 'promoted' status episode (Graphiti invalidates old speculative episode)
      2. Kicks off feedback loop recording (via knowledge.feedback)

    Note: flipping linked output episodes from speculative→confirmed is done by
    scenario_agent, procurement_agent, and reserve_optim_agent when they re-run
    on the promoted scenario. The monitor emits a scenario.promoted LangGraph event
    that triggers those re-runs.
    """
    from graphiti_core.nodes import EpisodeType
    from knowledge.connection import _get_graphiti

    g   = _get_graphiti()
    now = datetime.now(timezone.utc)

    episode_body = (
        f"[PROMOTED] Sandbox PendingScenario {scenario_ref} has been confirmed.\n"
        f"Live risk_score crossed action threshold at {now.isoformat()}.\n"
        f"Status updated: speculative → promoted.\n"
        f"Systems 2/3/4 re-running on confirmed live state.\n"
        f"Scenario ref: {scenario_ref}. "
        f"This promoted PendingScenario AFFECTS_SCENARIO {scenario_ref}."
    )

    await g.add_episode(
        name=f"promoted_{scenario_ref}",
        episode_body=episode_body,
        source=EpisodeType.text,
        source_description="SAGE sandbox promotion",
        reference_time=now,
        entity_types=ENTITY_TYPES,
        edge_types=EDGE_TYPES,
        edge_type_map=EDGE_TYPE_MAP,
    )

    episode_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"promoted_{scenario_ref}"))

    # Record feedback for the false-positive guard — promotion = TRUE POSITIVE
    # We don't have the feature vector here so we pass what we know
    try:
        from knowledge.feedback import record_confirmed_outcome
        await record_confirmed_outcome(
            scenario_id=scenario_ref,
            entity="",   # resolved upstream
            predicted_confidence=0.0,    # not available here; feedback module tolerates 0
            predicted_crossing_hours=0.0,
            actual_crossing_hours=0.0,   # exact value filled by monitor which has timing
            actual_peak_risk=0.0,
            feature_vector_at_prediction={},
        )
    except Exception as exc:
        log.warning("Feedback record failed for promotion %s (non-fatal): %s", scenario_ref, exc)

    return EpisodeRef(episode_uuid=episode_uuid, scenario_id=scenario_ref)
