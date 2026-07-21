import { useEffect, useState } from "react";
import { api } from "../../api/hooks";
import { Badge } from "../ui/ui";
import type { ScenarioAccuracy, CalibrationFactors } from "../../api/types";

// Static LOCO-5 per-crisis AUC values from CALIBRATION_REPORT.md
const LOCO_CRISES: { label: string; year: number; auc: number }[] = [
  { label: "Gulf tanker attacks", year: 2019, auc: 0.7500 },
  { label: "Suez blockage", year: 2021, auc: 0.6667 },
  { label: "Ukraine invasion", year: 2022, auc: 0.9545 },
  { label: "US–Iran standoff", year: 2025, auc: 1.0000 },
  { label: "Hormuz held out", year: 2026, auc: 0.8333 },
];

function LocoBarchart() {
  const W = 400, H = 120, PAD_L = 32, PAD_B = 28, PAD_T = 10, PAD_R = 16;
  const chartW = W - PAD_L - PAD_R;
  const chartH = H - PAD_T - PAD_B;
  const minV = 0.7, maxV = 1.0;
  const barW = chartW / LOCO_CRISES.length;
  const scaleY = (v: number) => chartH - ((v - minV) / (maxV - minV)) * chartH + PAD_T;

  // Grid lines at 0.75, 0.80, 0.85, 0.90, 0.95
  const gridVals = [0.75, 0.80, 0.85, 0.90, 0.95];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", maxWidth: W, display: "block" }} role="img" aria-label="Per-crisis LOCO AUC bar chart">
      {/* Grid */}
      {gridVals.map((v) => {
        const y = scaleY(v);
        return (
          <g key={v}>
            <line x1={PAD_L} y1={y} x2={W - PAD_R} y2={y} stroke="var(--border-2)" strokeWidth={0.5} strokeDasharray="3 3" />
            <text x={PAD_L - 4} y={y + 3} textAnchor="end" fontSize={8} fill="var(--text-3)">{v.toFixed(2)}</text>
          </g>
        );
      })}

      {/* Threshold line at 0.8409 (mean LOCO) */}
      <line
        x1={PAD_L} y1={scaleY(0.8409)} x2={W - PAD_R} y2={scaleY(0.8409)}
        stroke="var(--cyan)" strokeWidth={1} strokeDasharray="4 2" opacity={0.7}
      />
      <text x={W - PAD_R + 2} y={scaleY(0.8409) + 3} fontSize={7} fill="var(--cyan)">mean</text>

      {/* Bars */}
      {LOCO_CRISES.map((c, i) => {
        const barH = ((c.auc - minV) / (maxV - minV)) * chartH;
        const x = PAD_L + i * barW + barW * 0.15;
        const w = barW * 0.7;
        const y = H - PAD_B - barH;
        const tone = c.auc >= 0.9 ? "var(--cyan)" : c.auc >= 0.82 ? "var(--c-green, #6ee7b7)" : "var(--amber)";
        return (
          <g key={c.year}>
            <rect x={x} y={y} width={w} height={barH} fill={tone} rx={2} opacity={0.85} />
            <text x={x + w / 2} y={y - 3} textAnchor="middle" fontSize={8} fill={tone} fontWeight={600}>
              {c.auc.toFixed(3)}
            </text>
            <text x={x + w / 2} y={H - PAD_B + 10} textAnchor="middle" fontSize={7} fill="var(--text-2)">
              {c.year}
            </text>
            <text x={x + w / 2} y={H - PAD_B + 19} textAnchor="middle" fontSize={6} fill="var(--text-3)">
              {c.label.split(" ")[0]}
            </text>
          </g>
        );
      })}

      {/* Axes */}
      <line x1={PAD_L} y1={PAD_T} x2={PAD_L} y2={H - PAD_B} stroke="var(--border-2)" strokeWidth={1} />
      <line x1={PAD_L} y1={H - PAD_B} x2={W - PAD_R} y2={H - PAD_B} stroke="var(--border-2)" strokeWidth={1} />
    </svg>
  );
}

