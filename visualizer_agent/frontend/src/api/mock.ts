// Mock data mirroring the Figma design content. Used as a fallback so every
// screen renders faithfully even when the FastAPI gateway is not running.
// When the backend is up, the real API responses replace these.

import type {
  RiskScore,
  Supplier,
  Route,
  SprCavern,
  ProcurementOption,
  ProcurementRecData,
  ScenarioOutput,
  SprSchedule,
  IntelItem,
  GraphData,
  GraphNode,
  DashboardSummary,
} from "./types";

export const mockDashboard: DashboardSummary = {
  threat_level: "MEDIUM",
  active_alerts: 2,
  spr_coverage_pct: 57.2,
  brent_usd_bbl: 95.0,
  brent_source: "EIA-STEO",
  monitoring_entities: 61,
  bottlenecks: [
    { name: "Strait of Hormuz", status: "NOMINAL", risk: 0.62 },
    { name: "Bab-el-Mandeb", status: "CONTESTED", risk: 0.71 },
    { name: "Strait of Malacca", status: "NOMINAL", risk: 0.18 },
  ],
  top_risk_entity: "Strait of Hormuz",
};

export const mockRiskScores: RiskScore[] = [
  { entity: "Strait of Hormuz", score: 0.62, band: "ELEVATED", factors: { ais: 0.31, gdelt: 0.19, price: 0.12, sanctions: 0.05 }, lat: 26.5, lon: 56.4 },
  { entity: "Bab-el-Mandeb", score: 0.71, band: "ACTION", factors: { ais: 0.28, gdelt: 0.33, price: 0.14, sanctions: 0.02 }, lat: 12.5, lon: 43.3 },
  { entity: "Suez Canal", score: 0.24, band: "WATCH", factors: { ais: 0.08, gdelt: 0.09, price: 0.05, sanctions: 0.0 }, lat: 30.7, lon: 32.3 },
  { entity: "Strait of Malacca", score: 0.18, band: "CALM", factors: { ais: 0.06, gdelt: 0.05, price: 0.04, sanctions: 0.0 }, lat: 2.5, lon: 101.0 },
  { entity: "Jamnagar", score: 0.44, band: "WATCH", factors: { ais: 0.12, gdelt: 0.18, price: 0.1, sanctions: 0.04 }, lat: 22.5, lon: 70.0 },
];

export const mockSuppliers: Supplier[] = [
  { display_name: "Saudi Aramco", country: "Saudi Arabia", daily_export_mbpd: 6.3, risk_score: 0.22, sanctioned: false },
  { display_name: "ADNOC", country: "United Arab Emirates", daily_export_mbpd: 2.9, risk_score: 0.18, sanctioned: false },
  { display_name: "Iraqi Oil Ministry", country: "Iraq", daily_export_mbpd: 3.4, risk_score: 0.31, sanctioned: false },
  { display_name: "NIOC", country: "Iran", daily_export_mbpd: 1.4, risk_score: 0.88, sanctioned: true },
];

export const mockRoutes: Route[] = [
  { display_name: "Strait of Hormuz", throughput_mbpd: 21.0, risk_score: 0.62, status: "NOMINAL" },
  { display_name: "Bab-el-Mandeb", throughput_mbpd: 6.2, risk_score: 0.71, status: "CONTESTED" },
  { display_name: "Strait of Malacca", throughput_mbpd: 16.0, risk_score: 0.18, status: "NOMINAL" },
];

export const mockSpr: SprCavern[] = [
  { display_name: "Vizag SPR", capacity_mmt: 1.33, current_fill_mmt: 0.9, fill_pct: 0.677 },
  { display_name: "Mangaluru SPR", capacity_mmt: 1.5, current_fill_mmt: 0.86, fill_pct: 0.573 },
  { display_name: "Padur SPR", capacity_mmt: 2.5, current_fill_mmt: 1.4, fill_pct: 0.56 },
];

