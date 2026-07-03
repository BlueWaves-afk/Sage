import { useState } from "react";
import MapView from "../components/MapView";
import { Panel, Badge } from "../components/ui/ui";
import { IconPlay, IconCheck, IconExternal, IconShield, IconBrain } from "../components/icons";
import { api, useApi } from "../api/hooks";
import type { RiskScore } from "../api/types";
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

// The projected (escalated) state — same nodes, risk bands pushed toward CRITICAL.
function escalate(nodes: RiskScore[]): RiskScore[] {
  return nodes.map((n) => ({
    ...n,
    score: Math.min(1, n.score + 0.28),
    band: n.entity.includes("Hormuz") || n.entity.includes("Bab") ? "CRITICAL" : n.band,
  }));
}

export default function SimulationLab() {
  const { data: risk } = useApi(api.riskScores);
  const { data: scenario } = useApi(api.scenario);
  const [horizon, setHorizon] = useState(48);
  const nodes = risk ?? [];

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
            <IconShield width={14} height={14} /> Hormuz Disruption
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
          <Badge tone="cyan">Sandbox</Badge>
        </div>
        <button className="btn-run">
          <IconPlay width={13} height={13} /> Execute Run
        </button>
      </div>

      {/* Dual maps */}
      <div className="sim-maps">
        <div className="sim-map card">
          <div className="sim-map-tag">Current Reality</div>
          <MapView nodes={nodes} arcs={false} interactive={false} initialView={{ longitude: 56.4, latitude: 25.5, zoom: 5 }} />
          <div className="sim-telemetry">
            <div className="label-sm">Telemetry: T-Minus 0</div>
            <div className="sim-telemetry-row">
              <span>Vessels:</span>
              <span className="c-cyan mono">412</span>
            </div>
            <div className="sim-telemetry-row">
              <span>Flow Rate:</span>
              <span className="c-cyan mono">18.2M bpd</span>
            </div>
          </div>
        </div>
        <div className="sim-map card sim-map-predict">
          <div className="sim-map-tag predict">AI Sandbox Prediction (+{horizon} Hours)</div>
          <div className="sim-map-threat">
            <span className="sim-blip" /> Threat Level: CRITICAL
          </div>
          <MapView nodes={escalate(nodes)} arcs interactive={false} initialView={{ longitude: 56.4, latitude: 25.5, zoom: 5 }} />
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
        <Panel className="sim-summary" title="AI Simulation Summary" right={<Badge tone="cyan">{Math.round((scenario?.confidence ?? 0.91) * 100)}% Confidence</Badge>}>
          <div className="sim-summary-grid">
            <div>
              <div className="label-sm">Predicted Chain of Events</div>
              <ul className="sim-chain">
                {(scenario?.chain_of_events ?? []).map((e) => (
                  <li key={e}>{e}</li>
                ))}
              </ul>
            </div>
            <div>
              <div className="label-sm">Key Assumptions</div>
              <p className="sim-assumption">{scenario?.assumptions?.[0]}</p>
              <a className="sim-why" href="#">
                Why this prediction? <IconExternal width={13} height={13} />
              </a>
            </div>
          </div>
        </Panel>

        <Panel
          className="sim-action"
          title="AI Recommended Action"
          right={<Badge tone="cyan">Priority Action</Badge>}
        >
          <div className="sim-action-item">
            <div className="sim-action-head">
              <IconCheck width={16} height={16} className="c-cyan" />
              <span>UAE Emergency Procurement Cluster</span>
            </div>
            <p>
              Initiate immediate 72-hour purchase window for high-grade crude from UAE storage
              terminals via land-bypass pipeline to Fujairah.
            </p>
          </div>
          <div className="sim-action-item">
            <div className="sim-action-head">
              <IconShield width={16} height={16} className="c-cyan" />
              <span>Strategic Petroleum Reserve Activation</span>
            </div>
            <p>
              Authorize release of Tier-1 reserves from Vishakhapatnam and Padur to maintain 48-hour
              refinery continuity.
            </p>
          </div>
        </Panel>
      </div>

      {/* Impact horizon timeline */}
      <Panel className="sim-horizon" title={<span><IconBrain width={13} height={13} /> Impact Horizon Timeline</span>}>
        <div className="sim-horizon-track">
          {(scenario?.timeline ?? []).map((t) => (
            <div key={t.hour} className="sim-horizon-item">
              <span className={`sim-horizon-dot${t.critical ? " crit" : ""}`} />
              <div className={`sim-horizon-hour${t.critical ? " c-coral" : ""}`}>Hour {t.hour}</div>
              <div className="sim-horizon-label">{t.label}</div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
