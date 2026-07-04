import { useMemo, useState } from "react";
import MapView from "../components/MapView";
import { Panel, Badge, Skel, SkeletonBlock } from "../components/ui/ui";
import { IconPlay, IconCheck, IconExternal, IconShield, IconBrain } from "../components/icons";
import { api, useApi } from "../api/hooks";
import type { GraphNode, RiskScore, NodeImpact } from "../api/types";
import "./simulation.css";

const LAYERS = [
  { name: "Ships", on: true },
  { name: "Ports", on: true },
  { name: "Pipelines", on: false },
  { name: "Shipping Routes", on: true },
  { name: "Risk Nodes", on: true, tone: "coral" },
  { name: "Refineries", on: false },
  { name: "SPR", on: false },
  { name: "Corridors", on: false },
];

function toRiskScore(n: GraphNode): RiskScore {
  return {
    entity: n.name,
    score: n.score,
    band: n.band,
    factors: { ais: 0, gdelt: 0, price: 0, sanctions: 0 },
    lat: n.lat ?? undefined,
    lon: n.lon ?? undefined,
  };
}

// Project nodes forward using the REAL per-node exposure from System 2's cascade
// (node_impacts), not a hardcoded name match. A node with no computed exposure is
// left exactly as-is — the projection only shows where the model actually predicts
// spread, so the two maps can never silently contradict each other.
function projectNodes(nodes: RiskScore[], nodeImpacts: NodeImpact[]): RiskScore[] {
  const byName = new Map(nodeImpacts.map((n) => [n.node, n]));
  return nodes.map((n) => {
    const impact = byName.get(n.entity);
    if (!impact) return n;
    const projected = Math.min(1, n.score + impact.exposure * 0.4);
    const band =
      projected >= 0.9 ? "CRITICAL" : projected >= 0.7 ? "ACTION" : projected >= 0.45 ? "ELEVATED" : n.band;
    return { ...n, score: projected, band };
  });
}

