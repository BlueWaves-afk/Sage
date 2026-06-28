# SAGE Knowledge Base — Deployment Guide

**Project:** SAGE · Problem Statement 2 (AI-Driven Energy Supply Chain Resilience)
**Scope:** Everything needed to go from zero to a running knowledge base on AWS EC2 — infrastructure, containers, environment, cost, and the daily operational picture.
**Companion specs:**
- [`SAGE_Knowledge_Base_Spec.md`](./SAGE_Knowledge_Base_Spec.md) — architecture narrative
- [`SAGE_Schema_and_Contracts_Spec.md`](./SAGE_Schema_and_Contracts_Spec.md) — normative schema & contracts

---

## 1. What Language Everything Is Written In

| Layer | Language / Runtime | Why |
|---|---|---|
| **All contracts (C0–C7)** | **Python 3.11+, Pydantic v2** | Contracts are Pydantic `BaseModel` classes. Every field, type, default, and description is Python. |
| **SAGE core pipeline** | Python 3.11+ (async/await) | `graphiti-core` is a Python library. The triage gate, narrative synthesis agent, and write orchestration are all `async def` functions. |
| **LangGraph orchestration** | Python 3.11+ | LangGraph is a Python-native state machine library. The monitor, sandbox manager, and autonomous trigger loop are LangGraph nodes/edges. |
| **System 2 — ARIO cascade** | Python (NumPy / SciPy) + PyTorch | ARIO propagation is pure Python/NumPy. The GNN surrogate is a PyTorch model for GPU inference. |
| **System 3 — Procurement** | Python (OR-Tools, scikit-learn) | OR-Tools MILP solver and the Random Forest + Peng-Robinson EOS compatibility model. |
| **System 4 — SPR** | Python (NumPy) | Bellman iteration for SDP is NumPy arithmetic. Lagrangian relaxation is also pure Python. |
| **System 5 — Frontend** | TypeScript / React + deck.gl | The digital twin map, H3 heatmap, copilot UI, and pipeline status bar. |
| **API gateway** | Python (FastAPI) | REST + WebSocket server bridging the backend pipeline and the React frontend. |
| **Infrastructure / Ops** | Docker Compose (YAML) + Bash | 12-container single-host deployment. No Kubernetes for the hackathon. |
| **Config / secrets** | `.env` file (plain text, never committed) | All API keys, Bedrock region, FalkorDB password. Read by Docker Compose at boot. |

**Summary:** the knowledge base — contracts, schema, Graphiti wrappers, triage, synthesis, read/write API — is **100% Python**. The only non-Python runtime that SAGE core touches is FalkorDB (a native Redis-protocol graph DB running in Docker).

---

## 2. Infrastructure Overview

### 2.1 Deployment Philosophy

Single AWS EC2 instance. One server. Docker Compose. All 12 containers co-located. No Kubernetes, no managed services beyond Bedrock. This minimises setup time and maximises demo reliability. The architecture scales to distributed deployment post-hackathon with infrastructure changes only — no code changes.

### 2.2 Instance

| Spec | Value |
|---|---|
| **Instance type** | `g4dn.xlarge` |
| **vCPUs** | 4 |
| **RAM** | 16 GiB |
| **GPU** | 1× NVIDIA T4 (16 GiB VRAM) |
| **Region** | `ap-south-1` (Mumbai) — lowest latency to India, Nova models available, data stays in India geography |
| **Weeks 1–3** | Spot instance (~$0.24/hr) — LangGraph checkpointing handles interruptions |
| **Week 4 + demo** | On-demand ($0.526/hr) — no interruption risk during presentation |

**Why GPU is mandatory:** the GNN surrogate (System 2) runs PyTorch inference on the T4. On GPU: ~150ms forward pass. On CPU: ~800ms — too slow for the sandbox fork pipeline. The GNN uses ~1 GiB VRAM; 15 GiB remains for headroom.

### 2.3 Storage

