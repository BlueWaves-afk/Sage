import { useEffect, useState } from "react";
import WikiDrawer from "../components/WikiDrawer";
import MapView from "../components/MapView";
import { Badge } from "../components/ui/ui";
import { IconShield } from "../components/icons";
import { api, useApi } from "../api/hooks";
import type {
  GraphNode, RiskScore, NodeImpact,
  ScenarioOutput, ProcurementRecData, SprSchedule, RunSummary,
} from "../api/types";
import { useVoice, voiceStore } from "../voice/useVoiceStore";
import ScenarioBuilder from "../components/sim/ScenarioBuilder";
import ImpactTab from "../components/sim/ImpactTab";
import CascadeTab from "../components/sim/CascadeTab";
import ProcurementTab from "../components/sim/ProcurementTab";
import ReserveTab from "../components/sim/ReserveTab";
import CompareTab from "../components/sim/CompareTab";
import LearningTab from "../components/sim/LearningTab";
import SensitivityTab from "../components/sim/SensitivityTab";
import "./simulation.css";

type Tab = "impact" | "cascade" | "procurement" | "reserve" | "compare" | "sensitivity" | "learning";

function toRiskScore(n: GraphNode): RiskScore {
  return {
    entity: n.name, score: n.score, band: n.band,
    factors: { ais: 0, gdelt: 0, price: 0, sanctions: 0 },
    lat: n.lat ?? undefined, lon: n.lon ?? undefined,
  };
}

function projectNodes(nodes: RiskScore[], nodeImpacts: NodeImpact[]): RiskScore[] {
  const byName = new Map(nodeImpacts.map((n) => [n.node, n]));
  return nodes.map((n) => {
    const impact = byName.get(n.entity);
    if (!impact) return n;
    const projected = Math.min(1, n.score + impact.exposure * 0.4);
    const band = projected >= 0.9 ? "CRITICAL" : projected >= 0.7 ? "ACTION" : projected >= 0.45 ? "ELEVATED" : n.band;
    return { ...n, score: projected, band };
  });
}

