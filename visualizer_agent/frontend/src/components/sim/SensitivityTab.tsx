/**
 * Feature #2 — Tornado / Sensitivity chart.
 * Varies each ARIO assumption ±20% and ranks by impact swing.
 * "Assumptions must be explicit and testable" — this is its showpiece.
 */
import { useState } from "react";
import { api } from "../../api/hooks";
import type { ScenarioOutput, SensitivityRow } from "../../api/types";

interface Props {
  scenario: ScenarioOutput;
}

function TornadoBar({ row, maxSwing }: { row: SensitivityRow; maxSwing: number }) {
  const BAR_W = 200; // half-width budget in px
  const loW = Math.abs(row.swing_low) / maxSwing * BAR_W;
  const hiW = Math.abs(row.swing_high) / maxSwing * BAR_W;
  const loIsNeg = row.swing_low < 0;
  const hiIsNeg = row.swing_high < 0;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
      {/* Label */}
      <div style={{ width: 130, fontSize: 11, color: "var(--text-1)", textAlign: "right", flexShrink: 0 }}>
        {row.label}
      </div>

      {/* Bar chart (centered) */}
      <div style={{ position: "relative", width: BAR_W * 2, height: 20, flexShrink: 0 }}>
        {/* Center line */}
        <div style={{
          position: "absolute", left: BAR_W, top: 0, bottom: 0,
          width: 1, background: "var(--border-2)",
        }} />

        {/* Low swing (−20%) — extends left */}
        <div style={{
          position: "absolute",
          right: BAR_W,
          top: 3,
          height: 14,
          width: loW,
          background: loIsNeg ? "var(--c-red,#f87171)" : "var(--cyan)",
          borderRadius: "2px 0 0 2px",
          opacity: 0.85,
        }} />

        {/* High swing (+20%) — extends right */}
        <div style={{
          position: "absolute",
          left: BAR_W,
          top: 3,
          height: 14,
          width: hiW,
          background: hiIsNeg ? "var(--c-red,#f87171)" : "var(--cyan)",
          borderRadius: "0 2px 2px 0",
          opacity: 0.85,
        }} />
      </div>

      {/* Swing range label */}
      <div style={{ fontSize: 9, color: "var(--text-3)", fontVariantNumeric: "tabular-nums", flexShrink: 0 }}>
        {row.swing_low >= 0 ? "+" : ""}{row.swing_low.toFixed(3)} / +{row.swing_high.toFixed(3)} mbpd
      </div>
    </div>
  );
}

export default function SensitivityTab({ scenario }: Props) {
  const [rows, setRows] = useState<SensitivityRow[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function runAnalysis() {
    setLoading(true);
    setErr(null);
    const env = await api.scenarioSensitivity({ scenario_id: scenario.scenario_id });
    if (env.data && env.data.length > 0) {
      setRows(env.data);
    } else {
      setErr("Sensitivity run returned no data — scenario may be missing ARIO params.");
    }
    setLoading(false);
  }

  const maxSwing = rows ? Math.max(...rows.map((r) => r.max_swing), 0.001) : 1;

  return (
    <div className="sim-tab-content">
      <div className="sim-section">
        <div className="label-sm">
          Tornado / Sensitivity Analysis
          <span className="mono" style={{ marginLeft: 8, fontSize: 9, color: "var(--text-3)" }}>
            Vary each assumption ±20%, rank by gap swing (mbpd)
          </span>
        </div>

        {!rows && !loading && (
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 8 }}>
            <p style={{ fontSize: 12, color: "var(--text-2)", lineHeight: 1.5, maxWidth: 480 }}>
              ARIO runs ~30 perturbed scenarios (15 params × 2 directions) and ranks each
              assumption by how much it moves the supply gap. Runs in ~5–10 s.
            </p>
            <p style={{ fontSize: 11, color: "var(--text-3)", lineHeight: 1.4, maxWidth: 480 }}>
              Scenario: <strong style={{ color: "var(--text-1)" }}>{scenario.trigger_entity}</strong>
              {" · "}base gap <strong style={{ color: "var(--cyan)" }}>{scenario.gap_mbpd.toFixed(2)} mbpd</strong>
            </p>
            <button
              className="sim-toggle on"
              style={{ width: "fit-content" }}
              onClick={runAnalysis}
            >
              Run Sensitivity Analysis
            </button>
          </div>
        )}

        {loading && (
          <div style={{ color: "var(--text-3)", fontSize: 12, marginTop: 12 }}>
            Running {15} ARIO perturbations…
            <div className="sim-run-progress" style={{ marginTop: 8 }}>
              <div className="sim-run-bar" style={{ width: "60%", animation: "none", background: "var(--cyan-dim)" }} />
            </div>
          </div>
        )}

        {err && (
          <div style={{ color: "var(--c-red,#f87171)", fontSize: 12, marginTop: 8 }}>{err}</div>
        )}

        {rows && rows.length > 0 && (
          <>
            <div style={{ marginTop: 10, marginBottom: 6, fontSize: 9, color: "var(--text-3)", display: "flex", gap: 16 }}>
              <span>← Low (−20%)</span>
              <span style={{ flex: 1, textAlign: "center" }}>baseline</span>
              <span>High (+20%) →</span>
            </div>

            {rows.map((row) => (
              <TornadoBar key={row.param} row={row} maxSwing={maxSwing} />
            ))}

            <div style={{ marginTop: 10, fontSize: 10, color: "var(--text-3)", lineHeight: 1.5 }}>
              Cyan bars = gap increases (worse); red bars = gap decreases (better).
              {" "}Rank shows which assumptions dominate the uncertainty.
            </div>

            <button
              className="sim-reset"
              style={{ marginTop: 8 }}
              onClick={() => { setRows(null); setErr(null); }}
            >
              Re-run
            </button>
          </>
        )}
      </div>
    </div>
  );
}
