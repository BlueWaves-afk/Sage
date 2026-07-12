# Contributing to SAGE

Thank you for your interest in SAGE. This document covers how to get involved.

## Ways to contribute

- **Bug reports** — open an issue with steps to reproduce, expected vs. actual behaviour, and the relevant log output from `docker compose logs sage-core`.
- **Data corrections** — the context bundle (`data/india-energy-2026.context/`) accepts PRs that correct sourced values. Every row must cite a source from `manifest.yaml`; new sources must be added there first.
- **New context bundles** — a minimal 10-entity bundle for a different region (e.g. `japan-energy.context`) is welcome. See `data/india-energy-2026.context/manifest.yaml` for the schema.
- **Agent improvements** — ARIO coefficients, TOPSIS criterion weights, and Bellman SDP constants are all in `params/`; they accept evidence-backed PRs.
- **Frontend / UX** — the React frontend lives in `visualizer_agent/frontend/src/`; `npm run dev` spins up a local dev server against the live API.

## Development setup

```bash
cp .env.example .env          # fill in keys; LLM_PROVIDER=stub works without Bedrock
docker compose up sage-core redis falkordb
cd visualizer_agent/frontend && npm install && npm run dev
```

For the full 12-service stack (sensory agents + autonomous pipeline):
```bash
docker compose --profile sensory --profile agents up -d
```

## Pull request checklist

- [ ] All CSV rows carry a `source` key that resolves in `manifest.yaml`
- [ ] No `.env` or `.env.local` files included
- [ ] `docker compose build` passes without errors
- [ ] Frontend: `npm run build` (TypeScript strict) passes without errors
- [ ] New backend endpoints have a corresponding entry in `docs/EVALUATION.md`

## Code of conduct

Be respectful and constructive. Disagreements about methodology are welcome; personal attacks are not.

## Licence

By contributing, you agree that your contributions will be licensed under the [MIT Licence](LICENSE).
