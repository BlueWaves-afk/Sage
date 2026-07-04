import { useEffect, useState } from "react";
import { Panel, Badge, Skel, SkeletonBlock } from "../components/ui/ui";
import { IconShield, IconCheck, IconAlert, IconExternal } from "../components/icons";
import WikiDrawer from "../components/WikiDrawer";
import { RichText } from "../components/RichText";
import { api, useApi } from "../api/hooks";
import type { ProcurementOption, GraphNode } from "../api/types";
import { useVoice, voiceStore } from "../voice/useVoiceStore";
import "./response.css";

const AXES: { key: keyof ProcurementOption; label: string; invert?: boolean; max: number }[] = [
  { key: "grade_compatibility", label: "Grade Fit", max: 1 },
  { key: "corridor_risk", label: "Route Safety", invert: true, max: 1 },
  { key: "landed_cost_usd_bbl", label: "Cost", invert: true, max: 100 },
  { key: "lead_time_days", label: "Speed", invert: true, max: 14 },
  { key: "topsis_score", label: "TOPSIS", max: 1 },
];

// Radar chart across 5 normalised axes. The active (clicked) option is drawn bold
// and filled; every other option renders as a faint reference outline behind it,
// so picking a card always re-focuses the diagram on that option specifically —
// including options outside the top 3.
function Radar({
  options,
  activeSupplier,
}: {
  options: ProcurementOption[];
  activeSupplier: string | null;
}) {
  const size = 300;
  const cx = size / 2;
  const cy = size / 2;
  const R = 110;
  const n = AXES.length;

  const point = (i: number, r: number) => {
    const a = (Math.PI * 2 * i) / n - Math.PI / 2;
    return [cx + Math.cos(a) * r, cy + Math.sin(a) * r];
  };
  const norm = (opt: ProcurementOption, ax: (typeof AXES)[number]) => {
    const v = Number(opt[ax.key]);
    const frac = Math.min(1, Math.max(0, v / ax.max));
    return ax.invert ? 1 - frac : frac;
  };
  const shapeOf = (opt: ProcurementOption) => AXES.map((ax, i) => point(i, R * norm(opt, ax)).join(",")).join(" ");

  const active = options.find((o) => o.supplier === activeSupplier) ?? options[0];

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

      {/* Faint reference outlines for every other option — context, not competing */}
      {options
        .filter((o) => o.supplier !== active?.supplier)
        .map((opt) => (
          <polygon
            key={opt.supplier}
            points={shapeOf(opt)}
            fill="none"
            stroke="#4b5568"
            strokeWidth={1}
            strokeOpacity={0.45}
          />
        ))}

      {/* The active option — bold, filled, animates in on change */}
      {active && (
        <polygon
          key={`active-${active.supplier}`}
          className="radar-active-shape"
          points={shapeOf(active)}
          fill="#38c6ee"
          fillOpacity={0.16}
          stroke="#38c6ee"
          strokeWidth={2.5}
        />
      )}
    </svg>
  );
}

