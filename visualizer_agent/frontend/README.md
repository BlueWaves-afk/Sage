# SAGE Frontend — System 5

React + Vite + deck.gl command-center UI for SAGE, built to the Figma design
(`National Defense AI`). Six screens, wired to the FastAPI gateway with graceful
mock-data fallback so every screen renders even when the backend is offline.

## Screens

| Route | Screen | Backend endpoint |
|-------|--------|------------------|
| `/` | Landing | `/health` |
| `/command` | National Energy Intelligence Command Center | `/api/risk-scores`, `/ws` |
| `/intelligence` | Global Intelligence Explorer | `/api/risk-scores` |
| `/simulation` | Simulation Lab (anticipatory sandbox) | `/api/scenario` |
| `/response` | Response Planner (procurement + SPR) | `/api/procurement`, `/api/spr-schedule` |
| `/copilot` | Strategic Copilot | `POST /api/copilot` |

## Develop

```bash
npm install
npm run dev          # http://localhost:5173  (proxies /api + /ws → :8000)
```

Start the backend separately (`docker compose up sage-core api-gateway`) for live
data; without it the UI shows clearly-labelled demo data.

## Build & deploy

```bash
npm run build        # → dist/  (static, deploy anywhere)
```

- **Vercel / Amplify:** point the project at `visualizer_agent/frontend`, build
  command `npm run build`, output `dist`. Set `VITE_API_BASE` / `VITE_WS_BASE`
  to the EC2 gateway URL (see `.env.example`).
- **Same-origin (EC2):** serve `dist/` behind the same nginx that proxies the
  gateway; leave the env vars blank so the app uses relative `/api` + `/ws`.

## Design system

Tokens live in `src/index.css` (`:root`). Deep-navy surfaces, cyan accent,
JetBrains Mono for telemetry. Change a token there and it propagates everywhere.

## Stack

- **deck.gl** `ScatterplotLayer` (risk nodes) + `ArcLayer` (supply routes) over a
  free CARTO dark basemap (no map token required).
- **react-router** for the 6 routes; `AppShell` holds the icon rail, top bar,
  status bar shared by the five operational screens.
- **No state library** — a tiny `useApi` hook + a `usePipeline` WebSocket hook.
