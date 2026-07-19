#!/usr/bin/env bash
#
# deploy_gemini.sh — cut SAGE over from AWS Bedrock to free-tier Google Gemini.
#
# Run ON THE EC2 BOX:
#   cd /home/ubuntu/sage && bash scripts/deploy_gemini.sh
#
# Prereq: add your Gemini key to /home/ubuntu/sage/.env.local as:
#   GOOGLE_API_KEY=<your key from https://aistudio.google.com/apikey>
#
# What it does:
#   1. git pull (brings the LLM_PROVIDER=gemini code)
#   2. sets LLM_PROVIDER=gemini in .env.local (overrides .env's bedrock)
#   3. rebuilds sage-core + api-gateway (adds the google-genai SDK)
#   4. WIPES the graph — required, because the embedding dimension changes
#      (Titan 1024-d -> Gemini text-embedding-004 768-d); mixed dims break search
#   5. re-seeds the context bundle under Gemini (facts phase: structured graph +
#      768-d embeddings, deterministic, no LLM rate-limit risk). Narrative prose
#      then fills in over time from the live pipeline.
#   6. restarts and prints verification
set -euo pipefail

cd "$(dirname "$0")/.."          # repo root
ROOT="$(pwd)"
echo "==> repo: $ROOT"

# ── 0. preconditions ─────────────────────────────────────────────────────────
if ! grep -q '^GOOGLE_API_KEY=' .env.local 2>/dev/null; then
  echo "ERROR: GOOGLE_API_KEY is not set in .env.local"
  echo "       Add this line to $ROOT/.env.local, then re-run:"
  echo "         GOOGLE_API_KEY=<your key from https://aistudio.google.com/apikey>"
  exit 1
fi

# ── 1. pull the Gemini code ──────────────────────────────────────────────────
echo "==> git pull"
git pull --ff-only

# ── 3. rebuild the two images that import knowledge/ (need google-genai) ─────
echo "==> rebuild sage-core + api-gateway (installs google-genai)"
docker compose build sage-core api-gateway

# ── 3b. PRE-FLIGHT: validate the Gemini key BEFORE any destructive step ──────
# If the key is bad or google-genai is broken, abort here — the old graph and the
# working Bedrock setup are left untouched, so the live demo never breaks.
echo "==> validating Gemini key + embeddings (no changes yet)"
GKEY="$(grep '^GOOGLE_API_KEY=' .env.local | head -1 | cut -d= -f2- | tr -d '"'\'' ')"
docker compose run --rm --no-deps -T \
  -e GKEY="$GKEY" sage-core python -c "
import os
from google import genai
c = genai.Client(api_key=os.environ['GKEY'])
r = c.models.embed_content(model='text-embedding-004', contents='sage preflight')
emb = getattr(r, 'embeddings', None)
if emb is None:
    emb = getattr(r, 'embedding', None)
first = emb[0] if isinstance(emb, (list, tuple)) else emb
vals = getattr(first, 'values', first)
assert vals and len(vals) > 100, 'empty embedding'
print('GEMINI_PREFLIGHT_OK dim=%d' % len(vals))
" || { echo 'GEMINI_PREFLIGHT_FAILED — aborting, graph + Bedrock left intact'; exit 2; }

# ── 3c. pre-flight passed → NOW flip provider (point of no easy return) ──────
echo "==> set LLM_PROVIDER=gemini in .env.local"
if grep -q '^LLM_PROVIDER=' .env.local; then
  sed -i 's/^LLM_PROVIDER=.*/LLM_PROVIDER=gemini/' .env.local
else
  echo 'LLM_PROVIDER=gemini' >> .env.local
fi

# ── 4. wipe the old Titan-dimension graph ────────────────────────────────────
echo "==> start infra + FLUSHALL FalkorDB (drop old 1024-d embeddings)"
docker compose up -d falkordb redis
until docker compose exec -T falkordb redis-cli ping | grep -q PONG; do sleep 2; done
docker compose exec -T falkordb redis-cli FLUSHALL

# ── 5. bring up core, then re-seed the bundle under Gemini ───────────────────
echo "==> start sage-core + api-gateway"
docker compose up -d sage-core api-gateway
sleep 8
echo "==> re-seed context bundle (facts phase) under Gemini embeddings"
docker compose exec -T sage-core python scripts/sage_instantiate.py \
  data/india-energy-2026.context --facts-only

# ── 6. restart so every consumer picks up the fresh graph + provider ─────────
echo "==> restart sage-core + api-gateway"
docker compose restart sage-core api-gateway

echo ""
echo "==> DONE. Verify with:"
echo "    docker compose exec -T sage-core python -c \"import os;os.environ['LLM_PROVIDER']='gemini';from knowledge.bedrock import _AWS_REGION;from graphiti_core.llm_client.gemini_client import GeminiClient;print('gemini import OK')\""
echo "    docker logs sage-sage-core-1 --since 3m 2>&1 | grep -iE 'LLM_PROVIDER|gemini|error|traceback' | tail"
echo "    curl -s http://localhost/api/graph | python3 -c 'import json,sys;d=json.load(sys.stdin);print(\"nodes\",len(d[\"nodes\"]),\"edges\",len(d[\"edges\"]))'"
echo "    # then open http://44.213.136.64/  — feed should populate as Gemini synthesizes"
