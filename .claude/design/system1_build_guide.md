# Building System 1 — Step-by-Step Guide

> Supersedes the bug-focused `system1_interaction.md` (whose §6 "critical bugs" are now fixed).
> This is the build guide, grounded in the actual ingest code.

## The mental model

```
YOU BUILD THIS                          ALREADY BUILT & VERIFIED (don't touch)
┌─────────────────────┐                ┌──────────────────────────────────────┐
│ 4 sub-agents         │  push_signal  │ ingest_queue.run_consumer_loop()      │
│ ais / news /         │ ────────────► │  → ingest_signal() → triage gate      │
│ sanctions / prices   │  (Redis)      │     → synthesize (news/sanctions)     │
│                      │               │     → extract   (ais/price)           │
│ Each: detect → build │               │  → buffer per entity                  │
│ NormalizedSignal →   │               │  → every 30s: fusion → write_risk_state│
│ push_signal()        │               │     → wiki + graph + vectors          │
└─────────────────────┘                └──────────────────────────────────────┘
```

A sub-agent's entire contract is: produce a `NormalizedSignal` with the right `source`,
`entity_refs`, and `payload`, then call `push_signal()`. You never call `ingest_signal`, `triage`,
the fusion, or `write_risk_state` — the consumer does all of that.

---

## Step 0 — Shared scaffolding (do once)

```python
# sensory_agent/_base.py
import uuid
from datetime import datetime, timezone
from contracts.signal import NormalizedSignal
from knowledge.ingest_queue import push_signal

def new_signal_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

async def emit(signal: NormalizedSignal) -> None:
    """The ONLY way a sub-agent touches the KB."""
    await push_signal(signal)
```

Entity resolution is mandatory — never put free-form names in `entity_refs`:

```python
from knowledge.registry import (
    resolve_h3, resolve_instrument, resolve_name, canonical_name, register_vessel,
)
```

---

## The payload contract — THE critical detail

The fusion consumer (`ingest_queue._run_fusion_for_entity`) reads **specific payload keys** to build
the risk score. Wrong key name → that factor silently reads 0. Authoritative (from the code):