// Landed cost = baseline Brent (~$95/bbl) + freight + bypass/war-risk premium —
// values here match a real golden-path run (Hormuz closed, all routes bypass it).
const mockProcurementOptions: ProcurementOption[] = [
  { supplier: "ADNOC", grade: "Murban", route_via: "Cape of Good Hope", landed_cost_usd_bbl: 98.05, lead_time_days: 24, grade_compatibility: 1.0, corridor_risk: 0.0, topsis_score: 0.78, rationale: "Murban's light-sweet assay matches Jamnagar's configured slate; the Fujairah bypass avoids the contested Hormuz chokepoint entirely, offsetting a modest freight premium with the lowest corridor risk of any option." },
  { supplier: "KazMunayGas", grade: "CPC Blend", route_via: "Suez Canal", landed_cost_usd_bbl: 98.5, lead_time_days: 26, grade_compatibility: 0.88, corridor_risk: 0.0, topsis_score: 0.73, rationale: "CPC Blend via Suez avoids Hormuz entirely. Longer lead time is offset by a highly compatible medium grade and zero corridor risk." },
  { supplier: "NNPC", grade: "Bonny Light", route_via: "Suez Canal", landed_cost_usd_bbl: 98.8, lead_time_days: 26, grade_compatibility: 0.9, corridor_risk: 0.0, topsis_score: 0.68, rationale: "Bonny Light's low sulfur content is compatible with Jamnagar's slate; routing via Suez avoids the disrupted Hormuz corridor at a modest cost premium." },
];

export const mockProcurement: ProcurementRecData = {
  scenario_id: "scn_hormuz_2026_0223",
  status: "confirmed",
  target_refinery: "Jamnagar Refinery",
  ranked: mockProcurementOptions,
};

// Shape matches the real ScenarioOutputData contract exactly (verified against a
// live golden-path run: Iran-Israel conflict escalation closing Strait of Hormuz).
export const mockScenario: ScenarioOutput = {
  scenario_id: "scn_hormuz_2026_0223",
  trigger_entity: "Strait of Hormuz",
  status: "confirmed",
  confidence: 1.0,
  gap_mbpd: 0.61,
  gap_duration_days: 10,
  feedstock_gap_timeline: [0.15, 0.29, 0.43, 0.57, 0.61, 0.55, 0.42, 0.28, 0.14, 0.03],
  price_impact_low: 35.7,
  price_impact_high: 61.2,
  spr_depletion_days: 45,
  gdp_proxy_impact_pct: -1.28,
  inflation_impact_pct: 3.62,
  sector_impacts: [
    { sector: "transport", petroleum_share: 0.51, shortfall_mbpd: 0.31, gdp_weight: 7.0, criticality: 0.9 },
    { sector: "industry", petroleum_share: 0.12, shortfall_mbpd: 0.07, gdp_weight: 27.0, criticality: 0.6 },
    { sector: "agriculture", petroleum_share: 0.05, shortfall_mbpd: 0.03, gdp_weight: 18.0, criticality: 0.85 },
  ],
  node_impacts: [
    { node: "Jamnagar Refinery", node_type: "Refinery", exposure: 0.429, peak_gap_mbpd: 0.61, onset_day: 3, gap_timeline: [] },
  ],
  assumptions: {
    disruption_fraction: { value: 0.8, unit: "frac", source: "LLM scenario decision" },
    escalation_profile: { value: "escalating", source: "LLM scenario decision" },
    import_dependence_pct: { value: 88.6, unit: "%", source: "PPAC 2025" },
  },
};

export const mockSprSchedule: SprSchedule = {
  scenario_id: "scn_hormuz_2026_0223",
  status: "confirmed",
  prob_above_buffer: 0.089,
  constraint_satisfied: false,
  lagrange_multiplier: null,
  option_value_of_waiting: -273.46,
  daily_plan: [
    { day: 1, action: "draw", volume_mmt: 0.172, reserve_after_mmt: 2.878, days_cover_after: 5.05, decision_driver: "drawing 0.172 MMT to cover 0.172 MMT/d feedstock gap" },
    { day: 2, action: "draw", volume_mmt: 0.172, reserve_after_mmt: 2.705, days_cover_after: 4.75, decision_driver: "drawing 0.172 MMT to cover 0.172 MMT/d feedstock gap" },
    { day: 3, action: "draw", volume_mmt: 0.172, reserve_after_mmt: 2.533, days_cover_after: 4.44, decision_driver: "drawing 0.172 MMT to cover 0.172 MMT/d feedstock gap" },
    { day: 4, action: "draw", volume_mmt: 0.172, reserve_after_mmt: 2.360, days_cover_after: 4.14, decision_driver: "drawing 0.172 MMT to cover 0.172 MMT/d feedstock gap" },
    { day: 5, action: "draw", volume_mmt: 0.172, reserve_after_mmt: 2.188, days_cover_after: 3.84, decision_driver: "drawing 0.172 MMT to cover 0.172 MMT/d feedstock gap" },
  ],
  policy_memo:
    "Given the current 1.58 mbpd supply gap projected over 30 days, initiate a strategic drawdown of the SPR immediately, releasing 3.05 MMT over a 25-day period. The chance constraint (P(reserve<3 days)≤0.05) is NOT satisfied under this scenario severity — diversifying via alternative procurement is essential, not optional.",
};

