/**
 * G2 — End-to-end response time strip.
 * Shows "Signal → Recommendation: 74 s (median, last 5 runs)" with per-stage
 * breakdown on hover. Displayed in Command Center below the pipeline bar.
 */
import { useState, useEffect } from "react";
import { api as client } from "../api/client";
import type { ResponseTimeSummary } from "../api/types";
import "./responsetime.css";

const STAGE_LABELS: { key: keyof import("../api/types").ResponseTimeRun; label: string }[] = [
  { key: "signal_to_risk_s",              label: "Signal → Risk" },
  { key: "scenario_to_procurement_s",     label: "Scenario → Procure" },
  { key: "procurement_to_reserve_s",      label: "Procure → Reserve" },
];

function fmt(s: number | null | undefined): string {
  if (s == null) return "—";
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`;
}

export default function ResponseTimeStrip() {
  const [data, setData] = useState<ResponseTimeSummary | null>(null);
  const [show, setShow] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      const { data: d } = await client.responseTime();
      if (alive && d) setData(d);
    };
    load();
    // Refresh every 60 s so the strip updates after each new pipeline run
    const id = setInterval(load, 60_000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  if (!data || data.rolling_median_s == null) return null;

  const last = data.last_run;

  return (
    <div
      className="rt-strip"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      <span className="rt-icon">⚡</span>
      <span className="rt-label">Signal → Recommendation</span>
      <span className="rt-value">{fmt(data.rolling_median_s)}</span>
      <span className="rt-meta">median · last {data.runs.length} run{data.runs.length !== 1 ? "s" : ""}</span>

      {show && last && (
        <div className="rt-tooltip">
          <div className="rt-tooltip-title">Last run · {fmt(last.total_s)} total</div>
          {STAGE_LABELS.map(({ key, label }) =>
            last[key] != null ? (
              <div key={key} className="rt-tooltip-row">
                <span className="rt-tooltip-stage">{label}</span>
                <span className="rt-tooltip-dur">{fmt(last[key] as number)}</span>
              </div>
            ) : null
          )}
          <div className="rt-tooltip-foot">
            See <a href="/docs/METHODOLOGY.md" target="_blank" rel="noreferrer">METHODOLOGY.md</a> for clock definition
          </div>
        </div>
      )}
    </div>
  );
}