export default function SimulationLab() {
  // Cache-first: load latest cached outputs on mount
  const { data: cachedScenario } = useApi(api.scenario);
  const { data: cachedProc }     = useApi(api.procurement);
  const { data: cachedSpr }      = useApi(api.sprSchedule);
  const { data: graph }          = useApi(api.graph);
  const { data: dash }           = useApi(api.dashboard);

  // Active run results (replace cached once a run completes)
  const [scenario, setScenario]   = useState<ScenarioOutput | null>(null);
  const [proc, setProc]           = useState<ProcurementRecData | null>(null);
  const [sprSched, setSprSched]   = useState<SprSchedule | null>(null);
  const [activeLabel, setActiveLabel] = useState<string | null>(null);

  // Seed from cache when cache arrives and no run yet
  useEffect(() => { if (cachedScenario && !scenario) setScenario(cachedScenario); }, [cachedScenario]);
  useEffect(() => { if (cachedProc && !proc) setProc(cachedProc); }, [cachedProc]);
  useEffect(() => { if (cachedSpr && !sprSched) setSprSched(cachedSpr); }, [cachedSpr]);

  const [tab, setTab]   = useState<Tab>("impact");
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [wikiNode, setWikiNode] = useState<GraphNode | null>(null);

  const openWikilink = (entity: string) =>
    setWikiNode({ id: entity, name: entity, type: "Entity", lat: null, lon: null, score: 0, band: "CALM", degree: 0 });

  // Called by ScenarioBuilder when a run finishes
  async function handleRunComplete(scenarioId: string, label: string) {
    setActiveLabel(label);
    const [sEnv, pEnv, rEnv] = await Promise.all([
      api.scenarioById(scenarioId),
      api.procurementById(scenarioId),
      api.sprScheduleById(scenarioId),
    ]);
    if (sEnv.data) {
      setScenario(sEnv.data);
      // Push to compare list (cap 3)
      const s = sEnv.data;
      setRuns((prev) => [
        ...prev.slice(-2),
        {
          runId: scenarioId,
          label,
          scenarioId,
          entity: s.trigger_entity,
          gap_mbpd: s.gap_mbpd,
          price_impact_low: s.price_impact_low,
          price_impact_high: s.price_impact_high,
          gdp_proxy_impact_pct: s.gdp_proxy_impact_pct,
          spr_depletion_days: s.spr_depletion_days,
          gap_duration_days: s.gap_duration_days ?? 0,
          timestamp: new Date().toISOString(),
        },
      ]);
    }
    if (pEnv.data) setProc(pEnv.data);
    if (rEnv.data) setSprSched(rEnv.data);
    setTab("impact");
  }

  // Voice integration
  const runTrigger = useVoice((s) => s.runScenarioTrigger);
  const drawerByVoice = useVoice((s) => s.drawerEntity);
  useEffect(() => {
    if (!runTrigger) return;
    voiceStore.setStatus(`Latest scenario for ${runTrigger}`);
    voiceStore.clearScenarioTrigger();
  }, [runTrigger]);
  useEffect(() => {
    if (!drawerByVoice) return;
    openWikilink(drawerByVoice);
    voiceStore.openDrawer(null);
  }, [drawerByVoice]);

  const nodes = (graph?.nodes ?? []).map(toRiskScore);
  const projected = scenario ? projectNodes(nodes, scenario.node_impacts ?? []) : nodes;

  const TABS: { id: Tab; label: string }[] = [
    { id: "impact",      label: "Impact" },
    { id: "cascade",     label: "Cascade" },
    { id: "procurement", label: "Procurement" },
    { id: "reserve",     label: "Reserve" },
    { id: "compare",      label: "Compare" },
    { id: "sensitivity",  label: "Sensitivity" },
    { id: "learning",     label: "Learning" },
  ];

  return (
    <div className="sim-lab">
      {/* Top control bar */}
      <div className="sim-topbar card">
        <span className="label-sm c-cyan">Anticipatory Simulation Environment</span>
        <span className="sim-scenario-pill">
          <IconShield width={14} height={14} />
          {activeLabel ?? scenario?.trigger_entity ?? "No active scenario"}
        </span>
        <Badge tone={dash ? "cyan" : "muted"}>{dash?.threat_level ?? "—"}</Badge>
        <span style={{ flex: 1 }} />
        <button className="sim-reset" onClick={() => { setScenario(cachedScenario); setProc(cachedProc); setSprSched(cachedSpr); setActiveLabel(null); }}>
          Reset to cached
        </button>
      </div>

      {/* Main grid */}
      <div className="sim-main">
        {/* Builder rail */}
        <ScenarioBuilder onRunComplete={handleRunComplete} onLoadScenarioId={handleRunComplete} />

        {/* Results pane */}
        <div className="sim-results">
          {/* Map strip */}
          <div className="sim-maps-strip">
            <div className="sim-map-mini card">
              <div className="sim-map-tag">Current State</div>
              <MapView nodes={nodes} arcs={false} interactive={false} initialView={{ longitude: 56.4, latitude: 25.5, zoom: 4 }} />
            </div>
            <div className={`sim-map-mini card${scenario ? " sim-map-predict" : ""}`}>
              <div className={`sim-map-tag${scenario ? " predict" : ""}`}>Projected ({activeLabel ?? "cached"})</div>
              {scenario && <div className="sim-map-threat"><span className="sim-blip" /> Gap: {scenario.gap_mbpd.toFixed(2)} mbpd</div>}
              <MapView nodes={projected} arcs={!!scenario} interactive={false} initialView={{ longitude: 56.4, latitude: 25.5, zoom: 4 }} />
            </div>
          </div>

          {/* Tab bar */}
          <div className="sim-tabbar">
            {TABS.map((t) => (
              <button
                key={t.id}
                className={`sim-tabbar-btn${tab === t.id ? " active" : ""}`}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* Tab panels */}
          <div className="sim-tabpanel">
            {tab === "impact" && scenario && (
              <ImpactTab scenario={scenario} onWikilink={openWikilink} />
            )}
            {tab === "impact" && !scenario && (
              <div className="sim-empty">Run a scenario or wait for the cached output to load.</div>
            )}

            {tab === "cascade" && scenario && (
              <CascadeTab scenario={scenario} onWikilink={openWikilink} />
            )}
            {tab === "cascade" && !scenario && (
              <div className="sim-empty">No scenario output yet.</div>
            )}

            {tab === "procurement" && proc && (
              <ProcurementTab proc={proc} onWikilink={openWikilink} />
            )}
            {tab === "procurement" && !proc && (
              <div className="sim-empty">Procurement data appears after running with "Run Procurement + Reserve" enabled.</div>
            )}

            {tab === "reserve" && sprSched && (
              <ReserveTab spr={sprSched} onWikilink={openWikilink} />
            )}
            {tab === "reserve" && !sprSched && (
              <div className="sim-empty">Reserve schedule appears after running with downstream enabled.</div>
            )}

            {tab === "compare" && (
              <CompareTab runs={runs} baseline={cachedScenario ?? null} />
            )}

            {tab === "sensitivity" && scenario && (
              <SensitivityTab scenario={scenario} />
            )}
            {tab === "sensitivity" && !scenario && (
              <div className="sim-empty">Run a scenario first to enable sensitivity analysis.</div>
            )}

            {tab === "learning" && <LearningTab />}
          </div>
        </div>
      </div>

      <WikiDrawer node={wikiNode} onClose={() => setWikiNode(null)} />
    </div>
  );
}