// A representative slice of the geospatial knowledge graph for offline mode.
// When the backend is up, /api/graph replaces this with the full 61-node graph.
const gn = (
  id: string,
  name: string,
  type: string,
  lat: number,
  lon: number,
  score = 0,
): GraphNode => ({
  id,
  name,
  type,
  lat,
  lon,
  score,
  band:
    score >= 0.85 ? "CRITICAL" : score >= 0.7 ? "ACTION" : score >= 0.45 ? "ELEVATED" : score >= 0.25 ? "WATCH" : "CALM",
  degree: 0,
});

const MOCK_NODES: GraphNode[] = [
  // Corridors
  gn("corridor_hormuz", "Strait of Hormuz", "Corridor", 26.5, 56.4, 0.62),
  gn("corridor_bab", "Bab-el-Mandeb", "Corridor", 12.5, 43.3, 0.71),
  gn("corridor_suez", "Suez Canal", "Corridor", 30.7, 32.3, 0.24),
  gn("corridor_malacca", "Strait of Malacca", "Corridor", 2.5, 101.0, 0.18),
  gn("corridor_cape", "Cape of Good Hope", "Corridor", -34.3, 18.5, 0.08),
  // Refineries (India)
  gn("ref_jamnagar", "Jamnagar Refinery", "Refinery", 22.47, 70.07, 0.44),
  gn("ref_vadinar", "Vadinar Refinery", "Refinery", 22.28, 69.72, 0.3),
  gn("ref_paradip", "Paradip Refinery", "Refinery", 20.31, 86.69, 0.2),
  gn("ref_mangaluru", "Mangaluru Refinery", "Refinery", 12.91, 74.84, 0.22),
  gn("ref_visakh", "Visakhapatnam Refinery", "Refinery", 17.69, 83.28, 0.18),
  // SPR
  gn("spr_vizag", "Vizag SPR", "SPRCavern", 17.69, 83.28, 0.1),
  gn("spr_mangaluru", "Mangaluru SPR", "SPRCavern", 12.91, 74.84, 0.1),
  gn("spr_padur", "Padur SPR", "SPRCavern", 13.06, 74.68, 0.1),
  // Suppliers (country oil hubs)
  gn("sup_aramco", "Saudi Aramco", "Supplier", 25.36, 49.59, 0.22),
  gn("sup_adnoc", "ADNOC", "Supplier", 24.47, 54.37, 0.18),
  gn("sup_iraq", "Iraqi Oil Ministry", "Supplier", 30.51, 47.78, 0.31),
  gn("sup_nioc", "NIOC", "Supplier", 29.61, 50.83, 0.88),
  gn("sup_kpc", "Kuwait Petroleum Corporation", "Supplier", 29.34, 47.68, 0.2),
  gn("sup_qatar", "QatarEnergy", "Supplier", 25.29, 51.53, 0.16),
  gn("sup_rosneft", "Rosneft", "Supplier", 55.75, 37.62, 0.55),
  gn("sup_us", "United States", "Supplier", 29.76, -95.37, 0.05),
  gn("sup_nnpc", "NNPC", "Supplier", 4.77, 7.01, 0.28),
  // Grades
  gn("grade_arablight", "Arab Light", "CrudeGrade", 24.7, 47.9),
  gn("grade_murban", "Murban", "CrudeGrade", 23.9, 55.0),
  gn("grade_basrah", "Basrah Medium", "CrudeGrade", 30.0, 47.0),
  gn("grade_urals", "Urals", "CrudeGrade", 54.8, 39.0),
  // Ports
  gn("port_yanbu", "Yanbu", "Port", 24.09, 38.05, 0.15),
  gn("port_fujairah", "Fujairah", "Port", 25.11, 56.34, 0.2),
  // Authorities
  gn("auth_ofac", "OFAC", "Authority", 38.9, -77.04, 0),
  gn("auth_eu", "EU", "Authority", 50.85, 4.35, 0),
  // Events
  gn("event_redsea", "2024 Red Sea Crisis", "GeoEvent", 14.5, 42.5, 0.8),
  gn("event_hormuz", "2025 Iran-Israel Conflict", "GeoEvent", 27.0, 55.5, 0.9),
];

