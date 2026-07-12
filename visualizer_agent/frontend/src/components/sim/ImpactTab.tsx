import { useMemo, useState } from "react";
import { Badge } from "../ui/ui";
import { RichText } from "../RichText";
import GapFanChart from "./GapFanChart";
import { api } from "../../api/hooks";
import type { ScenarioOutput, MonteCarloBands, GraphNode, MitigatedResult } from "../../api/types";

/** Inline mini sparkline for the GDP trajectory (G6). */
function GdpSparkline({ trajectory }: { trajectory: number[] }) {
  const W = 80, H = 22;
  const nonZero = trajectory.filter(v => v !== 0);
  if (!nonZero.length) return null;
  const min = Math.min(...trajectory);
  const max = Math.max(...trajectory);
  const range = max - min || 0.001;
  const pts = trajectory.map((v, i) => {
    const x = (i / (trajectory.length - 1)) * W;
    const y = H - ((v - min) / range) * H;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return (
    <svg width={W} height={H} style={{ display: "block", marginTop: 4 }} aria-label="GDP impact trajectory">
      <polyline points={pts} fill="none" stroke="var(--c-red, #f87171)" strokeWidth="1.5" />
    </svg>
  );
}

interface HorizonPoint { day: number; label: string; critical: boolean }

function buildHorizon(s: ScenarioOutput): HorizonPoint[] {
  const tl = s.feedstock_gap_timeline ?? [];
  const peakDay = tl.length ? tl.indexOf(Math.max(...tl)) : 0;
  const pts: HorizonPoint[] = [
    { day: 0, label: "Disruption Begins", critical: false },
    { day: peakDay, label: `Peak Supply Gap (${s.gap_mbpd.toFixed(2)} mbpd)`, critical: true },
  ];
  if (s.spr_depletion_days < (s.gap_duration_days ?? 0) + 15) {
    pts.push({ day: Math.round(s.spr_depletion_days), label: "SPR Reaches Floor", critical: true });
  }
  pts.push({ day: Math.round(s.gap_duration_days ?? 0), label: "Gap Subsides", critical: false });
  return pts;
}

interface Props {
  scenario: ScenarioOutput;
  onWikilink: (entity: string) => void;
  onNodeClick?: (n: GraphNode) => void;
}

export default function ImpactTab({ scenario, onWikilink }: Props) {
  const mc = (scenario.assumptions?.monte_carlo as unknown as MonteCarloBands) ?? null;
  const horizonPoints = useMemo(() => buildHorizon(scenario), [scenario]);
  const [outcomeOpen, setOutcomeOpen] = useState(false);
  const [realGap, setRealGap] = useState("");
  const [realPrice, setRealPrice] = useState("");
  const [outcomeMsg, setOutcomeMsg] = useState<string | null>(null);
  const [mitigated, setMitigated] = useState<MitigatedResult | null>(null);
  const [mitigating, setMitigating] = useState(false);

  async function runMitigated() {
    setMitigating(true);
    setMitigated(null);
    const env = await api.scenarioRunMitigated(scenario.scenario_id);
    if (env.data) setMitigated(env.data);
    setMitigating(false);
  }

  async function submitOutcome() {
    const body: Record<string, number> = {};
    if (realGap.trim()) body.gap_mbpd = parseFloat(realGap);
    if (realPrice.trim()) body.price_impact_high = parseFloat(realPrice);
    if (Object.keys(body).length === 0) return;
    const env = await api.logScenarioOutcome(scenario.scenario_id, body);
    if (env.data?.ok) {
      setOutcomeMsg("Logged — thank you. Accuracy panel (Learning tab) updated.");
      setOutcomeOpen(false);
      setRealGap(""); setRealPrice("");
    } else {
      setOutcomeMsg("Failed to log outcome.");
    }
  }

  const bandTone = (band?: string | null): "cyan" | "amber" | "red" | "muted" => {
    if (!band) return "muted";
    const b = band.toUpperCase();
    if (b === "CRITICAL") return "red";
    if (b === "ACTION" || b === "ELEVATED") return "amber";
    return "cyan";
  };

  return (
    <div className="sim-tab-content">
      {/* Outcome logging control */}
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, alignItems: "center" }}>
        {outcomeMsg && <span style={{ fontSize: 10, color: "var(--text-3)" }}>{outcomeMsg}</span>}
        <button className="sim-reset" onClick={() => setOutcomeOpen((v) => !v)}>
          Log actual outcome
        </button>
      </div>
      {outcomeOpen && (
        <div className="sim-callout" style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div className="label-sm">What actually happened? (analyst-logged, feeds the Learning tab)</div>
          <div style={{ display: "flex", gap: 8 }}>
            <input className="sim-input" placeholder="Realized gap (mbpd)" value={realGap} onChange={(e) => setRealGap(e.target.value)} style={{ flex: 1 }} />
            <input className="sim-input" placeholder="Realized price high ($/bbl)" value={realPrice} onChange={(e) => setRealPrice(e.target.value)} style={{ flex: 1 }} />
            <button className="sim-toggle on" onClick={submitOutcome}>Submit</button>
          </div>
        </div>
      )}

      {/* KPI strip */}
      <div className="sim-kpi-strip">
        <div className="sim-kpi">
          <div className="sim-kpi-label">Peak Gap</div>
          <div className="sim-kpi-value c-coral">{scenario.gap_mbpd.toFixed(2)}<span className="sim-kpi-unit"> mbpd</span></div>
          {mc && <div className="sim-kpi-band">p10 {mc.gap_mbpd.p10.toFixed(2)} · p90 {mc.gap_mbpd.p90.toFixed(2)}</div>}
        </div>
        <div className="sim-kpi">
          <div className="sim-kpi-label">Duration</div>
          <div className="sim-kpi-value">{scenario.gap_duration_days ?? "—"}<span className="sim-kpi-unit"> d</span></div>
        </div>
        <div className="sim-kpi">
          <div className="sim-kpi-label">Price Impact</div>
          <div className="sim-kpi-value c-amber">
            +${scenario.price_impact_low.toFixed(0)}–${scenario.price_impact_high.toFixed(0)}<span className="sim-kpi-unit">/bbl</span>
          </div>
          {mc && <div className="sim-kpi-band">MC: ${mc.price_impact_usd.low.toFixed(0)}–${mc.price_impact_usd.high.toFixed(0)}</div>}
        </div>
        <div className="sim-kpi">
          <div className="sim-kpi-label">SPR Depletion</div>
          <div className="sim-kpi-value c-amber">{scenario.spr_depletion_days.toFixed(0)}<span className="sim-kpi-unit"> d</span></div>
          {mc && <div className="sim-kpi-band">p10 {mc.spr_depletion_days.p10.toFixed(0)} · p90 {mc.spr_depletion_days.p90.toFixed(0)}</div>}
        </div>
        <div className="sim-kpi">
          <div className="sim-kpi-label">GDP Hit</div>
          <div className="sim-kpi-value">{scenario.gdp_proxy_impact_pct != null ? `${scenario.gdp_proxy_impact_pct.toFixed(2)}%` : "—"}</div>
          {scenario.gdp_trajectory_pct && scenario.gdp_trajectory_pct.length > 0 && (
            <GdpSparkline trajectory={scenario.gdp_trajectory_pct} />
          )}
        </div>
        <div className="sim-kpi">
          <div className="sim-kpi-label">Inflation</div>
          <div className="sim-kpi-value">{scenario.inflation_impact_pct != null ? `+${scenario.inflation_impact_pct.toFixed(2)}%` : "—"}</div>
        </div>
        <div className="sim-kpi">
          <div className="sim-kpi-label">Confidence</div>
          <div className="sim-kpi-value">
            <Badge tone={bandTone(scenario.status)}>{Math.round(scenario.confidence * 100)}%</Badge>
          </div>
        </div>
      </div>

      {/* Fan chart */}
      <div className="sim-section">
        <div className="label-sm">Supply Gap Timeline
          {mc && <span className="mono" style={{ marginLeft: 8, fontSize: 9, color: "var(--text-3)" }}>Monte Carlo p10–p90 (n={mc.n})</span>}
        </div>
        <GapFanChart scenario={scenario} />
      </div>

      {/* Narrative */}
      <div className="sim-section">
        <div className="label-sm">Narrative Assessment</div>
        <p className="sim-narrative">
          Gap peaks at <strong>{scenario.gap_mbpd.toFixed(2)} mbpd</strong> over{" "}
          <strong>{scenario.gap_duration_days ?? "?"} days</strong>; SPR covers{" "}
          <strong>{scenario.spr_depletion_days.toFixed(0)} days</strong>; Brent +${scenario.price_impact_low.toFixed(0)}–${scenario.price_impact_high.toFixed(0)}/bbl.
        </p>
        {(scenario.assumptions as unknown as Record<string, { value: string }>)?.scenario_rationale?.value && (
          <RichText
            text={(scenario.assumptions as unknown as Record<string, { value: string }>).scenario_rationale.value}
            onWikilink={onWikilink}
          />
        )}
      </div>

      {/* Horizon timeline */}
      <div className="sim-section">
        <div className="label-sm">Impact Horizon</div>
        <div className="sim-horizon-track">
          {horizonPoints.map((t) => (
            <div key={t.label} className="sim-horizon-item">
              <span className={`sim-horizon-dot${t.critical ? " crit" : ""}`} />
              <div className={`sim-horizon-hour${t.critical ? " c-coral" : ""}`}>Day {t.day}</div>
              <div className="sim-horizon-label">{t.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Feature #3 — Re-run-with-mitigation */}
      <div className="sim-section">
        <div className="label-sm">
          SAGE Mitigation Value
          <span className="mono" style={{ marginLeft: 8, fontSize: 9, color: "var(--text-3)" }}>
            Re-run with procurement reallocation + SPR draw applied
          </span>
        </div>

        {!mitigated && !mitigating && (
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 6 }}>
            <p style={{ fontSize: 11, color: "var(--text-2)", flex: 1, lineHeight: 1.5 }}>
              Apply SAGE's top alternative supplier and SPR draw schedule as inputs,
              then re-simulate the residual supply gap — demonstrating the value loop end-to-end.
            </p>
            <button className="sim-toggle on" onClick={runMitigated} style={{ flexShrink: 0 }}>
              Run with SAGE Mitigations
            </button>
          </div>
        )}

        {mitigating && (
          <div style={{ color: "var(--text-3)", fontSize: 12, marginTop: 8 }}>
            Re-running ARIO with mitigations applied…
          </div>
        )}

        {mitigated && (
          <div style={{ marginTop: 8 }}>
            {/* Before/After comparison */}
            <div style={{ display: "flex", gap: 10, marginBottom: 10 }}>
              <div className="sim-kpi" style={{ flex: 1 }}>
                <div className="sim-kpi-label">Base Gap</div>
                <div className="sim-kpi-value c-coral">{mitigated.base_gap_mbpd.toFixed(2)}<span className="sim-kpi-unit"> mbpd</span></div>
              </div>
              <div style={{ display: "flex", alignItems: "center", color: "var(--cyan)", fontSize: 20, fontWeight: 700 }}>→</div>
              <div className="sim-kpi" style={{ flex: 1 }}>
                <div className="sim-kpi-label">Mitigated Gap</div>
                <div className="sim-kpi-value c-cyan">{mitigated.mitigated_gap_mbpd.toFixed(2)}<span className="sim-kpi-unit"> mbpd</span></div>
              </div>
              <div className="sim-kpi" style={{ flex: 1 }}>
                <div className="sim-kpi-label">Reduction</div>
                <div className="sim-kpi-value c-green" style={{ color: "var(--c-green,#6ee7b7)" }}>
                  −{mitigated.reduction_mbpd.toFixed(2)}<span className="sim-kpi-unit"> ({mitigated.pct_reduction.toFixed(0)}%)</span>
                </div>
              </div>
            </div>

            {/* Before/After visual bar */}
            <div style={{ marginBottom: 8 }}>
              <div style={{ display: "flex", gap: 4, alignItems: "center", height: 14, borderRadius: 4, overflow: "hidden", background: "var(--bg-4)" }}>
                <div style={{
                  width: `${(mitigated.mitigated_gap_mbpd / mitigated.base_gap_mbpd) * 100}%`,
                  background: "var(--cyan)", height: "100%", transition: "width 0.6s ease",
                }} />
                <div style={{
                  flex: 1, background: "var(--c-red,#f87171)", height: "100%", opacity: 0.3,
                }} />
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 9, color: "var(--text-3)", marginTop: 3 }}>
                <span>Residual gap (cyan)</span>
                <span>Mitigated portion (reduced)</span>
              </div>
            </div>

            {/* Mitigation sources */}
            {mitigated.mitigation_sources.map((s) => (
              <div key={s.label} style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "var(--text-2)", padding: "3px 0", borderBottom: "1px solid var(--border-1)" }}>
                <span>{s.label}</span>
                <span style={{ color: "var(--cyan)", fontVariantNumeric: "tabular-nums" }}>−{s.offset_mbpd.toFixed(3)} mbpd</span>
              </div>
            ))}

            <button className="sim-reset" style={{ marginTop: 8 }} onClick={() => setMitigated(null)}>
              Reset
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