export default function ResponsePlanner() {
  const { data: procurement, live: pLive } = useApi(api.procurement);
  const { data: schedule, live: sLive } = useApi(api.sprSchedule);
  const options = pLive ? procurement?.ranked ?? [] : [];
  const dailyPlan = schedule?.daily_plan ?? [];
  const [wikiNode, setWikiNode] = useState<GraphNode | null>(null);
  const openWikilink = (entity: string) =>
    setWikiNode({ id: entity, name: entity, type: "Entity", lat: null, lon: null, score: 0, band: "CALM", degree: 0 });
  const maxReserve = Math.max(1, ...dailyPlan.map((d) => d.days_cover_after));

  // Which procurement option the radar currently focuses on — defaults to #1,
  // and updates whenever a card is clicked (any card, not just the top 3).
  const [activeSupplier, setActiveSupplier] = useState<string | null>(null);
  const active = activeSupplier ?? options[0]?.supplier ?? null;

  // Voice `select_option` action — resolved with a lenient case-insensitive
  // startsWith match so "select ADNOC" hits the ADNOC card without requiring
  // exact string equality with whatever the STT capitalization was.
  const supplierByVoice = useVoice((s) => s.activeSupplier);
  useEffect(() => {
    if (!supplierByVoice) return;
    const q = supplierByVoice.toLowerCase();
    const match = options.find((o) =>
      o.supplier.toLowerCase() === q || o.supplier.toLowerCase().startsWith(q)
    );
    if (match) setActiveSupplier(match.supplier);
    voiceStore.selectSupplier(null);
  }, [supplierByVoice, options]);

  const drawerByVoice = useVoice((s) => s.drawerEntity);
  useEffect(() => {
    if (!drawerByVoice) return;
    setWikiNode({ id: drawerByVoice, name: drawerByVoice, type: "Entity", lat: null, lon: null, score: 0, band: "CALM", degree: 0 });
    voiceStore.openDrawer(null);
  }, [drawerByVoice]);

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
              <Radar options={options} activeSupplier={active} />
              <div className="rp-legend">
                <span className="rp-legend-item rp-legend-active">
                  <span className="rp-legend-dot" style={{ background: "#38c6ee" }} />
                  {options.find((o) => o.supplier === active)?.supplier ?? "—"}
                </span>
                <span className="rp-legend-item rp-legend-muted">
                  <span className="rp-legend-dot rp-legend-dot-outline" />
                  other options
                </span>
              </div>
            </div>
            <div className="rp-options">
              {options.map((o, i) => (
                // A div (not <button>) — RichText renders clickable wikilink
                // <button>s inside the rationale, and nesting <button> inside
                // <button> is invalid HTML. Keyboard-accessible via role+tabIndex.
                <div
                  key={o.supplier}
                  className={`rp-option${o.supplier === active ? " top" : ""}`}
                  role="button"
                  tabIndex={0}
                  aria-pressed={o.supplier === active}
                  onClick={() => setActiveSupplier(o.supplier)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setActiveSupplier(o.supplier);
                    }
                  }}
                >
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
                  {o.rationale && (
                    <p className="rp-option-rationale">
                      <RichText text={o.rationale} onWikilink={openWikilink} />
                    </p>
                  )}
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
        right={
          sLive && schedule ? (
            <Badge tone={schedule.constraint_satisfied ? "green" : "red"}>
              {Math.round(schedule.prob_above_buffer * 100)}% above 3-day buffer
            </Badge>
          ) : (
            <Skel w={140} h={22} />
          )
        }
      >
        {!sLive || !schedule ? (
          <SkeletonBlock lines={5} note="Day-by-day drawdown plan appears after System 4 runs against a scenario" />
        ) : (
        <div className="rp-spr-body">
          <div className="rp-chart">
            {dailyPlan.slice(0, 14).map((d) => (
              <div key={d.day} className="rp-bar-col">
                <div className="rp-bar-wrap">
                  <div
                    className={`rp-bar${d.days_cover_after < 3 ? " warn" : ""}`}
                    style={{ height: `${(d.days_cover_after / maxReserve) * 100}%` }}
                  >
                    <span className="rp-bar-value mono">{d.days_cover_after.toFixed(1)}</span>
                  </div>
                </div>
                <div className="rp-bar-day">Day {d.day}</div>
                <div className="rp-bar-action">{d.action}</div>
              </div>
            ))}
          </div>
          <div className="rp-memo">
            <div className="label-sm">Policy Memo</div>
            <p><RichText text={schedule.policy_memo} onWikilink={openWikilink} /></p>
            <div className="rp-memo-foot">
              <span className="rp-memo-item">
                {schedule.constraint_satisfied ? (
                  <><IconCheck width={13} height={13} className="c-green" /> CMDP constraint satisfied</>
                ) : (
                  <><IconAlert width={13} height={13} className="c-red" /> CMDP constraint NOT satisfied — diversify procurement</>
                )}
              </span>
              <a href="#" className="rp-memo-link">Full drawdown model <IconExternal width={12} height={12} /></a>
            </div>
          </div>
        </div>
        )}
      </Panel>

      <WikiDrawer node={wikiNode} onClose={() => setWikiNode(null)} />
    </div>
  );
}
