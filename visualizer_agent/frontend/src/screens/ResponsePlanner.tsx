import { Panel, Badge, Skel, SkeletonBlock } from "../components/ui/ui";
import { IconShield, IconCheck, IconExternal } from "../components/icons";
import { api, useApi } from "../api/hooks";
import type { ProcurementOption } from "../api/types";
import "./response.css";

const AXES: { key: keyof ProcurementOption; label: string; invert?: boolean; max: number }[] = [
  { key: "grade_compatibility", label: "Grade Fit", max: 1 },
  { key: "corridor_risk", label: "Route Safety", invert: true, max: 1 },
  { key: "landed_cost_usd_bbl", label: "Cost", invert: true, max: 100 },
  { key: "lead_time_days", label: "Speed", invert: true, max: 14 },
  { key: "topsis_score", label: "TOPSIS", max: 1 },
];

// Radar chart comparing the top-3 procurement options across 5 normalised axes.
function Radar({ options }: { options: ProcurementOption[] }) {
  const size = 300;
  const cx = size / 2;
  const cy = size / 2;
  const R = 110;
  const n = AXES.length;
  const colors = ["#38c6ee", "#34d38a", "#f5a623"];

  const point = (i: number, r: number) => {
    const a = (Math.PI * 2 * i) / n - Math.PI / 2;
    return [cx + Math.cos(a) * r, cy + Math.sin(a) * r];
  };
  const norm = (opt: ProcurementOption, ax: (typeof AXES)[number]) => {
    const v = Number(opt[ax.key]);
    const frac = Math.min(1, Math.max(0, v / ax.max));
    return ax.invert ? 1 - frac : frac;
  };

  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="radar">
      {[0.25, 0.5, 0.75, 1].map((ring) => (
        <polygon
          key={ring}
          points={AXES.map((_, i) => point(i, R * ring).join(",")).join(" ")}
          fill="none"
          stroke="#21344f"
          strokeWidth={1}
        />
      ))}
      {AXES.map((ax, i) => {
        const [x, y] = point(i, R);
        const [lx, ly] = point(i, R + 24);
        return (
          <g key={ax.label}>
            <line x1={cx} y1={cy} x2={x} y2={y} stroke="#21344f" strokeWidth={1} />
            <text x={lx} y={ly} className="radar-axis" textAnchor="middle" dominantBaseline="middle">
              {ax.label}
            </text>
          </g>
        );
      })}
      {options.slice(0, 3).map((opt, oi) => (
        <polygon
          key={opt.supplier}
          points={AXES.map((ax, i) => point(i, R * norm(opt, ax)).join(",")).join(" ")}
          fill={colors[oi]}
          fillOpacity={0.12}
          stroke={colors[oi]}
          strokeWidth={2}
        />
      ))}
    </svg>
  );
}

export default function ResponsePlanner() {
  const { data: procurement, live: pLive } = useApi(api.procurement);
  const { data: schedule, live: sLive } = useApi(api.sprSchedule);
  const options = pLive ? procurement ?? [] : [];
  const maxReserve = Math.max(...(schedule?.drawdown ?? [{ reserve_days: 10 }]).map((d) => d.reserve_days));

  return (
    <div className="rp">
      <div className="rp-top">
        {/* Procurement ranking */}
        <Panel
          className="rp-proc"
          title="Alternative Procurement — TOPSIS Ranking"
          right={<Badge tone={pLive ? "green" : "muted"}>{pLive ? "LIVE" : "AWAITING RUN"}</Badge>}
        >
          {!pLive ? (
            <SkeletonBlock lines={4} note="TOPSIS ranking appears after System 3 runs against a scenario" />
          ) : (
          <div className="rp-proc-body">
            <div className="rp-radar-wrap">
              <Radar options={options} />
              <div className="rp-legend">
                {options.slice(0, 3).map((o, i) => (
                  <div key={o.supplier} className="rp-legend-item">
                    <span className="rp-legend-dot" style={{ background: ["#38c6ee", "#34d38a", "#f5a623"][i] }} />
                    {o.supplier}
                  </div>
                ))}
              </div>
            </div>
            <div className="rp-options">
              {options.map((o, i) => (
                <div key={o.supplier} className={`rp-option${i === 0 ? " top" : ""}`}>
                  <div className="rp-option-head">
                    <span className="rp-rank">#{i + 1}</span>
                    <div className="rp-option-name">
                      <span>{o.supplier}</span>
                      <span className="rp-grade">{o.grade}</span>
                    </div>
                    <span className="rp-topsis c-cyan">{o.topsis_score.toFixed(2)}</span>
                  </div>
                  <div className="rp-option-metrics">
                    <span>via {o.route_via}</span>
                    <span className="mono">${o.landed_cost_usd_bbl.toFixed(1)}/bbl</span>
                    <span className="mono">{o.lead_time_days}d</span>
                    <span className="mono">compat {o.grade_compatibility.toFixed(2)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
          )}
        </Panel>
      </div>

      {/* SPR drawdown schedule */}
      <Panel
        className="rp-spr"
        title={<span><IconShield width={13} height={13} /> Strategic Reserve Drawdown Schedule</span>}
        right={sLive ? <Badge tone="green">{Math.round((schedule?.buffer_probability ?? 0) * 100)}% above 3-day buffer</Badge> : <Skel w={140} h={22} />}
      >
        {!sLive ? (
          <SkeletonBlock lines={5} note="Day-by-day drawdown plan appears after System 4 runs against a scenario" />
        ) : (
        <div className="rp-spr-body">
          <div className="rp-chart">
            {(schedule?.drawdown ?? []).map((d) => (
              <div key={d.day} className="rp-bar-col">
                <div className="rp-bar-wrap">
                  <div
                    className={`rp-bar${d.reserve_days < 8 ? " warn" : ""}`}
                    style={{ height: `${(d.reserve_days / maxReserve) * 100}%` }}
                  >
                    <span className="rp-bar-value mono">{d.reserve_days.toFixed(1)}</span>
                  </div>
                </div>
                <div className="rp-bar-day">Day {d.day}</div>
                <div className="rp-bar-action">{d.action}</div>
              </div>
            ))}
          </div>
          <div className="rp-memo">
            <div className="label-sm">Policy Memo</div>
            <p>{schedule?.memo}</p>
            <div className="rp-memo-foot">
              <span className="rp-memo-item"><IconCheck width={13} height={13} className="c-green" /> CMDP constraint satisfied</span>
              <a href="#" className="rp-memo-link">Full drawdown model <IconExternal width={12} height={12} /></a>
            </div>
          </div>
        </div>
        )}
      </Panel>
    </div>
  );
}
