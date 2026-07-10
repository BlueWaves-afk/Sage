// Thin REST client for the SAGE API gateway.
// STRICT: the frontend renders ONLY data retrieved from the knowledge base. There
// is NO mock/fallback data. On network/HTTP error a call returns { data: null,
// live: false } and the UI shows an explicit OFFLINE state — never fabricated data.

import type {
  RiskScore,
  Supplier,
  Route,
  SprCavern,
  ProcurementRecData,
  ScenarioOutput,
  SprSchedule,
  CopilotAnswer,
  GraphData,
  DashboardSummary,
  IntelSignal,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "";

export interface Envelope<T> {
  data: T | null;
  live: boolean;
}

async function get<T>(path: string, opts?: RequestInit): Promise<Envelope<T>> {
  try {
    const res = await fetch(`${BASE}${path}`, {
      headers: { Accept: "application/json" },
      signal: AbortSignal.timeout(8000),
      ...opts,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = (await res.json()) as T;
    return { data, live: true };
  } catch {
    // No fallback data — the KB is the single source of truth.
    return { data: null, live: false };
  }
}

export const api = {
  health: () => get<{ status: string; kb_ready: boolean }>("/health"),

  riskScores: () => get<RiskScore[]>("/api/risk-scores"),

  graph: () => get<GraphData>("/api/graph"),

  dashboard: () => get<DashboardSummary>("/api/dashboard"),

  suppliers: () => get<Supplier[]>("/api/suppliers"),

  routes: () => get<Route[]>("/api/routes"),

  spr: () => get<SprCavern[]>("/api/spr"),

  scenario: () => get<ScenarioOutput>("/api/scenario"),

  procurement: () => get<ProcurementRecData>("/api/procurement"),

  sprSchedule: () => get<SprSchedule>("/api/spr-schedule"),

  wiki: (entity: string) =>
    get<{ entity: string; content: string }>(`/api/wiki/${encodeURIComponent(entity)}`),

  accuracy: () => get<{ detection_lead_hours: number; prestage_accuracy: number }>("/api/accuracy"),

  intelligence: (limit = 15) => get<IntelSignal[]>(`/api/intelligence?limit=${limit}`),

  evidence: (entity: string, limit = 12) =>
    get<IntelSignal[]>(`/api/evidence/${encodeURIComponent(entity)}?limit=${limit}`),

  copilot: (question: string) =>
    get<CopilotAnswer>("/api/copilot", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: question }),
      signal: AbortSignal.timeout(25000),
    }),
};