const E = (source: string, target: string, relation: string) => ({ source, target, relation });
const MOCK_EDGES = [
  E("sup_aramco", "corridor_hormuz", "EXPORTS_VIA"),
  E("sup_adnoc", "corridor_hormuz", "EXPORTS_VIA"),
  E("sup_iraq", "corridor_hormuz", "EXPORTS_VIA"),
  E("sup_nioc", "corridor_hormuz", "EXPORTS_VIA"),
  E("sup_kpc", "corridor_hormuz", "EXPORTS_VIA"),
  E("sup_qatar", "corridor_hormuz", "EXPORTS_VIA"),
  E("corridor_hormuz", "ref_jamnagar", "FEEDS"),
  E("corridor_hormuz", "ref_vadinar", "FEEDS"),
  E("corridor_hormuz", "ref_mangaluru", "FEEDS"),
  E("sup_aramco", "port_yanbu", "BYPASS_ROUTE"),
  E("sup_adnoc", "port_fujairah", "BYPASS_ROUTE"),
  E("sup_rosneft", "corridor_suez", "EXPORTS_VIA"),
  E("sup_nnpc", "corridor_cape", "EXPORTS_VIA"),
  E("grade_arablight", "sup_aramco", "ORIGINATES_FROM"),
  E("grade_murban", "sup_adnoc", "ORIGINATES_FROM"),
  E("grade_basrah", "sup_iraq", "ORIGINATES_FROM"),
  E("grade_urals", "sup_rosneft", "ORIGINATES_FROM"),
  E("grade_arablight", "ref_jamnagar", "CONFIGURED_FOR"),
  E("grade_murban", "ref_jamnagar", "CONFIGURED_FOR"),
  E("grade_basrah", "ref_paradip", "CONFIGURED_FOR"),
  E("ref_visakh", "spr_vizag", "FEEDS_RESERVE"),
  E("ref_mangaluru", "spr_mangaluru", "FEEDS_RESERVE"),
  E("sup_nioc", "auth_ofac", "SANCTIONED_BY"),
  E("sup_rosneft", "auth_eu", "SANCTIONED_BY"),
  E("event_hormuz", "corridor_hormuz", "AFFECTS_SCENARIO"),
  E("event_redsea", "corridor_bab", "AFFECTS_SCENARIO"),
];

// Compute degree for sizing.
for (const e of MOCK_EDGES) {
  const s = MOCK_NODES.find((n) => n.id === e.source);
  const t = MOCK_NODES.find((n) => n.id === e.target);
  if (s) s.degree++;
  if (t) t.degree++;
}

export const mockGraph: GraphData = { nodes: MOCK_NODES, edges: MOCK_EDGES };

export const mockIntel: IntelItem[] = [
  { id: "1", source: "REUTERS", time: "14:21:44", text: "Emergency meeting of EU energy ministers called for next Tuesday.", tone: "info" },
  { id: "2", source: "AIS ALERTS", time: "14:19:12", text: "Tanker 'OCEAN SPIRIT' changed course near Socotra Island; seeking anchorage.", tone: "warn" },
  { id: "3", source: "PRICE MVT", time: "14:15:00", text: "WTI Futures holding steady despite inventory draw-down report.", tone: "good" },
  { id: "4", source: "SAGE CORE", time: "14:02:55", text: "Cyber anomaly detected at Houston terminal SCADA interface. Quarantined.", tone: "crit" },
];
