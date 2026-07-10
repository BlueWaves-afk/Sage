# SAGE — AWS EC2 Deployment Guide

Single-instance Docker Compose deployment. All services co-located; scale out later
without code changes.

## 1. Instance sizing

The full stack is **CPU-only** (no GPU needed — the System 2 "GNN surrogate" runs the
ARIO-analytic path at ~20 ms; PyTorch is a CPU build isolated to the scenario agent).

| Instance | vCPU / RAM | Runs |
|---|---|---|
| **t3.medium** | 2 / **4 GiB** | **Full hackathon system** — core (5) + the 4 live System-1 sensory agents (~2.3–2.7 GiB). Systems 2/3/4 run **in-process** inside sage-core when the pipeline fires (ARIO-analytic, no torch loaded). Skip the always-on `agents` profile. |
| **t3.large** | 2 / 8 GiB | Comfortable headroom + the always-on Systems 2/3/4 agent containers (`--profile agents`) if you want them separate. |
| **t3.xlarge** | 4 / 16 GiB | Matches the plan's ~6.5 GiB estimate; needed only if you add the CPU-torch scenario container or GPU work. |

> **A 4 GiB t3.medium runs the whole live demo.** The sensory containers are light
> (~150–250 MiB each — no torch/transformers in their images; news tone degrades to
> keyword-based). Systems 2/3/4 execute inside the pipeline, not as always-on containers.
> Cheaper still: **t3.medium spot** (~70% off), **t4g.medium** (ARM, ~20% off), AWS
> Lightsail 4 GiB ($24/mo flat), or just run `docker compose up` on the demo laptop.

Storage: 30 GB gp3 root is plenty; FalkorDB persists to `./knowledge/graph_store`
(bind-mounted). Security group inbound: 22 (SSH), 80 (frontend), 8000 (API),
3000 (FalkorDB browser, optional).

## 2. Prerequisites

```bash
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER    # re-login after this
git clone <repo> && cd Sage
cp .env.example .env             # edit LLM_PROVIDER + AWS_* / OPENAI_*
#  Put the 3 free sensory keys (aisstream/EIA/newsdata) in .env.local (gitignored):
cat > .env.local <<'EOF'
AISSTREAM_API_KEY=...
EIA_API_KEY=...
NEWSDATA_API_KEY=...
EOF
```

Set `FALKORDB_HOST=falkordb` and `REDIS_URL=redis://redis:6379/0` in `.env`
(the in-cluster hostnames — already the defaults).

## 3. Bring it up

Compose uses **profiles** so you choose how much runs:

```bash
# Lean core (fits t3.medium): datastores + KB core + API + UI
docker compose up -d --build          # falkordb, redis, sage-core, api-gateway, frontend

# + live System 1 sensing (needs t3.large+)
docker compose --profile sensory up -d --build

# + Systems 2/3/4 always-on agent containers (needs t3.xlarge)
docker compose --profile sensory --profile agents up -d --build
```

Health check:
```bash
curl -s localhost:8000/health         # {"status":"ok","kb_ready":true}
docker compose ps                     # all healthy
```

## 4. Instantiate the knowledge base (first boot)

The graph store is empty on a fresh volume. Instantiate the sourced `.context`
bundle — this loads the 61 real, cited entities + edges + params (no fabricated
data):

```bash
docker compose exec sage-core python -m scripts.seed_kb
# or from host with the stack up:
PYTHONPATH=. FALKORDB_HOST=localhost REDIS_URL=redis://localhost:6380/0 \
  python3.11 scripts/seed_kb.py
```

Then start System 1 so real signals flow in and the KB computes risk on its own:

```bash
docker compose --profile sensory up -d
```

Open `http://<ec2-ip>/` — the Command Center reads live from the KB. Risk reflects
**reality**: it stays LOW/CALM when the feeds are quiet and rises autonomously only
when real signals (news / AIS / sanctions / price) warrant it — Systems 2/3/4 fire
on a genuine threshold crossing. Nothing is seeded, authored, or hardcoded.

> Optional manual poll: `python3.11 scripts/seed_from_live.py` pulls one batch of
> real signals immediately instead of waiting for the agents' intervals. It is
> **not required** — the running agents do this continuously.

## 5. Ports

| Port | Service |
|---|---|
| 80 | Frontend (nginx → SPA, proxies /api + /ws to gateway) |
| 8000 | API gateway (REST + WebSocket) |
| 3000 | FalkorDB browser (optional — inspect the graph) |
| 6379 / 6380 | FalkorDB / Redis (internal; exposed for host debugging) |

## 6. DEMO_MODE (offline replay)

Set `DEMO_MODE=true` in `.env` to run the presentation offline from pre-recorded
signals instead of hitting live feeds. *(Fixture replay path is tracked — see the
volatile-refresh tasks; live feeds work today with the keys above.)*

## 7. Notes

- **Bedrock region**: `.env` uses `AWS_REGION`. Confirm Nova Pro/Lite are enabled in
  that region for your account (the plan targets `ap-south-1`; `us-east-1` also works).
- **Secrets**: `.env` and `.env.local` are gitignored. Never bake keys into an image.
- **Persistence**: stop/restart is safe — FalkorDB data and the `/wiki` volume persist.