| Source | Required `payload` keys (exact) |
|---|---|
| **ais** | `gap_hours` (float), `dark_vessel` (bool), `anomaly_score` (0..1), `h3_cell` (str), `velocity_std` (float, opt) |
| **news**/**gdelt** | `tone` or `gdelt_tone` (neg=hostile), `tone_delta` (opt), `severity` (0..1; >0.7 counts as event) |
| **price** | `price_change_pct` (float), `changepoint` (bool) or `bocd_probability` (>0.8), `regime_stressed` (0/1), `war_risk_premium_proxy` (float) |
| **sanctions** | `change` (`add`/`remove`), `subject_type` (`entity`/`person`/`state`/`vessel`), `vessel_mmsi` (str, if vessel) |

---

## Build order: easiest → hardest

### Step 1 — Prices (build first; deterministic, no streaming)

yfinance `BZ=F`/`CL=F` every 5 min. Push ONLY on BOCD changepoint/regime shift — never normal ticks.

```python
# sensory_agent/prices.py
from contracts.signal import NormalizedSignal
from knowledge.registry import resolve_instrument, canonical_name
from sensory_agent._base import emit, new_signal_id, utcnow
import yfinance as yf

_series = {"BZ=F": [], "CL=F": []}

async def poll_instrument(instrument: str):
    price = float(yf.Ticker(instrument).history(period="1d", interval="5m")["Close"].iloc[-1])
    _series[instrument].append(price)
    cp = detect_changepoint(_series[instrument])          # your BOCD
    if not (cp.is_changepoint or cp.regime_shift):
        return                                            # normal tick → DO NOT push
    entity_ids = resolve_instrument(instrument)
    if not entity_ids:
        return
    await emit(NormalizedSignal(
        signal_id=new_signal_id("price"), source="price",
        observed_at=utcnow(), ingested_at=utcnow(),
        priority_hint="HIGH", force_synthesis=False,      # ais/price NEVER force synthesis
        entity_refs=[canonical_name(eid) for eid in entity_ids],
        summary=f"{instrument} BOCD changepoint: {cp.pct:+.1f}% move, regime {cp.regime}",
        payload={
            "instrument": instrument, "price": price, "price_change_pct": cp.pct,
            "changepoint": True, "bocd_probability": cp.probability,
            "regime_stressed": 1.0 if cp.regime != "calm" else 0.0,
            "war_risk_premium_proxy": cp.war_risk_premium,
        },
    ))
```

### Step 2 — Sanctions (deterministic diff; always synthesizes)

OFAC SDN XML + EU + UN, diff vs last snapshot, push on every change. `force_synthesis=True` always.

```python
# sensory_agent/sanctions.py
from knowledge.registry import resolve_name, canonical_name, register_vessel

async def on_diff(entries: list[dict]):
    for e in entries:
        subject, mmsi = e["subject"], e.get("mmsi")
        eid = resolve_name(subject)
        if not eid and mmsi:                              # new vessel → register FIRST
            eid = register_vessel(mmsi=mmsi, vessel_name=subject, imo=e.get("imo"))
        refs = [canonical_name(eid)] if eid else [subject]
        if (op := e.get("operator")) and (op_id := resolve_name(op)):
            refs.append(canonical_name(op_id))
        await emit(NormalizedSignal(
            signal_id=new_signal_id("sanctions"), source="sanctions",
            observed_at=utcnow(), ingested_at=utcnow(),
            priority_hint="HIGH", force_synthesis=True,   # sanctions ALWAYS synthesize
            entity_refs=refs,
            summary=f"{e['list']}: {subject} {e['change']}ed — {e.get('subject_type','entity')}",
            payload={"list": e["list"], "change": e["change"], "subject": subject,
                     "subject_type": e.get("subject_type", "entity"),
                     "vessel_mmsi": mmsi, "operator": e.get("operator")},
        ))
```

Run every 6h + immediately on detected change. Removals matter too.

### Step 3 — News/GDELT (LLM extraction; triage decides)

GDELT 2.0 + NewsAPI every 15 min. Nova Micro extraction → resolve → discard unresolved.

```python
# sensory_agent/news.py
async def on_article(text, url, published_at):
    candidates = await nova_micro_extract_entities(text)
    refs = [canonical_name(eid) for name in candidates if (eid := resolve_name(name))]
    if not refs:
        return                                            # no tracked entity → discard
    sev = await estimate_severity(text)
    await emit(NormalizedSignal(
        signal_id=new_signal_id("news"), source="news",
        observed_at=published_at, ingested_at=utcnow(),
        priority_hint="HIGH" if sev > 0.6 else "MED",
        force_synthesis=False,                            # let triage similarity-gate decide
        entity_refs=refs,
        summary=first_sentence(text),                     # becomes the LLM "NEW SIGNAL" block
        payload={"actor": actor, "action": action, "tone": gdelt_tone,
                 "severity": sev, "tone_delta": tone_delta},
        source_url=url,
    ))
```

### Step 4 — AIS (build last; streaming + detection)

aisstream.io websocket. Push per anomaly cluster, never per ping. `force_synthesis=False` always.

```python
# sensory_agent/ais.py
async def on_anomaly_cluster(h3_cell, mmsi, gap_hours, anomaly_score, dark_count):
    eid = resolve_h3(h3_cell)
    if not eid:
        return                                            # cell not tracked → discard
    await emit(NormalizedSignal(
        signal_id=new_signal_id("ais"), source="ais",
        observed_at=utcnow(), ingested_at=utcnow(),
        priority_hint="HIGH", force_synthesis=False,      # AIS NEVER force-synthesizes
        entity_refs=[canonical_name(eid)], h3_cells=[h3_cell], lat=26.1, lon=57.2,
        summary=f"AIS dark-vessel cluster: {dark_count} vessels near {canonical_name(eid)}, {gap_hours:.0f}h gap",
        payload={"mmsi": mmsi, "gap_hours": gap_hours, "dark_vessel": True,
                 "anomaly_score": anomaly_score, "h3_cell": h3_cell, "dark_count": dark_count},
    ))
```

Internally: H3-index positions → detect gaps (>4h) → cluster → emit one signal per cluster.

---

## How risk scores happen (you don't write them)

You never call `write_risk_state`. The consumer does, automatically:
1. Each pushed signal is buffered per entity (`_signal_buffer`).
2. Every 30s (or 10 signals): `_run_fusion_for_entity` reads your payload keys → builds the 17-D
   `_FeatureVector` → `_predict` (weighted-sum fallback, or a trained GBM at `FUSION_MODEL_PATH`)
   → `write_risk_state`.
3. `write_risk_state` writes the `RISK_STATE` graph edge (deterministic, bitemporal) + updates the
   wiki frontmatter. The orchestration monitor reads it via `get_risk_scores`.

Your job for risk scores = emit the right payload keys. To improve scoring, train a GBM matching the
`_FeatureVector`/`_FusionResult` interface and save it to `FUSION_MODEL_PATH`.

## How the triage gate works (you don't call it)

You influence triage via `source` + `force_synthesis`:

| `source` | Triage routes to | Set |
|---|---|---|
| `ais`, `price` | `extract` (always) — graph factors, no prose | `force_synthesis=False` |
| `sanctions` | `synthesize` (always) — implications prose | `force_synthesis=True` |
| `news`/`gdelt` | similarity-based | `force_synthesis=False` |

Enforced in `knowledge/triage.py` (`_NUMERIC_SOURCES`, `_ALWAYS_SYNTH_SOURCES`).

---

## Run & test

```bash
docker compose up falkordb redis -d
docker compose up sage-core                              # runs run_consumer_loop()
docker compose --profile sensory up sensory-prices      # enable each sub-agent
```

Verify a signal flowed end-to-end:
```python
from knowledge.api.read import get_risk_scores, get_wiki_page
scores = await get_risk_scores()                         # your entity appears with a score
page   = await get_wiki_page("Strait of Hormuz")         # updated if news/sanctions
```

---

## Build checklist (per sub-agent)

- [ ] Calls only `push_signal()` — never `ingest_signal`, `write_risk_state`, `add_episode`, triage
- [ ] `entity_refs` via `resolve_h3`/`resolve_instrument`/`resolve_name` → `canonical_name`
- [ ] `payload` uses the exact keys from the contract table
- [ ] AIS: per cluster not per ping; `force_synthesis=False`
- [ ] Price: only on BOCD changepoint/regime; `force_synthesis=False`
- [ ] Sanctions: `force_synthesis=True`; `register_vessel()` before new MMSI; handle removals
- [ ] News: `force_synthesis=False`; discard unresolved; informative `summary`
- [ ] `observed_at` = event time, not emit time; `signal_id` unique per signal
- [ ] Container calls `await kb_init()` at boot; `sage-core` consumer is running

---

## Novel-entity promotion — registry growth (wire after System 1 ships)

When System 1 encounters an entity NOT in the registry (a new vessel, an unlisted
supplier, an emerging port), the graph extraction still creates the node, but it won't
get a canonical name, wiki page, or `[[wikilink]]` eligibility until promoted.

**What to wire:**
1. Sanctions sub-agent already has `register_vessel(mmsi, name, operator)` in
   `knowledge/registry.py:579` — it's defined but never called. Wire it when a new
   MMSI appears on the SDN list and is not in `REGISTRY`.
2. For new suppliers or ports surfaced by news/AIS: add `register_entity(entity_id,
   canonical_name, entity_type, aliases, coordinates)` — same pattern as
   `register_vessel` but generalised.
3. After `register_*`, call `synthesize(signal, entity=canonical_name, persist=True)`
   to seed the initial wiki page from the signal that introduced the entity.
4. The registry is in-memory and boots from the `.context` bundle. For promoted
   entities to survive restarts, write them back to
   `data/india-energy-2026.context/facts/nodes/<type>.csv` (or a separate
   `facts/nodes/dynamic.csv`) and re-instantiate.

**Why it matters:** without promotion, the knowledge graph grows new nodes from
signals (correct, happens automatically via Graphiti extraction) but the narrative
layer (wiki + `[[wikilinks]]`) stays blind to them. Promotion closes that gap so
the system's understanding — not just its graph — evolves dynamically.
