import { useEffect, useState } from "react";
import { api } from "../../api/hooks";
import { Badge } from "../ui/ui";
import type { ScenarioAccuracy, CalibrationFactors } from "../../api/types";

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
              {Object.entries(scenario.mape).map(([axis, m]) => (
                <div className="sim-kpi" key={axis}>
                  <div className="sim-kpi-label">{axis.replace(/_/g, " ")} MAPE</div>
                  <div className="sim-kpi-value c-amber">{(m.mape * 100).toFixed(1)}<span className="sim-kpi-unit">% (n={m.n})</span></div>
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