| Item | Config | Purpose |
|---|---|---|
| Root EBS | 30 GB gp3 (included) | OS + Docker images + `/wiki` volume |
| Separate EBS | 20 GB gp3, mounted at `/var/lib/falkordb` | FalkorDB data persistence across instance stops. **Critical — do not skip.** |
| S3 bucket | ~2 GB | Demo cache (pre-recorded signal replay) + FalkorDB snapshots backup |

---

## 3. The 12-Container Architecture

All containers run on one internal Docker bridge network. Only the API gateway and frontend are externally exposed.

```
┌─────────────────────────────── EC2 g4dn.xlarge (ap-south-1) ──────────────────────────────┐
│                                                                                              │
│  ┌──────────────┐  ┌──────────────┐                                                         │
│  │  falkordb    │  │    redis     │  ← start first; all others depend_on these two          │
│  │  (port 6379) │  │  (internal)  │                                                         │
│  └──────┬───────┘  └──────┬───────┘                                                         │
│         │                  │                                                                 │
│  ┌──────┴───────┐          │                                                                 │
│  │   graphiti   │          │ LangGraph checkpointing                                        │
│  │  (HTTP API)  │          │                                                                 │
│  └──────┬───────┘          │                                                                 │
│         │                  │                                                                 │
│  ┌──────┴───────────────────┴────────────────────────────────────┐                          │
│  │                        sage-core                              │  ← most critical          │
│  │  LangGraph state machine · triage · synthesis · sandbox mgr  │                          │
│  │  Calls Bedrock Nova Pro (synthesis) + Nova Micro (triage)     │                          │
│  └──────────────────────────────────────────────────────────────┘                          │
│                                                                                              │
│  ┌─────────────────── System 1 (4 sub-agents) ──────────────────┐                          │
│  │  system1-ais      system1-news    system1-sanctions  system1-prices                      │
│  │  (AIS websocket)  (GDELT/RSS)     (OFAC/EU/UN diff)  (EIA/yfinance)                     │
│  └──────────────────────────────────────────────────────────────┘                          │
│                                                                                              │
│  ┌────────────────────────────────────────────────────────────────┐                         │
│  │  system2-scenario    system3-procure    system4-spr            │                         │
│  │  (ARIO + GNN/GPU)    (OR-Tools + RF)    (SDP/CMDP NumPy)       │                         │
│  └────────────────────────────────────────────────────────────────┘                         │
│                                                                                              │
│  ┌──────────────────┐  ┌──────────────────────────────────────────┐                         │
│  │   api-gateway    │  │            frontend (nginx)              │                         │
│  │   FastAPI + WS   │  │  React + deck.gl (pre-built static)      │                         │
│  │   port 8000 ───────────────────────────────── port 80/443     │                         │
│  └──────────────────┘  └──────────────────────────────────────────┘                         │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Container Specs

| Container | System | RAM | GPU | Notes |
|---|---|---|---|---|
| `falkordb` | KB backend | 512 MB | — | Official FalkorDB image. Persists to separate EBS. Port 6379 (Bolt/Redis protocol). |
| `redis` | LangGraph checkpointing + signal queue | 256 MB | — | Internal only. All 4 System-1 agents write signals here. |
| `graphiti` | SAGE knowledge layer | 512 MB | — | `graphiti-core` Python service. Connects to FalkorDB via Bolt. Exposes internal HTTP API. |
| `sage-core` | SAGE pipeline | 1 GB | — | The most critical container. Triage, synthesis, sandbox fork, LangGraph monitor, all write orchestration. |
| `system1-ais` | AIS sensing | 256 MB | — | Persistent asyncio websocket to aisstream.io. H3 conversion + HABIT imputation inline. |
| `system1-news` | GDELT/news sensing | 256 MB | — | APScheduler, polls every 15 min. Nova Micro for entity extraction. |
| `system1-sanctions` | Sanctions diff | 128 MB | — | Polls every 6 hrs. OFAC/EU/UN diff. Always-on. |
| `system1-prices` | Commodity prices | 128 MB | — | Polls every 5 min. BOCD on every tick. yfinance + EIA. |
| `system2-scenario` | ARIO cascade + GNN | 2 GB | 1 GB VRAM | PyTorch loaded at startup, stays in GPU memory. ARIO is pure Python/NumPy. |
| `system3-procure` | Procurement orchestrator | 512 MB | — | OR-Tools + scikit-learn RF. Event-triggered by Scenario_Output node. |
| `system4-spr` | SPR SDP/CMDP solver | 256 MB | — | NumPy Bellman iteration. Event-triggered alongside System 3. |
| `api-gateway` | FastAPI + WebSocket | 512 MB | — | REST + WebSocket push to frontend. Port 8000 exposed. |
| `frontend` | React + deck.gl | 128 MB | — | Pre-built static files. nginx on port 80/443. |
| **Total** | | **~6.5 GB** | | Leaves ~9.5 GiB headroom in the 16 GiB instance for OS, Docker overhead, GNN inference spikes. |

### 3.2 Container Start Order

```
falkordb + redis   (start first — healthcheck)
       ↓
