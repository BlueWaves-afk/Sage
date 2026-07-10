// Typed shapes for the SAGE API gateway responses.
// Mirrors contracts/outputs.py and knowledge/api/read.py return models.

export type RiskBand = "CALM" | "WATCH" | "ELEVATED" | "ACTION" | "CRITICAL";
export type ThreatLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface RiskScore {
  entity: string;
  score: number;
  band: RiskBand;
  factors: { ais: number; gdelt: number; price: number; sanctions: number };
  lat?: number;
  lon?: number;
  updated_at?: string;
}

export interface Supplier {
  display_name: string;
  country: string;
  daily_export_mbpd: number;
  risk_score: number;
  sanctioned: boolean;
}

export interface Route {
  display_name: string;
  throughput_mbpd: number;
  risk_score: number;
  status: "NOMINAL" | "CONTESTED" | "BLOCKED";
}

export interface SprCavern {
  display_name: string;
  capacity_mmt: number;
  current_fill_mmt: number;
  fill_pct: number;
}

export interface ProcurementOption {
  supplier: string;
  grade: string;
  route_via: string;
  landed_cost_usd_bbl: number;
  lead_time_days: number;
  grade_compatibility: number;
  corridor_risk: number;
  topsis_score: number;
  rationale: string;
}

// Mirrors contracts/outputs.py::ProcurementRecData exactly — the real /api/procurement
// response is this wrapper, not a bare ProcurementOption[].
export interface ProcurementRecData {
  scenario_id: string;
  status: "speculative" | "confirmed";
  target_refinery: string | null;
  ranked: ProcurementOption[];
}

// Mirrors contracts/outputs.py::ScenarioOutputData exactly — field names must match
// the real backend response (verified against a live golden-path run), not an
// invented shape, or the UI silently renders nothing for fields that don't exist.
export interface SectorImpact {
  sector: string;
  petroleum_share: number;
  shortfall_mbpd: number;
  gdp_weight: number;
  criticality: number;
}

export interface NodeImpact {
  node: string;
  node_type: string;
  exposure: number;
  peak_gap_mbpd: number;
  onset_day: number;
  gap_timeline: number[];
}

export interface AssumptionEntry {
  value: number | string;
  unit?: string;
  source?: string;
  [key: string]: unknown;
}

export interface ScenarioOutput {
  scenario_id: string;
  trigger_entity: string;
  status: "speculative" | "confirmed" | "counterfactual";
  confidence: number;
  gap_mbpd: number;
  gap_duration_days: number;
  feedstock_gap_timeline: number[];
  price_impact_low: number;
  price_impact_high: number;
  spr_depletion_days: number;
  gdp_proxy_impact_pct: number | null;
  inflation_impact_pct: number | null;
  sector_impacts: SectorImpact[];
  node_impacts: NodeImpact[];
  assumptions: Record<string, AssumptionEntry>;
  counterfactual_type?: string | null;
}

// Mirrors contracts/outputs.py::SPRScheduleData / SPRDay.
export interface SprDay {
  day: number;
  action: "draw" | "hold" | "refill";
  volume_mmt: number;
  reserve_after_mmt: number;
  days_cover_after: number;
  decision_driver?: string | null;
}

export interface SprSchedule {
  scenario_id: string;
  status: "speculative" | "confirmed";
  daily_plan: SprDay[];
  prob_above_buffer: number;
  constraint_satisfied: boolean;
  lagrange_multiplier?: number | null;
  option_value_of_waiting?: number | null;
  policy_memo: string;
}

export interface IntelItem {
  id: string;
  source: "REUTERS" | "AIS ALERTS" | "PRICE MVT" | "SAGE CORE" | "OFAC";
  time: string;
  text: string;
  tone: "info" | "warn" | "good" | "crit";
}

export interface CopilotSource {
  index: number;
  entity: string;
  type: string;
  kind: "wiki" | "graph";
  snippet?: string | null;
}

export interface CopilotAnswer {
  answer: string;
  citations: string[];
  sources: CopilotSource[];
  route: "vector" | "graph" | "hybrid";
  latency_ms?: number;
}

