import { useState } from "react";
import MapView from "../components/MapView";
import { Panel, Badge, Meter } from "../components/ui/ui";
import { IconBrain, IconCheck } from "../components/icons";
import { api, useApi } from "../api/hooks";
import "./intelligence.css";

const LAYERS = ["Ships", "Ports", "Pipelines", "Shipping Routes", "Risk Nodes", "Refineries", "SPR"];
const NETWORK = ["HORMUZ", "SAUDI ARABIA", "JAMNAGAR", "INDIAN SPR"];
const TIMELINE = [
  { time: "08:00", label: "US Sanctions", tone: "c-cyan" },
  { time: "10:45", label: "Vessel Delay", tone: "c-muted" },
  { time: "12:30", label: "Brent Spike", tone: "c-coral" },
  { time: "CURRENT", label: "Risk Alert", tone: "c-cyan" },
];

export default function GlobalIntelligence() {
  const [activeLayers, setActiveLayers] = useState<string[]>(["Ships", "Pipelines", "Shipping Routes"]);
  const { data: risk } = useApi(api.riskScores);

  const toggle = (l: string) =>
    setActiveLayers((a) => (a.includes(l) ? a.filter((x) => x !== l) : [...a, l]));

  return (
    <div className="gi">
      {/* Map column */}
      <div className="gi-map-col">
        <div className="gi-breadcrumb mono">
          WORLD <span className="gi-sep">›</span> MIDDLE EAST <span className="gi-sep">›</span>{" "}
          PERSIAN GULF <span className="gi-sep">›</span>{" "}
          <span className="c-cyan">STRAIT OF HORMUZ</span>
        </div>
        <div className="gi-tabs">
          {LAYERS.map((l) => (
            <button
              key={l}
              className={`gi-tab${activeLayers.includes(l) ? " active" : ""}`}
              onClick={() => toggle(l)}
            >
              {l}
            </button>
          ))}
        </div>
        <div className="gi-map card">
          <MapView
            nodes={risk ?? []}
            initialView={{ longitude: 56.4, latitude: 26.5, zoom: 6 }}
          />
        </div>
      </div>

      {/* Briefing column */}
      <aside className="gi-brief">
        <div className="gi-brief-head">
          <span className="gi-brief-title">
            <IconBrain width={18} height={18} className="c-cyan" /> SAGE Briefing
          </span>
          <span className="mono gi-ver">VER: SAGE-V4.2</span>
        </div>

        <div className="gi-section">
          <div className="label-sm">Current Situation</div>
          <p className="gi-situation">
            Recent naval exercises in the northern corridor, combined with regional policy shifts, have
            introduced a 15% increase in transit latency. Sentiment analysis of carrier-owner
            communications indicates growing caution regarding insurance premium stability for Q3.
          </p>
        </div>

        <div className="gi-metrics">
          <div className="gi-metric card gi-metric-amber">
            <div className="label-sm">Threat Level</div>
            <div className="gi-metric-value c-amber">
              ELEVATED <span className="gi-blip" />
            </div>
          </div>
          <div className="gi-metric card">
            <div className="label-sm">Confidence</div>
            <div className="gi-metric-value c-cyan">94%</div>
            <Meter value={0.94} />
          </div>
        </div>

        <div className="gi-section">
          <div className="label-sm">Supporting Evidence</div>
          <div className="gi-evidence">
            {["Reuters", "AIS Live", "OFAC"].map((s) => (
              <span key={s} className="gi-evidence-chip">
                <IconCheck width={13} height={13} className="c-cyan" /> {s}
              </span>
            ))}
          </div>
          <div className="gi-updated mono">
            <span>LAST UPDATED: 14:22:08 UTC</span>
            <span>SYNCED 2M AGO</span>
          </div>
        </div>

        <button className="gi-why">
          <IconBrain width={15} height={15} /> Why does SAGE think this?
        </button>

        <div className="gi-section">
          <div className="label-sm">Connected Network</div>
          <div className="gi-network">
            {NETWORK.map((n, i) => (
              <div key={n} className="gi-node-wrap">
                <div className="gi-node">
                  <span className="gi-node-dot" />
                  <span className="gi-node-name">{n}</span>
                </div>
                {i < NETWORK.length - 1 && <span className="gi-node-link">›</span>}
              </div>
            ))}
          </div>
        </div>

        <div className="gi-section">
          <div className="label-sm">Event Timeline</div>
          <div className="gi-timeline">
            {TIMELINE.map((e) => (
              <div key={e.label} className="gi-tl-item">
                <span className={`gi-tl-dot ${e.tone}`} />
                <span className="gi-tl-time mono">{e.time}</span>
                <span className={`gi-tl-label ${e.tone}`}>{e.label}</span>
              </div>
            ))}
          </div>
        </div>
      </aside>
    </div>
  );
}
