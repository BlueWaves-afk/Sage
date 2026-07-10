import { useState } from "react";
import ScoreBreakdown from "./ScoreBreakdown";
import { RichText } from "../RichText";
import { Badge } from "../ui/ui";
import type { ProcurementRecData, ProcurementOption } from "../../api/types";

interface Props {
  proc: ProcurementRecData;
  onWikilink: (entity: string) => void;
}

export default function ProcurementTab({ proc, onWikilink }: Props) {
  const [selIdx, setSelIdx] = useState(0);
  const ranked = proc.ranked ?? [];
  const sel: ProcurementOption | null = ranked[selIdx] ?? null;

  return (
    <div className="sim-tab-content">
      {proc.target_refinery && (
        <div className="sim-section">
          <span className="label-sm">Target Refinery: </span>
          <span className="c-cyan mono">{proc.target_refinery}</span>
        </div>
      )}

      <div className="sim-section">
        <div className="label-sm">TOPSIS-Ranked Procurement Options</div>
        <div className="sim-table-wrap">
          <table className="sim-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Supplier</th>
                <th>Grade</th>
                <th>Route</th>
                <th>$/bbl</th>
                <th>Lead</th>
                <th>TOPSIS</th>
              </tr>
            </thead>
            <tbody>
              {ranked.map((r, i) => (
                <tr
                  key={i}
                  className={selIdx === i ? "sim-tr-selected" : ""}
                  onClick={() => setSelIdx(i)}
                  style={{ cursor: "pointer" }}
                >
                  <td className="mono" style={{ color: i === 0 ? "var(--cyan)" : "var(--text-2)" }}>
                    {i === 0 ? "★" : i + 1}
                  </td>
                  <td className={i === 0 ? "c-cyan" : ""}>{r.supplier}</td>
                  <td style={{ fontSize: 11 }}>{r.grade}</td>
                  <td style={{ fontSize: 11, color: "var(--text-2)" }}>{r.route_via}</td>
                  <td className="mono">${r.landed_cost_usd_bbl.toFixed(1)}</td>
                  <td className="mono">{r.lead_time_days}d</td>
                  <td>
                    <div className="sim-bar-wrap">
                      <div className="sim-bar sim-bar-cyan" style={{ width: `${Math.round(r.topsis_score * 100)}%` }} />
                      <span className="mono" style={{ fontSize: 10, marginLeft: 4 }}>{r.topsis_score.toFixed(3)}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {sel && (
        <div className="sim-proc-detail">
          <div className="sim-section">
            <div className="label-sm">Score Breakdown — {sel.supplier}</div>
            <ScoreBreakdown option={sel} />
          </div>
          <div className="sim-section">
            <div className="label-sm">Rationale</div>
            <RichText text={sel.rationale} onWikilink={onWikilink} />
          </div>
        </div>
      )}

      <div style={{ marginTop: 8 }}>
        <Badge tone={proc.status === "confirmed" ? "cyan" : "muted"}>{proc.status}</Badge>
      </div>
    </div>
  );
}
