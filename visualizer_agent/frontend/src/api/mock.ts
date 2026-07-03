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
} from "./types";

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

export const mockIntel: IntelItem[] = [
  { id: "1", source: "REUTERS", time: "14:21:44", text: "Emergency meeting of EU energy ministers called for next Tuesday.", tone: "info" },
  { id: "2", source: "AIS ALERTS", time: "14:19:12", text: "Tanker 'OCEAN SPIRIT' changed course near Socotra Island; seeking anchorage.", tone: "warn" },
  { id: "3", source: "PRICE MVT", time: "14:15:00", text: "WTI Futures holding steady despite inventory draw-down report.", tone: "good" },
  { id: "4", source: "SAGE CORE", time: "14:02:55", text: "Cyber anomaly detected at Houston terminal SCADA interface. Quarantined.", tone: "crit" },
];
