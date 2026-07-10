# SAGE — Session Handoff

**Last updated:** 2026-07-10  
**Stack state:** FULLY UP AND HEALTHY (all 9 containers)

---

## System Status (as of handoff)

```
sage-core        UP   (knowledge base, ingest queue, monitor, LangGraph)
api-gateway      UP   (port 8000, /health → ok, kb_ready: true)
frontend         UP   (port 80, healthy)
falkordb         UP   (port 6379, healthy — graph store)
redis            UP   (port 6380, healthy — output cache)
sensory-news     UP   (NEWSDATA → episodic ingest)
sensory-ais      UP   (AISSTREAM → episodic ingest)
sensory-prices   UP   (yfinance/EIA → volatile store)
sensory-sanctions UP  (OFAC+UN → episodic ingest)
```

**KB:** 59 entities monitored, 2 entities have RISK_STATE scores (KazMunayGas, WTI Midland), rest still at 0.0 (no threshold crossing yet since fresh restart).  
**Live Intelligence:** 15 real signals in /api/intelligence  
**Systems 2/3/4 cache:** Empty — no threshold crossing has fired since restart (expected in calm state).  
**Brent:** $95.0/bbl (EIA-STEO baseline)

---

## What Was Built (Complete Architecture)

### Three-Store Knowledge Base
- **FalkorDB** — semantic graph: 61 nodes (energy entities), edges with `throughput_share_pct`, `RISK_STATE` on each node
- **Graphiti** — episodic memory: timestamped signal episodes with `MENTIONS` edges to entity nodes
- **Obsidian wiki** — wikilink synthesis: per-entity markdown pages at `knowledge/wiki/`

### System 1 — Sensory Agents (`sensory_agent/`)
4 live feeds running continuously:
- `prices.py` — yfinance BZ=F every 15min → volatile store + episodic
- `news.py` — NEWSDATA API every 10min → episodic ingest
- `ais.py` — AISSTREAM websocket → episodic ingest  
- `sanctions.py` — OFAC + UN lists daily → episodic ingest

All run via `sensory_agent/runner.py` (lazy imports, avoids cross-dep crashes).

### System 2/3/4 — Response Pipeline (`orchestration/`)
- **LangGraph** `build_response_graph()` in `orchestration/graph.py` — compiled StateGraph: `refresh → scenario → procure → reserve`
- Fires via `orchestration/triggers.py` on threshold crossing (RISK_STATE > 0.65)
- Outputs cached to Redis: `sage:scenario:latest`, `sage:procurement:latest`, `sage:spr:latest`
- Frontend reads via `/api/scenario`, `/api/procurement`, `/api/reserve`

### Risk Engine (`knowledge/ingest_queue.py`)
- Synthesis-first: signals → Nova Micro triage → Nova Pro synthesis → fusion → RISK_STATE
- Escalate-fast/decay-slow: `RISK_HALF_LIFE_H=48`
- In-process `_last_risk` cache (race-free, fixes fusion overwrite bug)
- After write: calls `cascade_risk_from()` + `_maybe_learn_edges()` for HIGH signals

### Risk Cascade (`knowledge/cascade.py`)
- BFS along EXPOSES/FEEDS/SUPPLIES/EXPORTS_VIA edges
- Exposure-weighted decay using real `throughput_share_pct` from `.context` bundle
- Falls back to `CASCADE_DECAY=0.6`

### Edge-Weight Learning (`knowledge/edge_learning.py`)
- Nova Pro detects dependency-share changes in HIGH signals
- Bitemporal Cypher SET on `throughput_share_pct`
- `_resolve()` uses canonical registry for name matching

### Volatile / Semi-Static Tier (`knowledge/context/volatile.py`, `volatile_refresh.py`)
- Redis hash + in-process dict overrides for params like `baseline_brent_usd_per_bbl`
- `prices.py` feeds this on every BZ=F poll
- `DEMO_MODE=true` loads from `data/demo_fixtures/volatile_feb2026.json`

### Per-Node Provenance (`knowledge/context/provenance.py`)
- `prov_source_url`, `prov_tier`, `prov_source_label`, `prov_as_of` on every FalkorDB node
- Hooked as Phase 4 of `loader.instantiate()`

### India Supply-Chain Stability Index
- Degree-weighted mean of all RISK_STATE scores
- Exposed via `/api/dashboard` as `supply_chain_index`

### Live Intelligence + Evidence (`knowledge/api/read.py`)
- `get_recent_intelligence(limit)` — 5-day window, dedup by headline, real signals only
- `get_evidence_for(entity, limit)` — MENTIONS-edge query for entity's source episodes
- Both exposed via gateway: `/api/intelligence`, `/api/evidence/{entity}`

### Frontend (`visualizer_agent/frontend/src/`)
- **Zero mock data** — `api/mock.ts` deleted, all fallbacks removed
- `CommandCenter.tsx` — Live Intelligence rail (max-height 300px scroll), Evidence buttons (AIS/News/Sanctions/Price with strict source mapping), clickable ↗ source links
- `api/client.ts` — errors return `{ data: null, live: false }` (OFFLINE state, no mocks)
- Wiki drawer: wikilink navigation with back button, breadcrumb, framer-motion animations
- Map: uniform nodes, gold rings for top-10% hubs, edges hidden at rest, zoom-to-fit on click

---

## File Map (Key Files)

