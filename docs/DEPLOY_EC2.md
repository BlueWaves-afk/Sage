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

Storage: 30 GB gp3 root is plenty; FalkorDB persists to `./knowledge/graph_store`,
Redis (AOF) to `./knowledge/redis_store`, and the feedback/scenario-outcome
ledgers to `./demo_cache` — all bind-mounted so `docker compose down`/rebuild
never silently discards state.

**Security group (production-facing instance):**

| Port | Source | Purpose |
|---|---|---|
| 80 (or 443 if fronted by TLS) | `0.0.0.0/0` | Frontend — the only port the public should reach |
| 22 | your IP only | SSH |
| 8000, 3000 | **not public** | API gateway and the unauthenticated FalkorDB browser. nginx already proxies `/api` and `/ws` to 8000 internally — there's no reason to expose it directly. If you need to debug them remotely, restrict to your IP or use an SSH tunnel instead of an open SG rule. |

No TLS is configured in `docker/nginx.conf` (plain HTTP on :80). For a bare
IP demo that's an accepted tradeoff; for a real domain, put an ALB with an ACM
cert in front (target group → instance:80) or run Caddy/certbot on the box.

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
data). `sage_instantiate.py` LLM-authors a rich narrative wiki page per entity by
default (Nova Pro); pass `--no-llm-author` for deterministic stubs, or
`--facts-only` to skip narratives entirely:

```bash
docker compose exec sage-core python -m scripts.sage_instantiate
# or from host with the stack up:
PYTHONPATH=. FALKORDB_HOST=localhost REDIS_URL=redis://localhost:6380/0 \
  LLM_PROVIDER=bedrock python3.11 scripts/sage_instantiate.py
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
- **Bedrock auth**: attach an IAM instance role with `bedrock:InvokeModel*`
  instead of putting `AWS_ACCESS_KEY_ID`/`SECRET` in `.env` — boto3 picks up
  instance-metadata credentials automatically when those are left blank. No
  static keys to leak, rotate, or accidentally commit.
- **CORS**: set `CORS_ALLOWED_ORIGINS` in `.env` to your actual domain once
  you have one (defaults to `*`, fine for same-origin nginx setups).
- **Secrets**: `.env` and `.env.local` are gitignored. Never bake keys into an image.
- **Persistence**: `docker compose down`/rebuild is safe — FalkorDB
  (`knowledge/graph_store`), Redis AOF (`knowledge/redis_store`), the `/wiki`
  volume, and the feedback/scenario-outcome ledgers (`demo_cache/`) are all
  bind-mounted to the host and survive container recreation.
- **Log rotation**: all services cap json-file logs at 10MB × 3 files — the
  instance disk won't fill up from unbounded container logs.
- **Backups**: nothing is scheduled automatically. Minimum viable backup for a
  demo instance — an EBS snapshot covers everything at once since all state
  lives under bind-mounts on the root volume:
  ```bash
  aws ec2 create-snapshot --volume-id <root-vol-id> --description "sage-backup-$(date +%F)"
  ```
  For finer-grained recovery, `redis-cli -p 6380 BGSAVE` + `tar` of
  `knowledge/graph_store` and `demo_cache/` to S3 on a cron works too.
- **Building on the instance vs. ECR**: `docker compose up -d --build` compiles
  `graphiti-core`, `numpy`, `scikit-learn`, `shap` from scratch on 2 vCPUs —
  workable but slow (~10+ min cold). For repeat deploys, build locally/in CI and
  push to ECR instead:
  ```bash
  aws ecr create-repository --repository-name sage-api-gateway
  aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com
  docker build -f docker/api_gateway.Dockerfile -t <account>.dkr.ecr.<region>.amazonaws.com/sage-api-gateway:latest .
  docker push <account>.dkr.ecr.<region>.amazonaws.com/sage-api-gateway:latest
  ```
  then point `docker-compose.yml`'s `image:` at the ECR URI (drop `build:`) on
  the instance and use `docker compose pull && docker compose up -d`.
