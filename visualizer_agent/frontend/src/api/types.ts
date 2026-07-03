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

export interface ScenarioOutput {
  scenario_id: string;
  trigger_entity: string;
  status: "speculative" | "confirmed";
  confidence: number;
  gap_mbpd: number;
  price_shock_pct: number;
  spr_cover_days: number;
  narrative: string;
  chain_of_events: string[];
  assumptions: string[];
  timeline: { hour: number; label: string; critical?: boolean }[];
}

export interface SprSchedule {
  scenario_id: string;
  buffer_probability: number;
  drawdown: { day: number; reserve_days: number; action: string }[];
  memo: string;
}

export interface IntelItem {
  id: string;
  source: "REUTERS" | "AIS ALERTS" | "PRICE MVT" | "SAGE CORE" | "OFAC";
  time: string;
  text: string;
  tone: "info" | "warn" | "good" | "crit";
}

export interface CopilotAnswer {
  answer: string;
  citations: { entity: string; episode_id: string }[];
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
