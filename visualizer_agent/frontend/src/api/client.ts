// Thin REST client for the SAGE API gateway.
// STRICT: the frontend renders ONLY data retrieved from the knowledge base. There
// is NO mock/fallback data. On network/HTTP error a call returns { data: null,
// live: false } and the UI shows an explicit OFFLINE state — never fabricated data.

import type {
  RiskScore,
  RiskHistoryPoint,
  SprCurve,
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
  ScenarioRunRequest,
  ScenarioRunStatus,
  ScenarioPreset,
  ScenarioCard,
  ScenarioAccuracy,
  CalibrationFactors,
  AgentTraceEvent,
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

async function post<T>(path: string, body: unknown, opts?: RequestInit): Promise<Envelope<T>> {
  try {
    const res = await fetch(`${BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(60000),
      ...opts,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = (await res.json()) as T;
    return { data, live: true };
  } catch {
    return { data: null, live: false };
  }
}

export const api = {
  health: () => get<{ status: string; kb_ready: boolean; live?: boolean; voice_mode?: string }>("/health"),

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

  wikiList: (limit = 50) =>
    get<{ entity: string; title: string; updated: string | null }[]>(`/api/wiki?limit=${limit}`),

  accuracy: () => get<{ detection_lead_hours?: number; prestage_accuracy?: number; fusion_model?: { version: string; validation: string; auc?: number; mean_loco_auc?: number; threshold?: number; trained_at?: string; n_crises?: number; n_ticks?: number; label?: string } }>("/api/accuracy"),

  brief: () => get<{ entity: string | null; assessment: string | null; updated: string | null; wiki_entity: string | null }>("/api/brief"),

  intelligence: (limit = 15) => get<IntelSignal[]>(`/api/intelligence?limit=${limit}`),

  evidence: (entity: string, limit = 12) =>
    get<IntelSignal[]>(`/api/evidence/${encodeURIComponent(entity)}?limit=${limit}`),

  riskHistory: (entity: string, hours = 24) =>
    get<RiskHistoryPoint[]>(`/api/risk-history?entity=${encodeURIComponent(entity)}&hours=${hours}`),

  sprCurve: () => get<SprCurve>("/api/spr-curve"),

  runScenario: (body: ScenarioRunRequest) =>
    post<{ run_id: string; scenario_id: string | null }>("/api/scenario/run", body),

  scenarioStatus: (runId: string) =>
    get<ScenarioRunStatus>(`/api/scenario/status/${encodeURIComponent(runId)}`),

  scenarioPresets: () => get<ScenarioPreset[]>("/api/scenario/presets"),

  scenarioById: (id: string) =>
    get<ScenarioOutput>(`/api/scenario?scenario_id=${encodeURIComponent(id)}`),

  procurementById: (id: string) =>
    get<ProcurementRecData>(`/api/procurement?scenario_id=${encodeURIComponent(id)}`),

  sprScheduleById: (id: string) =>
    get<SprSchedule>(`/api/spr-schedule?scenario_id=${encodeURIComponent(id)}`),

  scenarioLibrary: (origin: "all" | "auto" | "user" | "preset" = "all", limit = 20) =>
    get<ScenarioCard[]>(`/api/scenario/library?origin=${origin}&limit=${limit}`),

  promoteScenario: (body: { scenario_id: string; label: string; blurb?: string }) =>
    post<{ slug: string }>("/api/scenario/promote", body),

  unpromoteScenario: (slug: string) =>
    get<{ ok: boolean }>(`/api/scenario/promote/${encodeURIComponent(slug)}`, { method: "DELETE" }),

  scenarioAccuracy: () => get<ScenarioAccuracy>("/api/scenario/accuracy"),

  logScenarioOutcome: (
    scenarioId: string,
    body: { gap_mbpd?: number; price_impact_high?: number; spr_depletion_days?: number; gdp_proxy_impact_pct?: number; note?: string }
  ) => post<{ ok: boolean; error: Record<string, number>; calibration: unknown }>(
    `/api/scenario/${encodeURIComponent(scenarioId)}/outcome`, body
  ),

  scenarioCalibration: () => get<CalibrationFactors>("/api/scenario/calibration"),

  agentTraceRecent: (limit = 30) => get<AgentTraceEvent[]>(`/api/agent-trace/recent?limit=${limit}`),

  responseTime: () => get<import("./types").ResponseTimeSummary>("/api/response-time"),

  demoIgnite: () => get<{ ok: boolean; message: string }>("/api/demo/ignite", { method: "POST" }),

  copilot: (question: string) =>
    get<CopilotAnswer>("/api/copilot", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: question }),
      signal: AbortSignal.timeout(25000),
    }),
};