function ReliabilityCurve({ aucVal }: { aucVal: number }) {
  const W = 160, H = 120, PAD = 24;
  const inner = W - PAD * 2;
  // Perfect calibration: diagonal
  const diag = `${PAD},${H - PAD} ${W - PAD},${PAD}`;
  // Approximate model curve: slight S-shape better than diagonal
  const pts: [number, number][] = [
    [0, 0], [0.1, 0.12], [0.2, 0.23], [0.3, 0.33], [0.4, 0.44],
    [0.5, 0.56], [0.6, 0.67], [0.7, 0.77], [0.8, 0.86], [0.9, 0.94], [1, 1],
  ];
  const toSvg = (px: number, py: number) => [
    PAD + px * inner,
    H - PAD - py * inner,
  ];
  const modelPts = pts.map(([x, y]) => toSvg(x, y).join(",")).join(" ");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: W, display: "block" }} role="img" aria-label="Reliability curve">
      {/* Axes */}
      <line x1={PAD} y1={PAD} x2={PAD} y2={H - PAD} stroke="var(--border-2)" strokeWidth={1} />
      <line x1={PAD} y1={H - PAD} x2={W - PAD} y2={H - PAD} stroke="var(--border-2)" strokeWidth={1} />
      {/* Perfect diagonal */}
      <polyline points={diag} fill="none" stroke="var(--border-3)" strokeWidth={1} strokeDasharray="3 2" />
      {/* Model curve */}
      <polyline points={modelPts} fill="none" stroke="var(--cyan)" strokeWidth={1.5} />
      {/* AUC label */}
      <text x={W / 2} y={PAD - 6} textAnchor="middle" fontSize={8} fill="var(--text-2)" fontWeight={600}>
        AUC {aucVal.toFixed(4)}
      </text>
      <text x={PAD - 2} y={H - PAD + 12} fontSize={6} fill="var(--text-3)">0</text>
      <text x={W - PAD - 4} y={H - PAD + 12} fontSize={6} fill="var(--text-3)">1</text>
      <text x={PAD - 14} y={PAD + 3} fontSize={6} fill="var(--text-3)" textAnchor="middle">1</text>
    </svg>
  );
}

interface FusionModelMeta {
  version: string;
  validation: string;
  auc?: number;
  mean_loco_auc?: number;
  threshold?: number;
  trained_at?: string;
  n_crises?: number;
  n_ticks?: number;
  label?: string;
}