export interface GraphNode {
  id: string;
  name: string;
  type: string; // Corridor | Supplier | Refinery | CrudeGrade | Port | SPRCavern | Authority | GeoEvent
  lat: number | null;
  lon: number | null;
  score: number;
  band: RiskBand;
  degree: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  relation: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface WikiPage {
  entity: string;
  content: string;
}

export interface Bottleneck {
  name: string;
  status: "NOMINAL" | "CONTESTED" | "BLOCKED";
  risk: number | null;
}

export interface SupplyChainIndex {
  index: number;
  band: string;
  method: string;
  contributors: { entity: string; risk: number; weight: number; contribution: number; band: string }[];
  entities_scored: number;
}

export interface DashboardSources {
  brent: string;
  spr: string;
  threat: string;
  ais: string;
  sanctions: string;
  news: string;
}

export interface DashboardSummary {
  threat_level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  active_alerts: number;
  spr_coverage_pct: number | null;
  brent_usd_bbl: number | null;
  brent_source: string | null;
  monitoring_entities: number;
  bottlenecks: Bottleneck[];
  top_risk_entity: string | null;
  supply_chain_index?: SupplyChainIndex | null;
  sources?: DashboardSources;
}

/** One piece of live intelligence (a real ingested signal/episode). */
export interface IntelSignal {
  id: string;
  source: string; // news | gdelt | ais | price | sanctions | synthesis
  headline: string;
  detail: string;
  source_url: string;
  entities: string[];
  recorded_at: string;
}

export interface RiskHistoryPoint {
  valid_at: string;
  score: number;
  factor_ais: number;
  factor_gdelt: number;
  factor_price: number;
  factor_sanctions: number;
}

export interface SprProjectionDay {
  day: number;
  fill_mmt: number;
  days_cover: number;
  action: "draw" | "hold" | "refill";
}

export interface SprCurve {
  caverns: SprCavern[];
  total_capacity_mmt: number;
  current_fill_mmt: number;
  fill_pct: number;
  days_cover: number;
  projection: SprProjectionDay[];
}

export interface ScenarioRunRequest {
  entity: string;
  disruption_fraction: number;
  disruption_days: number;
  escalation_profile: "constant" | "escalating" | "resolving";
  bypass_compromised_frac: number;
  spr_policy: "aggressive" | "moderate" | "none";
  demand_destruction_pct: number;
  run_downstream: boolean;
}

export interface ScenarioRunStatus {
  stage: "scenario" | "procurement" | "reserve" | "done" | "error";
  pct: number;
  scenario_id: string | null;
  error?: string | null;
}

export interface ScenarioPreset {
  id: string;
  label: string;
  entity: string;
  disruption_fraction: number;
  disruption_days: number;
  escalation_profile: "constant" | "escalating" | "resolving";
  bypass_compromised_frac: number;
  spr_policy: "aggressive" | "moderate" | "none";
  demand_destruction_pct: number;
  blurb: string;
  custom?: boolean;
  source_scenario_id?: string;
}

export interface ScenarioCard {
  scenario_id: string;
  label: string;
  origin: "auto" | "user" | "preset";
  trigger_entity: string;
  gap_mbpd: number;
  price_impact_high: number;
  gdp_proxy_impact_pct: number | null;
  spr_depletion_days: number;
  created_at: string;
  payload_available: boolean;
}

export interface ScenarioAccuracy {
  crossing: {
    total_predictions: number;
    confirmed: number;
    expired_false_positives: number;
    precision: number;
    mean_lead_time_error_hours: number | null;
    records_until_retrain: number;
  } | null;
  scenario: {
    total_predictions: number;
    realized: number;
    mape: Record<string, { mape: number; n: number }>;
    per_corridor: Record<string, { n: number; mape_gap: number | null; mape_price: number | null }>;
  } | null;
}

export interface CalibrationFactors {
  per_corridor: Record<string, { gap_x: number; price_x: number; n: number }>;
}

export interface MonteCarloBands {
  gap_mbpd: { p10: number; p50: number; p90: number };
  price_impact_usd: { low: number; high: number };
  spr_depletion_days: { p10: number; p50: number; p90: number };
  n: number;
}

export interface RunSummary {
  runId: string;
  label: string;
  scenarioId: string;
  entity: string;
  gap_mbpd: number;
  price_impact_low: number;
  price_impact_high: number;
  gdp_proxy_impact_pct: number | null;
  spr_depletion_days: number;
  gap_duration_days: number;
  timestamp: string;
}

export interface PipelineState {
  stage:
    | "SENSE"
    | "TRIAGE"
    | "SAGE"
    | "SANDBOX"
    | "SCENARIO"
    | "PROCURE"
    | "RESERVE";
  active: boolean;
}

export interface AgentTraceEvent {
  type: "agent_trace";
  system: "1" | "2" | "3" | "4";
  agent: "ais" | "news" | "prices" | "sanctions" | "fusion" | "scenario" | "procurement" | "reserve";
  action: string;
  status: "started" | "done" | "error";
  entity: string | null;
  origin: "auto" | "user" | null;
  ts: string;
}
