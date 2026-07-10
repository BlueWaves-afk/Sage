import { useState } from "react";
import SectorWaterfall from "./SectorWaterfall";
import type { ScenarioOutput, GraphNode } from "../../api/types";

interface Props {
  scenario: ScenarioOutput;
  onWikilink: (entity: string) => void;
}

export default function CascadeTab({ scenario, onWikilink }: Props) {
  const [selected, setSelected] = useState<string | null>(null);
  const nodes = [...(scenario.node_impacts ?? [])].sort((a, b) => b.peak_gap_mbpd - a.peak_gap_mbpd);
  const sectors = scenario.sector_impacts ?? [];
  const abm = (scenario.assumptions as unknown as Record<string, unknown>)?.abm_emergent as Record<string, unknown> | undefined;

  return (
    <div className="sim-tab-content">
      {/* Node cascade table */}
      <div className="sim-section">
        <div className="label-sm">Node Cascade — by Peak Gap</div>
        <div className="sim-table-wrap">
          <table className="sim-table">
            <thead>
              <tr>
                <th>Node</th>
                <th>Type</th>
                <th>Exposure</th>
                <th>Peak Gap</th>
                <th>Onset</th>
              </tr>
            </thead>
            <tbody>
              {nodes.map((n) => (
                <tr
                  key={n.node}
                  className={selected === n.node ? "sim-tr-selected" : ""}
                  onClick={() => { setSelected(n.node); onWikilink(n.node); }}
                  style={{ cursor: "pointer" }}
                >
                  <td className="c-cyan mono">{n.node}</td>
                  <td style={{ color: "var(--text-2)", fontSize: 11 }}>{n.node_type}</td>
                  <td>
                    <div className="sim-bar-wrap">
                      <div className="sim-bar" style={{ width: `${Math.round(n.exposure * 100)}%` }} />
                      <span className="mono" style={{ fontSize: 10, marginLeft: 4 }}>{(n.exposure * 100).toFixed(0)}%</span>
                    </div>
                  </td>
                  <td className="c-amber mono">{n.peak_gap_mbpd.toFixed(3)}</td>
                  <td className="mono" style={{ fontSize: 11 }}>Day {n.onset_day}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Sector waterfall */}
      {sectors.length > 0 && (
        <div className="sim-section">
          <div className="label-sm">Leontief IO Sector Cascade — Shortfall (mbpd)</div>
          <SectorWaterfall sectors={sectors} />
        </div>
      )}

      {/* ABM emergent callout */}
      {abm && (
        <div className="sim-callout">
          <span className="label-sm c-amber">ABM Emergent:</span>{" "}
          {String(abm.rationing_refineries ?? "N")} refineries rationing ·{" "}
          bypass utilisation {String(abm.bypass_utilisation ?? "—")}% ·{" "}
          stabilises in {String(abm.stabilisation_days ?? "—")} days
        </div>
      )}
    </div>
  );
}
