# CLAUDE.md — SAGE Project Rules

This file is read by Claude Code at the start of every session. Follow every rule here without exception. When in doubt, re-read the relevant section before acting.

---

## 1. Project Identity

**SAGE** = Synthesis-first Agentic Graph-Enhanced knowledge architecture.
**Problem:** ET AI Hackathon 2.0, Problem Statement 2 — AI-Driven Energy Supply Chain Resilience (India crude import vulnerability, Hormuz chokepoint).
**Stack:** Python 3.11+, Pydantic v2, Graphiti + FalkorDB, LangGraph, AWS Bedrock Nova, React + deck.gl.
**Design specs:** `.claude/design/` — read these before touching any interface or contract.

---

## 2. The Non-Negotiable Structural Rules

### 2.1 Import boundaries — enforce strictly

```
contracts/          ← imports nothing from this project
knowledge/          ← imports contracts/ only
orchestration/      ← imports contracts/ and knowledge/api/ only
sensory_agent/      ← imports contracts/ only (writes signals, reads nothing from KB directly)
scenario_agent/     ← imports contracts/ and knowledge/api/ only
alt_procurement_agent/ ← imports contracts/ and knowledge/api/ only
reserve_optim_agent/   ← imports contracts/ and knowledge/api/ only
visualizer_agent/   ← imports contracts/ and knowledge/api/ only
```

**Never** import `graphiti_core` outside of `knowledge/`. If you need graph data in any other module, add a function to `knowledge/api/read.py` and call that.

**Never** import from one agent package into another (e.g. `scenario_agent` must not import from `sensory_agent`). Agents communicate only through the knowledge base and Redis events.

### 2.2 The single write-path rule

Raw signals from `sensory_agent` are **never** passed to `graphiti.add_episode()` directly. The only path to Graphiti is:

```
NormalizedSignal → knowledge/api/write.py:ingest_signal() → triage → synthesis → add_episode()
```

Synthesized episodes only. This is why embeddings capture reconciled understanding, not raw noise.

### 2.3 The RISK_STATE isolation rule

A `PendingScenario`'s projected risk score must **never** be written as a `RISK_STATE` edge on a live entity node. Speculative outputs are stored only on `PendingScenario` nodes and linked output episodes. Violating this makes the LangGraph monitor fire on a future that hasn't happened.

### 2.4 Contracts are frozen after Week-1 sign-off

The `RISK_STATE` edge field names (`score`, `band`, `factor_ais`, `factor_gdelt`, `factor_price`, `factor_sanctions`) are **frozen** once signed off. Any change to these breaks the monitor, the UI colour bands, the scenario trigger, and the sandbox simultaneously. Treat them like a public API — bump `schema_version` and get team sign-off before touching.

---

## 3. Python Conventions

### 3.1 Style
- **Python 3.11+**. Use `from __future__ import annotations` at the top of every file.
- **Pydantic v2** throughout. Models use `BaseModel`; pass **classes** (not instances) to `entity_types` / `edge_types` in Graphiti calls.
- Line length: **100 characters** (configured in `pyproject.toml` via ruff).
- All async I/O uses `async def` / `await`. No blocking calls inside async functions.
- Type-annotate every function signature. Return types are not optional.

### 3.2 Field naming in Pydantic models
- Units belong in the field name: `throughput_mbpd`, `capacity_mmt`, `added_days`. A bare `capacity` is rejected.
- Scores are `float`, normalized `0.0–1.0`, with the range stated in `Field(description=...)`.
- All custom entity/edge attributes must be `Optional[...] = Field(None, ...)` unless they are definitionally always present — required fields without defaults cause Graphiti extraction failures.
- **Banned field names** (reserved by Graphiti internals): `uuid`, `name`, `group_id`, `labels`, `created_at`, `summary`, `attributes`, `name_embedding`. Use `event_time` not `created_at`; `display_name` not `name`.

### 3.3 Docstrings and Field descriptions
Graphiti feeds entity/edge docstrings and `Field(description=...)` to the extraction LLM verbatim. Write them as instructions to a smart analyst:
- State what the entity IS and what it is NOT (e.g. "NOT a port and NOT a country").
- Include a disambiguating example (e.g. "e.g. 'Strait of Hormuz', 'Bab-el-Mandeb'").
- State units and ranges in descriptions.

### 3.4 Error handling
- Stubs raise `NotImplementedError` with a one-line description of what needs implementing.
- Production functions raise typed domain exceptions, never bare `Exception`.
- Never swallow exceptions silently. Log + re-raise or return a typed error result.

### 3.5 No dead imports
Remove unused imports immediately. Ruff enforces this — run `ruff check .` before committing.

---

## 4. Graphiti-Specific Rules