export default function SimulationLab() {
  const { data: graph } = useApi(api.graph);
  const { data: scenario, live: scenLive } = useApi(api.scenario);
  const { data: dash, live: dashLive } = useApi(api.dashboard);
  const { data: proc, live: procLive } = useApi(api.procurement);
  const { data: sched, live: schedLive } = useApi(api.sprSchedule);
  const [horizon, setHorizon] = useState(48);

  const nodes = useMemo(() => (graph?.nodes ?? []).map(toRiskScore), [graph]);
  const projected = useMemo(
    () => (scenLive ? projectNodes(nodes, scenario?.node_impacts ?? []) : nodes),
    [nodes, scenario, scenLive]
  );

  const topOption = proc?.ranked?.[0] ?? null;

  // Timeline built from real System 2 output: onset of disruption, day of peak
  // feedstock gap, SPR depletion day, and when the disruption subsides — not an
  // invented "Insurance Surges / Terminal Delays" narrative.
  const horizonPoints = useMemo(() => {
    if (!scenLive || !scenario) return [];
    const gapTimeline = scenario.feedstock_gap_timeline ?? [];
    const peakDay = gapTimeline.length
      ? gapTimeline.indexOf(Math.max(...gapTimeline))
      : 0;
    const points = [
      { day: 0, label: "Disruption Begins", critical: false },
      { day: peakDay, label: `Peak Supply Gap (${scenario.gap_mbpd.toFixed(2)} mbpd)`, critical: true },
    ];
    if (scenario.spr_depletion_days < (scenario.gap_duration_days ?? 0) + 15) {
      points.push({ day: Math.round(scenario.spr_depletion_days), label: "SPR Reaches Floor", critical: true });
    }
    points.push({ day: Math.round(scenario.gap_duration_days ?? 0), label: "Gap Subsides", critical: false });
    return points;
  }, [scenario, scenLive]);

  return (
    <div className="sim">
      {/* Control bar */}
      <div className="sim-controls card">
        <div className="sim-env">
          <span className="label-sm c-cyan">Anticipatory Sandbox Environment</span>
        </div>
        <div className="sim-scenario">
          <span className="label-sm">Scenario:</span>
          <span className="sim-scenario-pill">
            <IconShield width={14} height={14} /> {scenario?.trigger_entity ?? "No active scenario"}
          </span>
        </div>
        <div className="sim-scrubber">
          <div className="sim-scrubber-labels">
            {["Now", "24h", "48h", "72h"].map((t) => (
              <span key={t}>{t}</span>
            ))}
          </div>
          <input
            type="range"
            min={0}
            max={72}
            step={12}
            value={horizon}
            onChange={(e) => setHorizon(Number(e.target.value))}
            className="sim-range"
          />
        </div>
        <div className="sim-mode">
          <span className="label-sm">Mode:</span>
          <Badge tone={scenLive ? "cyan" : "muted"}>{scenLive ? scenario?.status ?? "Sandbox" : "No live scenario"}</Badge>
        </div>
        <button className="btn-run press">
          <span className="btn-run-sheen" />
          <IconPlay width={13} height={13} /> Execute Run
        </button>
      </div>

      {/* Dual maps */}
      <div className="sim-maps">
        <div className="sim-map card">
          <div className="sim-map-tag">Current State</div>
          <MapView nodes={nodes} arcs={false} interactive={false} initialView={{ longitude: 56.4, latitude: 25.5, zoom: 5 }} />
          <div className="sim-telemetry">
            <div className="label-sm">Live Threat Level</div>
            <div className="sim-telemetry-row">
              <span>Status:</span>
              {dashLive ? (
                <span className="c-cyan mono">{dash?.threat_level}</span>
              ) : (
                <Skel w={70} h={13} />
              )}
            </div>
            <div className="sim-telemetry-row">
              <span>Tracked entities:</span>
              {dashLive ? (
                <span className="c-cyan mono">{dash?.monitoring_entities}</span>
              ) : (
                <Skel w={40} h={13} />
              )}
            </div>
          </div>
        </div>
        <div className={`sim-map card${scenLive ? " sim-map-predict" : ""}`}>
          <div className={`sim-map-tag${scenLive ? " predict" : ""}`}>
            AI Sandbox Projection (+{horizon}h)
          </div>
          {scenLive ? (
            <div className="sim-map-threat">
              <span className="sim-blip" /> Projected Gap: {scenario?.gap_mbpd.toFixed(2)} mbpd
            </div>
          ) : (
            <div className="sim-map-threat" style={{ color: "var(--text-3)", borderColor: "var(--border-2)" }}>
              No live scenario to project
            </div>
          )}
          <MapView
            nodes={projected}
            arcs={scenLive}
            interactive={false}
            initialView={{ longitude: 56.4, latitude: 25.5, zoom: 5 }}
          />
        </div>
        <aside className="sim-layers card">
          <div className="label">Map Layers</div>
          {LAYERS.map((l) => (
            <label key={l.name} className="sim-layer">
              <span className="sim-layer-name">{l.name}</span>
              <span className={`sim-check${l.on ? " on" : ""}${l.tone === "coral" ? " coral" : ""}`}>
                {l.on && <IconCheck width={12} height={12} />}
              </span>
            </label>
          ))}
          <div className="sim-layer-actions">
            <button className="sim-layer-btn">Zoom In +</button>
            <button className="sim-layer-btn">Zoom Out −</button>
            <button className="sim-layer-btn">Reset View ↺</button>
            <button className="sim-layer-btn">Locate India ⌖</button>
          </div>
        </aside>
      </div>

      {/* Summary + action */}
      <div className="sim-lower">
        <Panel
          className="sim-summary"
          title="AI Simulation Summary"
          right={scenLive ? <Badge tone="cyan">{Math.round((scenario?.confidence ?? 0) * 100)}% Confidence</Badge> : <Skel w={100} h={22} />}
        >
          {scenLive && scenario ? (
            <div className="sim-summary-grid">
              <div>
                <div className="label-sm">Sectoral Impact (shortfall, mbpd)</div>
                <ul className="sim-chain">
                  {scenario.sector_impacts.slice(0, 4).map((s) => (
                    <li key={s.sector}>
                      <strong style={{ textTransform: "capitalize" }}>{s.sector}</strong>: {s.shortfall_mbpd.toFixed(2)} mbpd
                      (criticality {s.criticality.toFixed(2)})
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <div className="label-sm">Key Assumptions</div>
                {Object.entries(scenario.assumptions)
                  .slice(0, 3)
                  .map(([key, v]) => (
                    <p key={key} className="sim-assumption" style={{ margin: "0 0 6px" }}>
                      <strong>{key.replace(/_/g, " ")}</strong>: {String(v.value)}
                      {v.unit ? ` ${v.unit}` : ""} <span className="c-dim">({v.source})</span>
                    </p>
                  ))}
                <a className="sim-why" href="#">
                  Why this prediction? <IconExternal width={13} height={13} />
                </a>
              </div>
            </div>
          ) : (
            <SkeletonBlock note="Run a scenario to populate — no cached System 2 output" />
          )}
        </Panel>

        <Panel
          className="sim-action"
          title="AI Recommended Action"
          right={scenLive ? <Badge tone="cyan">Priority Action</Badge> : <Skel w={90} h={22} />}
        >
          {procLive && topOption ? (
            <div className="sim-action-item">
              <div className="sim-action-head">
                <IconCheck width={16} height={16} className="c-cyan" />
                <span>{topOption.supplier} via {topOption.route_via}</span>
              </div>
              <p>{topOption.rationale}</p>
            </div>
          ) : (
            <SkeletonBlock lines={2} note="Recommended actions appear once System 3 runs against a scenario" />
          )}
          {schedLive && sched ? (
            <div className="sim-action-item">
              <div className="sim-action-head">
                <IconShield width={16} height={16} className="c-cyan" />
                <span>Strategic Petroleum Reserve — {sched.constraint_satisfied ? "Constraint OK" : "Constraint at risk"}</span>
              </div>
              <p>{sched.policy_memo}</p>
            </div>
          ) : (
            <SkeletonBlock lines={2} note="Reserve policy appears once System 4 runs against a scenario" />
          )}
        </Panel>
      </div>

      {/* Impact horizon timeline */}
      <Panel className="sim-horizon" title={<span><IconBrain width={13} height={13} /> Impact Horizon Timeline</span>}>
        <div className="sim-horizon-track">
          {!scenLive
            ? [0, 1, 2, 3].map((i) => (
                <div key={i} className="sim-horizon-item">
                  <span className="sim-horizon-dot" style={{ opacity: 0.3 }} />
                  <Skel w={60} h={13} />
                  <Skel w={90} h={11} />
                </div>
              ))
            : horizonPoints.map((t) => (
                <div key={t.label} className="sim-horizon-item">
                  <span className={`sim-horizon-dot${t.critical ? " crit" : ""}`} />
                  <div className={`sim-horizon-hour${t.critical ? " c-coral" : ""}`}>Day {t.day}</div>
                  <div className="sim-horizon-label">{t.label}</div>
                </div>
              ))}
        </div>
      </Panel>
    </div>
  );
}
