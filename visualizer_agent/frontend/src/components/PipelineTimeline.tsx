/**
 * Feature #5 — Alert → Recommendation timeline ribbon.
 * Horizontal visual: Signal → Risk → Scenario → Procurement → SPR
 * with measured per-stage deltas from /api/response-time.
 */
import { useState, useEffect } from "react";
import { api as client } from "../api/client";
import type { ResponseTimeSummary } from "../api/types";
import "./pipelinetimeline.css";

const STAGES = [
  { key: "signal",       label: "Signal",      icon: "📡", desc: "Live intel ingested" },
  { key: "risk",         label: "Risk",         icon: "⚠",  desc: "Fusion model fired" },
  { key: "scenario",     label: "Scenario",     icon: "📊", desc: "ARIO cascade" },
  { key: "procurement",  label: "Procurement",  icon: "🛢",  desc: "TOPSIS ranked" },
  { key: "spr",          label: "SPR",          icon: "🏭", desc: "Bellman SDP" },
] as const;

function fmt(s: number | null | undefined): string {
  if (s == null) return "—";
  if (s < 60) return `${Math.round(s)}s`;
  return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`;
}

export default function PipelineTimeline() {
  const [data, setData] = useState<ResponseTimeSummary | null>(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      const { data: d } = await client.responseTime();
      if (alive && d) setData(d);
    };
    load();
    const id = setInterval(load, 60_000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  const last = data?.last_run;

  // Map response-time keys to stage indices
  const durations: (number | null)[] = [
    null, // signal: no explicit duration — it's t=0
    last?.signal_to_risk_s ?? null,
    null, // scenario: derived from total
    last?.scenario_to_procurement_s ?? null,
    last?.procurement_to_reserve_s ?? null,
  ];

  const total = data?.rolling_median_s;
  const hasData = last != null;

  return (
    <div className="ptl-wrap">
      <div className="ptl-header">
        <span className="ptl-title">Autonomous Pipeline</span>
        {total != null && (
          <span className="ptl-total">
            end-to-end median <strong>{fmt(total)}</strong>
            {data && data.runs.length > 0 && (
              <span className="ptl-n"> · {data.runs.length} runs</span>
            )}
          </span>
        )}
        {!hasData && (
          <span className="ptl-hint">timing appears after first pipeline run</span>
        )}
      </div>

      <div className="ptl-track">
        {STAGES.map((s, i) => {
          const dur = durations[i];
          const active = hasData;
          return (
            <div key={s.key} className="ptl-stage-wrap">
              <div className={`ptl-stage${active ? " active" : ""}`}>
                <div className="ptl-icon">{s.icon}</div>
                <div className="ptl-stage-label">{s.label}</div>
                <div className="ptl-stage-desc">{s.desc}</div>
                {dur != null && (
                  <div className="ptl-dur">{fmt(dur)}</div>
                )}
              </div>
              {i < STAGES.length - 1 && (
                <div className={`ptl-arrow${active ? " active" : ""}`}>›</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