| File | Purpose |
|---|---|
| `knowledge/ingest_queue.py` | Core fusion engine, risk decay, cascade trigger |
| `knowledge/cascade.py` | BFS exposure-weighted risk propagation |
| `knowledge/edge_learning.py` | LLM-driven bitemporal edge weight updates |
| `knowledge/api/read.py` | Graph reads: intelligence, evidence, index, provenance |
| `knowledge/api/write.py` | Episode write + source_url stamping |
| `knowledge/context/volatile.py` | Semi-static param store (Redis + in-process) |
| `knowledge/context/volatile_refresh.py` | Price feed → volatile store |
| `knowledge/context/provenance.py` | Node provenance stamping |
| `orchestration/graph.py` | LangGraph StateGraph + run_response_pipeline |
| `orchestration/triggers.py` | Monitor → LangGraph delegation |
| `sensory_agent/runner.py` | Lazy-import entry point for all sensory agents |
| `sensory_agent/prices.py` | BZ=F price feed → volatile + episodic |
| `visualizer_agent/frontend/src/screens/CommandCenter.tsx` | Main dashboard UI |
| `visualizer_agent/frontend/src/api/client.ts` | API client (zero mocks) |
| `visualizer_agent/api_gateway/main.py` | FastAPI gateway (all /api/* endpoints) |
| `scripts/seed_kb.py` | First-boot KB instantiation (real cited data only) |
| `data/india-energy-2026.context` | 61-entity bundle with edges + params |
| `docs/DEPLOY_EC2.md` | EC2 deployment guide |

---

## Secrets / Keys

- **`.env`** — AWS credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`), LLM provider config. **Never committed.**
- **`.env.local`** — `AISSTREAM_API_KEY`, `EIA_API_KEY`, `NEWSDATA_API_KEY`. **Never committed.**
- AWS keys are NOT exposed in git history (verified: zero AKIA patterns).
- `docker-compose.yml` loads both: `env_file: [.env, .env.local (required: false)]`

---

## Pending / Next Steps

### Immediate (stack is healthy, verify these manually)

1. **Watch for first threshold crossing** — once a real HIGH signal comes in and RISK_STATE crosses 0.65, Systems 2/3/4 will fire and cache outputs. Until then `/api/scenario` etc. return `{"detail":"no ... available"}` — this is correct behaviour.

2. **KB may need re-seeding** — `nodes: 0` in the map graph view means the `get_full_graph` query found no FalkorDB entity nodes. The KB was instantiated (59 entities monitored) but FalkorDB graph nodes may need the static loader to run again:
   ```bash
   docker compose exec sage-core python -m scripts.seed_kb
   ```
   Then refresh the frontend map.

3. **Systems 2/3/4 empty-state UI** — Currently shows "no active disruption" skeleton. The cards (`procurement`, `reserve`, `supply-chain`) should show a calm-state message rather than loading skeletons when cache is empty. Consider adding an explicit empty-state design.

4. **AIS evidence filter** — Verify the Evidence panel AIS button only shows `source` = `ais` episodes (not news/gdelt). Source mapping is in `CommandCenter.tsx` `EV_SOURCES` map.

5. **GDELT dedup** — Live Intelligence had "→ UNITED STATES, Goldstein=-9.5" duplicates from GDELT raw events. Dedup is by headline + filter applied in `get_recent_intelligence`. Verify these no longer appear.

### Design / Hackathon

6. **Voice interface** was mentioned early in session — partially referenced in `command.css` (`cc-kpi-flash` animation for voice `flash_kpi` action). Not yet fully wired up.

7. **DEMO_MODE** fixture (`data/demo_fixtures/volatile_feb2026.json`) for offline presentation — exists as a path but fixture file may need populating.

8. **EC2 deploy** — Guide is at `docs/DEPLOY_EC2.md`. Recommend t3.medium for hackathon demo (4 GiB fits all 9 containers at ~2.5 GiB).

---

## Docker Quick Reference

```bash
# Check status
docker compose ps

# Logs
docker compose logs -f sage-core
docker compose logs -f sensory-news

# Re-seed KB (if map shows 0 nodes)
docker compose exec sage-core python -m scripts.seed_kb

# API health
curl localhost:8000/health
curl localhost:8000/api/dashboard | jq .monitoring_entities
curl localhost:8000/api/intelligence | jq length

# Manual signal poll (optional — agents do this automatically)
PYTHONPATH=. python3 scripts/seed_from_live.py

# Full restart after code change
docker compose up -d --build
docker compose --profile sensory up -d
```

---

## Known Issues (Resolved)

- **Fusion overwrite bug** — FIXED: in-process `_last_risk` cache
- **Sensory containers crash-loop** — FIXED: lazy imports in `sensory_agent/__init__.py`
- **Sensory exit code 0** — FIXED: `runner.py` entry point, Dockerfiles use `python -m sensory_agent.runner <name>`
- **Redis MISCONF (disk exhaustion)** — FIXED: Docker Desktop restarted, `docker system prune -af`, 211 GB freed
- **EU sanctions 404** — FIXED: EU list disabled, OFAC+UN active
- **Naive/aware datetime crash** — FIXED: `_aware(dt)` helper in `ingest_queue.py`

---

## Architecture Decisions (Non-obvious)

- **No golden path seed** — user explicitly removed `scripts/seed_golden_path.py`. System starts at CALM and rises only on real signals. "Pure honesty."
- **`seed_from_live.py` is optional** — System 1 agents run on intervals automatically; this script is just for immediate manual poll.
- **Systems 2/3/4 run in-process** (not separate containers) when triggered by the monitor — cheaper, fits t3.medium.
- **LangGraph is the active orchestrator** — `triggers.py` delegates to `run_response_pipeline()` which streams the StateGraph. `_cold_pipeline` is now 3 lines.
- **Escalate-fast / decay-slow** — new signals can only raise risk; decay happens via `RISK_HALF_LIFE_H=48` time factor. Prevents brief blips from wiping CRITICAL risk.
