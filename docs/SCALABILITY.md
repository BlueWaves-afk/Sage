# SAGE — Scalability

Three axes, honestly scoped: what runs live today, and the documented path beyond it.

## 1. Multi-tenancy — new economy = config swap (LIVE)

SAGE's worldview ships as a portable `.context` bundle. A second import-dependent
economy is instantiated from the **same engine, zero code changes** — only the bundle
and three env vars differ.

- `data/india-energy-2026.context` → graph `sage`, port 80
- `data/japan-energy-2026.context` → graph `sage_jp`, port 8001 (`docker-compose.japan.yml`)

Both tenants share one FalkorDB (isolated named graphs) and one Redis (isolated DB).

```bash
docker compose -f docker-compose.yml -f docker-compose.japan.yml up -d sage-core-jp api-gateway-jp
docker compose -f docker-compose.yml -f docker-compose.japan.yml exec -T sage-core-jp \
  python scripts/sage_instantiate.py data/japan-energy-2026.context --facts-only
curl http://<host>:8001/api/dashboard   # Japan KPIs (METI/JOGMEC/ENEOS), distinct from :80 India
```

## 2. Horizontal agent scaling — the stateless tier (LIVE)

Sensory agents are **stateless**: their only output is a `NormalizedSignal` pushed onto
the Redis signal bus. That's the sole coupling to the knowledge base, so agents replicate
freely — more workers = higher signal throughput, no shared state to contend on.

```bash
docker compose --profile sensory up -d --scale sensory-news=3 --scale sensory-ais=3
```

During a geopolitical spike, signal volume surges; adding workers keeps **signal→ingest
lead time flat** instead of letting the queue back up.

## 3. Kubernetes scale-out — the design (ARCHITECTURE DELIVERABLE)

`deploy/k8s/sensory-scale.yaml` is a valid Deployment + HorizontalPodAutoscaler that
scales the sensory tier 2→10 on CPU pressure. It is documented as the cloud-native path
(applies to EKS/GKE/k3s with metrics-server); the hackathon demo runs on docker-compose.
The stateful cores — FalkorDB and Redis — scale vertically or via managed services
(ElastiCache, a FalkorDB cluster), the standard stateful-tier pattern.

## What is *not* horizontally scalable (and why that's fine)

- **FalkorDB** (the knowledge graph) is the single source of truth — it scales vertically
  and via replicas for reads, not by naive sharding. This is deliberate: graph traversals
  (System 2's cascade) need a coherent view.
- The demo runs on a single 8 GB node. We tuned it for stability under the full 12-service
  load: a bounded FalkorDB write semaphore + `MAXQUEUED 500` to prevent query-queue
  saturation (see `knowledge/api/write.py`, `docker-compose.yml`).

## Operational efficiency (real, measured)

Scalability isn't only throughput — it's cost per unit of intelligence. We cut Bedrock
LLM spend **~95%** (from a $55/day peak to a few $/day) by: routing Graphiti's internal
extraction to Nova Lite, skipping redundant entity-extraction on deterministic writes
(risk states, System 2/3/4 outputs), and a per-entity synthesis cooldown. The system gets
*cheaper per tenant* as it scales, not more expensive.