graphiti           (waits for falkordb healthy)
       ↓
sage-core          (waits for graphiti + redis)
       ↓
system1-*          (all 4 start together; share redis URL)
system2-scenario   (waits for sage-core)
system3-procure    (waits for sage-core)
system4-spr        (waits for sage-core)
       ↓
api-gateway        (waits for sage-core)
frontend           (waits for api-gateway)
```

### 3.3 Key Docker Compose Patterns

```yaml
# excerpt — key configuration decisions only
services:
  falkordb:
    image: falkordb/falkordb:latest
    volumes:
      - /var/lib/falkordb:/data   # separate EBS mount
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]

  sage-core:
    volumes:
      - wiki_data:/app/wiki       # /wiki persists across restarts
    env_file: .env
    depends_on:
      falkordb: { condition: service_healthy }
      redis:    { condition: service_healthy }

  system2-scenario:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  api-gateway:
    ports: ["8000:8000"]         # only this + frontend are host-exposed

volumes:
  wiki_data:                      # narrative synthesis pages persist here
```

---

## 4. Environment Variables — Full Reference

Store in `.env`, never commit to git. Docker Compose reads at boot.

```bash
# ── Bedrock (LLM) ─────────────────────────────────────────────────────────────
BEDROCK_REGION=ap-south-1
BEDROCK_MODEL_SYNTHESIS=amazon.nova-pro-v1:0      # narrative synthesis — quality critical
BEDROCK_MODEL_EXTRACTION=amazon.nova-micro-v1:0   # triage + entity extraction — volume critical
BEDROCK_MODEL_MEMO=amazon.nova-pro-v1:0           # System 3 rationale + System 4 policy memo

# ── Knowledge Base ─────────────────────────────────────────────────────────────
FALKORDB_HOST=falkordb                            # Docker service name
FALKORDB_PORT=6379
FALKORDB_USERNAME=                                # leave blank if no auth
FALKORDB_PASSWORD=<set a strong password>
FALKORDB_DATABASE=sage                            # must match GRAPH_NAME in connection.py

REDIS_URL=redis://redis:6379                      # LangGraph checkpointing + signal queue

# ── Sensing sub-agents ─────────────────────────────────────────────────────────
AISSTREAM_API_KEY=<from aisstream.io>
EIA_API_KEY=<from eia.gov>
NEWSAPI_KEY=<from newsapi.org>
# GDELT, OFAC, Sentinel-1, OSM — no key required (free)

# ── Demo mode ──────────────────────────────────────────────────────────────────
DEMO_MODE=false                                   # true on presentation day
DEMO_CACHE_PATH=./demo_cache/                     # pre-recorded signal replay path

