// Mock data mirroring the Figma design content. Used as a fallback so every
// screen renders faithfully even when the FastAPI gateway is not running.
// When the backend is up, the real API responses replace these.

import type {
  RiskScore,
  Supplier,
  Route,
  SprCavern,
  ProcurementOption,
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

export const mockProcurement: ProcurementOption[] = [
  { supplier: "ADNOC", grade: "Murban", route_via: "Fujairah land-bypass", landed_cost_usd_bbl: 84.2, lead_time_days: 6, grade_compatibility: 0.94, corridor_risk: 0.12, topsis_score: 0.88, rationale: "Murban's light-sweet assay matches Jamnagar's configured slate; the Fujairah land-bypass to the Gulf of Oman avoids the contested Hormuz chokepoint entirely, offsetting a modest cost premium with the lowest corridor risk of any option." },
  { supplier: "Saudi Aramco", grade: "Arab Light", route_via: "Yanbu (Red Sea bypass)", landed_cost_usd_bbl: 82.9, lead_time_days: 10, grade_compatibility: 0.9, corridor_risk: 0.24, topsis_score: 0.81, rationale: "Arab Light via the Petroline pipeline to Yanbu bypasses Hormuz through the Red Sea. Longer lead time is offset by the lowest landed cost and a highly compatible medium-sour grade." },
  { supplier: "Iraqi Oil Ministry", grade: "Basrah Medium", route_via: "Strait of Hormuz", landed_cost_usd_bbl: 80.1, lead_time_days: 8, grade_compatibility: 0.86, corridor_risk: 0.62, topsis_score: 0.64, rationale: "Cheapest barrel but routes directly through the elevated-risk Hormuz corridor; ranked lower on corridor risk despite strong cost and acceptable compatibility." },
];

export const mockScenario: ScenarioOutput = {
  scenario_id: "scn_hormuz_2026_0223",
  trigger_entity: "Strait of Hormuz",
  status: "speculative",
  confidence: 0.91,
  gap_mbpd: 0.5,
  price_shock_pct: 12,
  spr_cover_days: 9.5,
  narrative:
    "Geopolitical tension in the Red Sea has reached a critical threshold. SAGE models predict a 12% increase in Brent Crude volatility over the next 48 hours. Strategic pivoting of tankers is underway.",
  chain_of_events: [
    "Complete cessation of traffic through main arterial lanes.",
    "Immediate insurance premium surge for local anchorage.",
    "Projected 12% global price shock within 48 hours.",
  ],
  assumptions: [
    "Assumes neutralization of Cape route optimization and static naval deployment in the Red Sea corridor.",
  ],
  timeline: [
    { hour: 12, label: "Insurance Surges" },
    { hour: 24, label: "Terminal Delays" },
    { hour: 36, label: "Local Price Spike" },
    { hour: 48, label: "Reserve Activation", critical: true },
  ],
};

export const mockSprSchedule: SprSchedule = {
  scenario_id: "scn_hormuz_2026_0223",
  buffer_probability: 0.97,
  drawdown: [
    { day: 1, reserve_days: 9.5, action: "Hold" },
    { day: 2, reserve_days: 9.1, action: "Hold" },
    { day: 3, reserve_days: 8.4, action: "Release Tier-1 (Vizag)" },
    { day: 4, reserve_days: 7.6, action: "Release Tier-1 (Padur)" },
    { day: 5, reserve_days: 7.0, action: "Sustain" },
  ],
  memo:
    "Authorize release of Tier-1 reserves from Vishakhapatnam and Padur to maintain 48-hour refinery continuity. Modelled drawdown holds reserve cover above the 3-day buffer with 97% probability across the projected gap window.",
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