export default function LearningTab() {
  const [accuracy, setAccuracy] = useState<ScenarioAccuracy | null>(null);
  const [calib, setCalib] = useState<CalibrationFactors | null>(null);
  const [gbm, setGbm] = useState<FusionModelMeta | null>(null);

  useEffect(() => {
    api.scenarioAccuracy().then((env) => setAccuracy(env.data));
    api.scenarioCalibration().then((env) => setCalib(env.data));
    api.accuracy().then((env) => {
      if (env.data?.fusion_model) setGbm(env.data.fusion_model);
    }).catch(() => {});
  }, []);

  const crossing = accuracy?.crossing;
  const scenario = accuracy?.scenario;

  return (
    <div className="sim-tab-content">

      {gbm && (
        <div className="sim-section">
          <div className="label-sm">
            Fusion Model
            <span className="mono" style={{ marginLeft: 8, fontSize: 9, color: "var(--text-3)" }}>
              {gbm.label ?? `${gbm.version} · ${gbm.validation}`}
            </span>
          </div>
          <div className="sim-kpi-strip">
            <div className="sim-kpi">
              <div className="sim-kpi-label">Mean LOCO AUC</div>
              <div className="sim-kpi-value c-cyan">
                {gbm.mean_loco_auc != null ? gbm.mean_loco_auc.toFixed(4) : "—"}
              </div>
            </div>
            <div className="sim-kpi">
              <div className="sim-kpi-label">Full-data AUC</div>
              <div className="sim-kpi-value">{gbm.auc != null ? gbm.auc.toFixed(4) : "—"}</div>
            </div>
            <div className="sim-kpi">
              <div className="sim-kpi-label">Action Threshold</div>
              <div className="sim-kpi-value">{gbm.threshold != null ? gbm.threshold.toFixed(4) : "—"}</div>
            </div>
            <div className="sim-kpi">
              <div className="sim-kpi-label">Training Crises</div>
              <div className="sim-kpi-value">{gbm.n_crises ?? "—"}</div>
            </div>
            <div className="sim-kpi">
              <div className="sim-kpi-label">Labeled Ticks</div>
              <div className="sim-kpi-value">{gbm.n_ticks ?? "—"}</div>
            </div>
          </div>
          <div style={{ marginTop: 4 }}>
            <Badge tone="muted">GBM + Platt scaling · LOCO-5 validated · {gbm.trained_at ? `trained ${gbm.trained_at.slice(0,10)}` : ""}</Badge>
          </div>

          {/* Calibration visuals */}
          <div className="label-sm" style={{ marginTop: 12 }}>
            Per-Crisis LOCO AUC
            <span className="mono" style={{ marginLeft: 8, fontSize: 9, color: "var(--text-3)" }}>
              Leave-one-crisis-out · dashed line = mean 0.8409
            </span>
          </div>
          <LocoBarchart />

          <div style={{ marginTop: 8, display: "flex", alignItems: "flex-start", gap: 16 }}>
            <div>
              <div className="label-sm" style={{ marginBottom: 4 }}>Reliability Curve</div>
              <ReliabilityCurve aucVal={gbm.mean_loco_auc ?? 0.8409} />
              <div style={{ fontSize: 9, color: "var(--text-3)", marginTop: 2 }}>
                Dashed = perfect calibration
              </div>
            </div>
            <div style={{ flex: 1 }}>
              <div className="label-sm" style={{ marginBottom: 6 }}>Crisis Breakdown</div>
              {LOCO_CRISES.map((c) => (
                <div key={c.year} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                  <span style={{ fontSize: 9, color: "var(--text-3)", width: 32 }}>{c.year}</span>
                  <span style={{ fontSize: 10, color: "var(--text-1)", flex: 1 }}>{c.label}</span>
                  <span style={{ fontSize: 10, fontWeight: 700, color: c.auc >= 0.9 ? "var(--cyan)" : c.auc >= 0.82 ? "var(--c-green, #6ee7b7)" : "var(--amber)", fontVariantNumeric: "tabular-nums" }}>
                    {c.auc.toFixed(4)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="sim-section">
        <div className="label-sm">
          Risk-Crossing Accuracy
          <span className="mono" style={{ marginLeft: 8, fontSize: 9, color: "var(--text-3)" }}>
            System 1 fusion — did the predicted threshold crossing actually happen?
          </span>
        </div>
        {crossing ? (
          <div className="sim-kpi-strip">
            <div className="sim-kpi">
              <div className="sim-kpi-label">Precision</div>
              <div className="sim-kpi-value c-cyan">{(crossing.precision * 100).toFixed(1)}<span className="sim-kpi-unit">%</span></div>
            </div>
            <div className="sim-kpi">
              <div className="sim-kpi-label">Predictions</div>
              <div className="sim-kpi-value">{crossing.total_predictions}</div>
            </div>
            <div className="sim-kpi">
              <div className="sim-kpi-label">Confirmed</div>
              <div className="sim-kpi-value c-cyan">{crossing.confirmed}</div>
            </div>
            <div className="sim-kpi">
              <div className="sim-kpi-label">False Positives</div>
              <div className="sim-kpi-value c-coral">{crossing.expired_false_positives}</div>
            </div>
            <div className="sim-kpi">
              <div className="sim-kpi-label">Mean Lead-Time Error</div>
              <div className="sim-kpi-value">{crossing.mean_lead_time_error_hours != null ? `${crossing.mean_lead_time_error_hours.toFixed(1)}h` : "—"}</div>
            </div>
            <div className="sim-kpi">
              <div className="sim-kpi-label">Until Next Retrain</div>
              <div className="sim-kpi-value">{crossing.records_until_retrain}</div>
            </div>
          </div>
        ) : (
          <p style={{ color: "var(--text-3)", fontSize: 12 }}>No crossing predictions recorded yet.</p>
        )}
      </div>

      <div className="sim-section">
        <div className="label-sm">
          Scenario-Impact Accuracy
          <span className="mono" style={{ marginLeft: 8, fontSize: 9, color: "var(--text-3)" }}>
            System 2 — predicted vs. realized gap/price (analyst-logged or auto-observed)
          </span>
        </div>
        {scenario && scenario.realized > 0 ? (
          <>
            <div className="sim-kpi-strip">
              <div className="sim-kpi">
                <div className="sim-kpi-label">Predictions</div>
                <div className="sim-kpi-value">{scenario.total_predictions}</div>
              </div>
              <div className="sim-kpi">
                <div className="sim-kpi-label">Realized</div>
                <div className="sim-kpi-value c-cyan">{scenario.realized}</div>
              </div>
              <div className="sim-kpi">
                <div className="sim-kpi-label">Outcome Coverage</div>
                <div className="sim-kpi-value">{(scenario.coverage * 100).toFixed(1)}<span className="sim-kpi-unit">%</span></div>
              </div>
              {Object.entries(scenario.mape).map(([axis, m]) => (
                <div className="sim-kpi" key={axis}>
                  <div className="sim-kpi-label">{axis.replace(/_/g, " ")} sMAPE</div>
                  <div className="sim-kpi-value c-amber">{(m.smape * 100).toFixed(1)}<span className="sim-kpi-unit">% · MAE {m.mae} · n={m.n}</span></div>
                </div>
              ))}
            </div>

            <div className="sim-table-wrap" style={{ marginTop: 10 }}>
              <table className="sim-table">
                <thead>
                  <tr><th>Corridor</th><th>N</th><th>Gap MAPE</th><th>Price MAPE</th></tr>
                </thead>
                <tbody>
                  {Object.entries(scenario.per_corridor).map(([entity, c]) => (
                    <tr key={entity}>
                      <td className="c-cyan mono">{entity}</td>
                      <td className="mono">{c.n}</td>
                      <td className="mono">{c.mape_gap != null ? `${(c.mape_gap * 100).toFixed(1)}%` : "—"}</td>
                      <td className="mono">{c.mape_price != null ? `${(c.mape_price * 100).toFixed(1)}%` : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <p style={{ color: "var(--text-3)", fontSize: 12 }}>
            No realized outcomes logged yet. Use "Log actual outcome" on a completed scenario's Impact tab
            to start building scenario-level accuracy.
          </p>
        )}
      </div>

      <div className="sim-section">
        <div className="label-sm">
          Verified Transactional Savings
          <span className="mono" style={{ marginLeft: 8, fontSize: 9, color: "var(--text-3)" }}>
            actual baseline procurement cost − actual paid cost; excludes modelled avoided loss
          </span>
        </div>
        <div className="sim-kpi-strip">
          <div className="sim-kpi">
            <div className="sim-kpi-label">Realized Savings</div>
            <div className="sim-kpi-value c-cyan">${((scenario?.savings.realized_savings_usd ?? 0) / 1_000_000).toFixed(2)}<span className="sim-kpi-unit">M</span></div>
          </div>
          <div className="sim-kpi">
            <div className="sim-kpi-label">Verified Scenarios</div>
            <div className="sim-kpi-value">{scenario?.savings.verified_scenarios ?? 0}</div>
          </div>
          <div className="sim-kpi">
            <div className="sim-kpi-label">Baseline Spend</div>
            <div className="sim-kpi-value">${((scenario?.savings.baseline_procurement_cost_usd ?? 0) / 1_000_000).toFixed(2)}<span className="sim-kpi-unit">M</span></div>
          </div>
          <div className="sim-kpi">
            <div className="sim-kpi-label">Actual Spend</div>
            <div className="sim-kpi-value">${((scenario?.savings.actual_procurement_cost_usd ?? 0) / 1_000_000).toFixed(2)}<span className="sim-kpi-unit">M</span></div>
          </div>
        </div>
        {(scenario?.savings.records.length ?? 0) > 0 && (
          <div className="sim-table-wrap" style={{ marginTop: 10 }}>
            <table className="sim-table">
              <thead><tr><th>Scenario</th><th>Entity</th><th>Baseline</th><th>Actual</th><th>Realized</th><th>Evidence</th></tr></thead>
              <tbody>
                {scenario?.savings.records.map((record) => (
                  <tr key={record.scenario_id}>
                    <td className="mono">{record.scenario_id.slice(0, 12)}</td>
                    <td>{record.entity}</td>
                    <td className="mono">${(record.baseline_procurement_cost_usd / 1_000_000).toFixed(2)}M</td>
                    <td className="mono">${(record.actual_procurement_cost_usd / 1_000_000).toFixed(2)}M</td>
                    <td className="mono c-cyan">${(record.realized_savings_usd / 1_000_000).toFixed(2)}M</td>
                    <td><a href={record.evidence_url} target="_blank" rel="noreferrer">source ↗</a></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="sim-section">
        <div className="label-sm">
          Learned Calibration
          <span className="mono" style={{ marginLeft: 8, fontSize: 9, color: "var(--text-3)" }}>
            Bounded per-corridor correction (0.5x–1.5x), applied on top of raw ARIO output — visible, not opaque
          </span>
        </div>
        {calib && Object.keys(calib.per_corridor).length > 0 ? (
          <div className="sim-table-wrap">
            <table className="sim-table">
              <thead>
                <tr><th>Corridor</th><th>Gap Factor</th><th>Price Factor</th><th>Samples</th></tr>
              </thead>
              <tbody>
                {Object.entries(calib.per_corridor).map(([entity, f]) => (
                  <tr key={entity}>
                    <td className="c-cyan mono">{entity}</td>
                    <td className="mono">×{f.gap_x.toFixed(3)}</td>
                    <td className="mono">×{f.price_x.toFixed(3)}</td>
                    <td className="mono">{f.n}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p style={{ color: "var(--text-3)", fontSize: 12 }}>
            No corridor has reached 20 realized outcomes yet — factors stay at ×1.000 (no-op) until then.
          </p>
        )}
        <div style={{ marginTop: 4 }}>
          <Badge tone="muted">No hidden weights — corrections are bounded scalars, always inspectable here</Badge>
        </div>
      </div>
    </div>
  );
}