# ── Safety ─────────────────────────────────────────────────────────────────────
CLOUDWATCH_ALARM_THRESHOLD=150                    # billing alarm in USD — set this before anything else
```

> **`DEMO_MODE=true`** switches all four sensing sub-agents from live feeds to JSON replay from `./demo_cache/`. Set it the night before the presentation and verify before leaving for the venue.

---

## 5. Data Sources

All free tier. No paid data licenses.

| Source | What you get | Access | Used by |
|---|---|---|---|
| [aisstream.io](https://aisstream.io) | Real-time global AIS, websocket | Free API key | System 1 AIS |
| [GDELT](https://www.gdeltproject.org) | Global event database, 15-min updates | Free (no key) | System 1 news |
| [NewsAPI](https://newsapi.org) | News headlines RSS | Free tier key | System 1 news |
| [EIA Open Data](https://www.eia.gov/opendata/) | Brent/WTI prices, SPR stocks, refinery utilization | Free API key | System 1 prices |
| [yfinance](https://github.com/ranaroussi/yfinance) | `BZ=F`, `CL=F` price series | Free Python library | System 1 prices |
| [OFAC SDN](https://ofac.treasury.gov/specially-designated-nationals-and-blocked-persons-list-sdn-human-readable-lists) / EU / UN | Sanctions registries (XML download) | Free public XML | System 1 sanctions |
| [ESA Sentinel-1 (Copernicus)](https://scihub.copernicus.eu) | SAR satellite imagery, 20m resolution | Free (Copernicus Hub) | System 1 AIS (dark-vessel fusion) |
| [PPAC](https://ppac.gov.in) | India crude imports by source, refinery processing | Free portal | Historical seeding |
| [ISPRL](https://isprl.gov.in) | India SPR: 5.33 MMT, Vizag/Mangaluru/Padur specs | Free public site | System 4 seed data |
| Natural Earth / OSM / GADM | Map geometry, ports, boundaries | Free | System 5 map |
| [World Port Index](https://msi.nga.mil/Publications/WPI) | Port coordinates, depths, facilities | Free (NGIA) | Port entity seeding |

---

## 6. Cost Breakdown

### 6.1 Cost per day

| Cost item | Daily cost | Notes |
|---|---|---|
| EC2 g4dn.xlarge (spot, weeks 1–3) | **~$5.76/day** | $0.24/hr × 24hr |
| EC2 g4dn.xlarge (on-demand, week 4) | **~$12.62/day** | $0.526/hr × 24hr |
| EBS — separate 20 GB gp3 (FalkorDB) | **~$0.053/day** | $0.08/GB/month → $1.60/month |
| S3 bucket (2 GB demo cache + backups) | **~$0.003/day** | ~$0.046/month |
| Bedrock Nova Micro — triage (5,000 calls/day, ~170 tokens) | **~$0.052/day** | $0.035/$0.14 per 1M tokens |
| Bedrock Nova Lite — entity extraction (600 calls/day, ~550 tokens) | **~$0.036/day** | $0.06/$0.24 per 1M tokens |
| Bedrock Nova Pro — synthesis (60 calls/day, ~1,200 tokens, 70% cache hit) | **~$0.034/day** | ~$0.115/day without cache |
| Bedrock Nova Pro — memos + copilot (55 calls/day, ~1,200 tokens) | **~$0.050/day** | Nova Pro + Nova Lite mix |
| Bedrock Titan Embeddings V2 (600 entities/day, ~200 tokens) | **~$0.002/day** | $0.00002/1K tokens |
| DNS / SSL | **~$0.033/day** | ~$1/month, Route 53 optional |
| **Total (dev, spot EC2, weeks 1–3)** | **~$5.96/day** | |
| **Total (demo week, on-demand EC2)** | **~$12.86/day** | |

### 6.2 Four-week total

| Item | 4-week total |
|---|---|
| EC2 (spot weeks 1–3 + on-demand week 4) | ~$160 |
| EBS 20 GB gp3 separate volume | ~$1.60 |
| S3 bucket (demo cache + backups, ~2 GB) | ~$0.05 |
| Bedrock LLM (Nova Micro + Lite + Pro, with caching) | ~$8 |
| Bedrock Embeddings (Titan Text V2) | ~$1 |
| Data sources | $0 (all free) |
| DNS / SSL | ~$1 |
| Buffer (dev testing, agent loop overruns) | ~$25 |
| **Total** | **~$197** |
| AWS new account credits | −$200 |
| **Effective total (new account)** | **~$0** |

### 6.3 Cost control rules

1. **Set the CloudWatch billing alarm at $150 before anything else.** A runaway LangGraph loop making thousands of Nova Pro calls can burn $500 in minutes.
2. **Enable Bedrock prompt caching for Nova Pro synthesis.** The system prompt + current entity wiki page is identical on repeated calls for the same entity → ~70% cache hit rate after warm-up → 70% cost reduction on synthesis (the dominant LLM call).
3. **Nova Micro for triage, Nova Pro only for synthesis.** Triage is 5,000 calls/day; paying Nova Pro rates would cost ~$10/day for triage alone.
4. **Spot instance for weeks 1–3.** LangGraph checkpoints to Redis — the pipeline resumes from the last state on spot interruption. Switch to on-demand one week before demo day.
5. **`DEMO_MODE=true` disables all live sensing.** No API calls, no Bedrock calls, no cost during the presentation itself.

---

## 7. The Knowledge Base Boot Sequence

What happens from `docker compose up` to a fully operational KB:

```
T+0s    falkordb + redis containers start
T+5s    healthchecks pass; graphiti container starts
T+10s   graphiti connects to FalkorDB (bolt://falkordb:6379, database='sage')
T+12s   graphiti runs build_indices_and_constraints() — idempotent, safe to repeat
T+15s   sage-core starts; loads ENTITY_TYPES + EDGE_TYPES + EDGE_TYPE_MAP from schema/
T+18s   sage-core runs seed_episode() — one episode per edge type to prime extraction
T+20s   sage-core initialises LangGraph state machine; threshold monitor starts polling every 30s
T+22s   system1-* containers start; sub-agents begin emitting NormalizedSignals to Redis queue
T+25s   system2/3/4 containers start; await trigger events from sage-core
T+30s   api-gateway starts; WebSocket endpoint ready
T+35s   frontend served; map loads from Graphiti entity nodes
```

After boot, the system is fully autonomous — no human action required to begin watching signals.

---

## 8. The Three Knowledge Stores — How They Fit Together

The "three-store system" referred to in the project plan:

```
                    NormalizedSignal
                          │
                    SAGE ingest_signal()
                          │
              ┌───────────┴───────────┐
              │      Triage gate      │
              │  (embedding similarity)│
              └───────────┬───────────┘
                          │
            ┌─────────────▼────────────────┐
            │   SAGE Narrative Synthesis    │
            │   (Nova Pro, LLM wiki agent)  │
            └─────────────┬────────────────┘
                          │ synthesized text
           ┌──────────────┼──────────────────┐
           ▼              ▼                  ▼
    ┌─────────────┐ ┌──────────────┐ ┌──────────────────┐
    │  /wiki      │ │  Graphiti    │ │  Graphiti        │
    │  Store      │ │  Episodic    │ │  Semantic Entity │
    │             │ │  Subgraph    │ │  Subgraph        │
    │  Canonical  │ │              │ │  + Embeddings    │
    │  prose page │ │  Every raw   │ │                  │
    │  per entity │ │  episode,    │ │  Typed nodes,    │
    │  (Markdown, │ │  non-lossy,  │ │  edges, validity │
    │  git-ver'd) │ │  with prov-  │ │  windows, 1024D  │
    │             │ │  enance      │ │  vectors, BM25   │
    └─────────────┘ └──────────────┘ └──────────────────┘
         Store 1         Store 2            Store 3
      (you build)    (Graphiti/FalkorDB) (Graphiti/FalkorDB)
```

| Store | What it is | Who owns it | Where it lives |
|---|---|---|---|
| **Store 1 — `/wiki`** | One Markdown file per entity. The reconciled, human-readable intelligence page for that entity. Git-versioned history. | SAGE coordination layer (you build) | Docker named volume on root EBS; `sage-core` container writes it |
| **Store 2 — Episodic subgraph** | Every synthesized episode node, non-lossy, with `MENTIONS` edges back to extracted entities. Ground-truth provenance. | Graphiti (composed, not built) | FalkorDB on separate EBS |
| **Store 3 — Semantic entity subgraph** | Typed entity nodes (`Corridor`, `Supplier`, etc.), typed edges (`RISK_STATE`, `EXPORTS_VIA`, etc.), validity windows (bitemporal), 1024-D embeddings for hybrid search. | Graphiti (composed, not built) | FalkorDB on separate EBS |

**Why three stores and not one:** the `/wiki` store gives you human-editable pages with full git history and a clean source for decision-memo assembly — Graphiti has no equivalent concept. The episodic store is non-lossy ground truth. The semantic store is the reasoning substrate. Each does something the others cannot.

**Single write path rule:** SAGE's `ingest_signal()` writes to all three in sequence, in one function. The `/wiki` page is written first, then the synthesized text (which includes the wiki content) is passed to `add_episode()` which updates the other two. No consumer ever writes directly to any store — they call the SAGE write API.

---

## 9. Day-One Validation Checklist

Run these before writing any application code. If any fail, fix before proceeding — a FalkorDB or Bedrock connectivity issue discovered in Week 3 is fatal.

- [ ] AWS account active; CloudWatch billing alarm set at $150
- [ ] EC2 `g4dn.xlarge` launched in `ap-south-1` with 30 GB root EBS + 20 GB separate EBS for FalkorDB
- [ ] Security group: inbound 22 (SSH), 80 (HTTP), 8000 (API), 443 (HTTPS). All other ports closed.
- [ ] Docker + Docker Compose installed; NVIDIA Container Toolkit installed for GPU access
- [ ] FalkorDB container running: `docker run -p 6379:6379 falkordb/falkordb:latest`
- [ ] Graphiti connects: `python3 -c "from graphiti_core import Graphiti; print('OK')"`
- [ ] FalkorDriver connects with `database='sage'`: smoke-test `build_indices_and_constraints()` completes
- [ ] Bedrock Nova Lite accessible: `aws bedrock invoke-model --model-id amazon.nova-lite-v1:0 --region ap-south-1 ...`
- [ ] `AISSTREAM_API_KEY` validated: websocket connection opens and receives position messages
- [ ] `EIA_API_KEY` validated: `curl 'https://api.eia.gov/v2/petroleum/pri/spt/data/?api_key=YOUR_KEY'`
- [ ] GDELT accessible: `curl 'http://data.gdeltproject.org/gdeltv2/lastupdate.txt'`
- [ ] All environment variables in `.env`; Docker Compose reads them correctly
- [ ] End-to-end smoke test: Reuters article about Hormuz → triage → synthesis → `graphiti.add_episode()` → entity visible in FalkorDB browser at `:3000` → `RISK_STATE` edge queryable → `/wiki` page written

---

## 10. Demo Day Configuration

One week before presentation, switch to on-demand and enable demo mode.

1. Stop spot instance. Launch on-demand `g4dn.xlarge` in same AZ. Attach the FalkorDB EBS volume.
2. Set `DEMO_MODE=true` in `.env`. Verify all sensing agents switch to replay from `./demo_cache/`.
3. Pre-populate demo cache: record one full golden-path run (Feb 23–28 Hormuz signal sequence) as JSON snapshots at each pipeline stage.
4. Verify GNN surrogate loaded in GPU memory at startup. Run 10 inference calls: confirm <150ms latency.
5. Run golden-path demo end-to-end three times. Measure and record the 300ms (pre-staged) vs 8,500ms (cold) numbers — these are headline demo metrics.
6. Have demo video recorded on local machine as backup.
7. Test on the presentation laptop, not the development machine.
8. Final check: CloudWatch shows no billing anomalies. Bedrock quota not hit. FalkorDB browser (`:3000`) shows expected entity graph.

---

## 11. Post-Hackathon Scaling Path

The hackathon runs everything on one server. Post-hackathon, the architecture scales to distributed without code changes — only infrastructure changes:

| Component | Single-host (hackathon) | Distributed (production) |
|---|---|---|
| FalkorDB | Docker container on EC2 | FalkorDB Cloud or dedicated instance |
| Redis | Docker container | ElastiCache |
| SAGE core | Single container | Multiple replicas behind ALB |
| System 1 sub-agents | 4 containers on one host | Independent ECS tasks or Lambda |
| Bedrock | Same | Same — already a managed service |
| Frontend | nginx on EC2 | S3 + CloudFront |
| Secrets | `.env` file | AWS Secrets Manager |
