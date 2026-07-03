// Thin REST client for the SAGE API gateway.
// Every call falls back to mock data (from ./mock) on network/HTTP error, so the
// UI always renders. `live` on the returned envelope tells the UI whether the
// data came from the backend or the fallback.

import type {
  RiskScore,
  Supplier,
  Route,
  SprCavern,
  ProcurementOption,
  ScenarioOutput,
  SprSchedule,
  CopilotAnswer,
  GraphData,
  WikiPage,
  DashboardSummary,
} from "./types";
import * as mock from "./mock";

const BASE = import.meta.env.VITE_API_BASE ?? "";

export interface Envelope<T> {
  data: T;
  live: boolean;
}

async function get<T>(path: string, fallback: T): Promise<Envelope<T>> {
  try {
    const res = await fetch(`${BASE}${path}`, {
      headers: { Accept: "application/json" },
      signal: AbortSignal.timeout(4000),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = (await res.json()) as T;
    return { data, live: true };
  } catch {
    return { data: fallback, live: false };
  }
}

export const api = {
  health: () => get<{ status: string; kb_ready: boolean }>("/health", { status: "degraded", kb_ready: false }),

  riskScores: () => get<RiskScore[]>("/api/risk-scores", mock.mockRiskScores),

  graph: () => get<GraphData>("/api/graph", mock.mockGraph),

  dashboard: () => get<DashboardSummary>("/api/dashboard", mock.mockDashboard),

  suppliers: () => get<Supplier[]>("/api/suppliers", mock.mockSuppliers),

  routes: () => get<Route[]>("/api/routes", mock.mockRoutes),

  spr: () => get<SprCavern[]>("/api/spr", mock.mockSpr),

  scenario: () => get<ScenarioOutput>("/api/scenario", mock.mockScenario),

  procurement: () => get<ProcurementOption[]>("/api/procurement", mock.mockProcurement),

  sprSchedule: () => get<SprSchedule>("/api/spr-schedule", mock.mockSprSchedule),

  wiki: (entity: string) =>
    get<{ entity: string; content: string }>(`/api/wiki/${encodeURIComponent(entity)}`, {
      entity,
      content: `# ${entity}\n\n_No wiki page available (backend offline)._`,
    }),

  accuracy: () => get<{ detection_lead_hours: number; prestage_accuracy: number }>("/api/accuracy", {
    detection_lead_hours: 120,
    prestage_accuracy: 0.91,
  }),

  async copilot(question: string): Promise<Envelope<CopilotAnswer>> {
    try {
      const res = await fetch(`${BASE}/api/copilot`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: question }),
        signal: AbortSignal.timeout(20000),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return { data: (await res.json()) as CopilotAnswer, live: true };
    } catch {
      return {
        data: {
          answer:
            "**SAGE ranks ADNOC's Murban first** for Jamnagar.\n\n## Why\n- Its light-sweet assay closely matches Jamnagar's configured slate [1].\n- The **Fujairah land-bypass** routes crude to the Gulf of Oman without transiting the elevated-risk Strait of Hormuz [2] — the lowest corridor risk in the set.\n\n_(Backend offline — illustrative answer.)_",
          citations: ["ADNOC", "Strait of Hormuz"],
          sources: [
            { index: 1, entity: "ADNOC", type: "Supplier", kind: "wiki" },
            { index: 2, entity: "Strait of Hormuz", type: "Corridor", kind: "wiki" },
          ],
          route: "graph" as const,
        },
        live: false,
      };
    }
  },
};