- **Connection:** always use `FalkorDriver(database='sage')` passed as `graph_driver=` to `Graphiti()`. Never use the legacy `uri=` / `graph_name=` form. The database name `"sage"` must never be `None` — a `None` database silently falls back to `default_db` and splits your graph.
- **Bootstrap:** call `build_indices_and_constraints()` on every container start. It is idempotent.
- **Episode writes:** pass `ENTITY_TYPES`, `EDGE_TYPES`, `EDGE_TYPE_MAP` from `knowledge/schema/` on every `add_episode()` call.
- **Seed on first boot:** run a seed episode that exercises every edge type once to work around Graphiti issue #1111 (custom edge attributes don't extract on first appearance).
- **Bulk ingest:** only use `add_episode_bulk()` for the initial empty-graph backfill. Live updates always use `add_episode()` — bulk skips edge invalidation.
- **Reference time:** always pass `reference_time=signal.observed_at` (when true in world), not `datetime.now()`.

---

## 5. LangGraph / Orchestration Rules

- The LangGraph monitor polls `get_risk_scores()` every 30 seconds. Do not change this interval without updating the deployment doc.
- Band thresholds live **only** in `contracts/bands.py`. Never hardcode `0.7` or `0.45` anywhere else.
- LangGraph state is checkpointed to Redis. Every node must be idempotent — if the container restarts mid-pipeline, re-running the node must produce the same result.
- The sandbox fork runs **parallel** to the synthesis branch, not sequential. Never await the sandbox inside the main synthesis path.

---

## 6. Cost and Model Routing

Follow the Bedrock model routing defined in the deployment spec. Do not upgrade to a more expensive model without justification:

| Task | Model |
|---|---|
| Triage classification | `amazon.nova-micro-v1:0` |
| Entity extraction (Graphiti) | `amazon.nova-micro-v1:0` |
| Narrative synthesis | `amazon.nova-pro-v1:0` |
| Policy memos, procurement rationale | `amazon.nova-pro-v1:0` |
| Copilot (simple queries) | `amazon.nova-lite-v1:0` |
| Embeddings | `amazon.titan-embed-text-v2:0` |

Enable Bedrock prompt caching on all Nova Pro synthesis calls. The system prompt + current entity page is identical on repeated calls for the same entity — expect ~70% cache hit rate after warm-up.

**Always check `CLOUDWATCH_ALARM_THRESHOLD` is set to 150 USD before running any agent loop.**

---

## 7. Git and PR Conventions

- **Branch naming:** `feat/<system>/<short-description>` or `fix/<system>/<short-description>`. System names: `knowledge`, `orchestration`, `sensory`, `scenario`, `procurement`, `reserve`, `visualizer`.
- **Commit messages:** imperative mood, present tense. First line ≤72 chars. Body explains the *why*, not the what.
- **Never commit:** `.env`, model weights (`gnn/weights/*.pt`), `demo_cache/` content, `__pycache__/`, `.pyc` files.
- **Before pushing:** run `ruff check .` and `ruff format --check .`. Fix all errors.
- **Breaking contract changes** (any edit to `contracts/`, `knowledge/schema/`, or the `RISK_STATE` field names in `knowledge/schema/edges.py`): require a bump to `schema_version` in `knowledge/connection.py` and a comment in the commit body naming which consumers are affected.

---

## 8. Testing Conventions

- Tests live in `tests/<module_name>/test_<file>.py` mirroring the source structure.
- Use `pytest` + `pytest-asyncio`. Mark async tests with `@pytest.mark.asyncio`.
- The Day-4 smoke test (`tests/integration/test_smoke.py`) is the Week-1 gate: ingest a real Hormuz signal → verify `RISK_STATE` edge is queryable → verify `/wiki` page is written. It must pass before any teammate starts Week-2 parallel builds.
- Never mock the Graphiti/FalkorDB layer in integration tests. Use a real FalkorDB container (spin up via `docker compose up falkordb -d` in CI).
- Unit tests may mock `knowledge/api/read.py` and `knowledge/api/write.py` — never deeper.

---

## 9. Demo Mode

When `DEMO_MODE=true`:
- All four sensory sub-agents read from `demo_cache/` instead of live feeds.
- No Bedrock calls are made during the presentation itself — all synthesis outputs are pre-cached.
- `DEMO_MODE` is read at startup; changing it requires a container restart.
- Never set `DEMO_MODE=true` in a development environment — it will silently hide real signal processing bugs.

---

## 10. What NOT to Do

- Do not add error handling or validation for scenarios that cannot happen. Trust internal contracts.
- Do not add features, abstractions, or helper utilities beyond what the current task requires.
- Do not rename contract fields without a `schema_version` bump and team sign-off.
- Do not add a new dependency to `pyproject.toml` without checking it is available in the `ap-south-1` region for the EC2 `g4dn.xlarge` image and does not conflict with the GPU PyTorch build.
- Do not write comments that explain WHAT the code does — well-named identifiers already do that. Only add a comment when the WHY is non-obvious.
- Do not use `add_episode_bulk()` for live signal ingestion.
- Do not write to `/wiki` from anywhere other than `knowledge/synthesis.py`.
