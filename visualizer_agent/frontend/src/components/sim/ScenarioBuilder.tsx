import { useEffect, useState } from "react";
import { api, useApi } from "../../api/hooks";
import type { ScenarioPreset, ScenarioRunRequest, ScenarioRunStatus, ScenarioCard } from "../../api/types";
import { IconPlay } from "../icons";
import ScenarioLibrary from "./ScenarioLibrary";

type RunState = {
  runId: string | null;
  running: boolean;
  stage: ScenarioRunStatus["stage"] | null;
  pct: number;
  error: string | null;
};

interface Props {
  onRunComplete: (scenarioId: string, label: string) => void;
  onLoadScenarioId: (scenarioId: string, label: string) => void;
}

const STAGE_LABEL: Record<string, string> = {
  scenario:    "Running scenario model…",
  procurement: "Optimising procurement…",
  reserve:     "Optimising SPR reserve…",
  done:        "Complete",
  error:       "Error",
};

export default function ScenarioBuilder({ onRunComplete, onLoadScenarioId }: Props) {
  const { data: initialPresets } = useApi(api.scenarioPresets);
  const [presets, setPresets] = useState<ScenarioPreset[] | null>(null);
  const [selPreset, setSelPreset] = useState<string | null>(null);
  const [promoteTarget, setPromoteTarget] = useState<ScenarioCard | null>(null);
  const [promoteLabel, setPromoteLabel] = useState("");
  const [promoteBlurb, setPromoteBlurb] = useState("");

  useEffect(() => { if (initialPresets && !presets) setPresets(initialPresets); }, [initialPresets, presets]);

  async function reloadPresets() {
    const env = await api.scenarioPresets();
    if (env.data) setPresets(env.data);
  }

  // Controlled parameters
  const [entity, setEntity] = useState("Strait of Hormuz");
  const [fracPct, setFracPct] = useState(80);           // 0–100 → disruption_fraction
  const [days, setDays] = useState(14);
  const [escalation, setEscalation] = useState<"constant" | "escalating" | "resolving">("constant");
  const [bypass, setBypass] = useState(false);
  const [sprPolicy, setSprPolicy] = useState<"aggressive" | "moderate" | "none">("aggressive");
  const [demandPct, setDemandPct] = useState(0);        // 0–30
  const [runDownstream, setRunDownstream] = useState(true);

  const [run, setRun] = useState<RunState>({ runId: null, running: false, stage: null, pct: 0, error: null });

  // Load preset params into controls
  function applyPreset(p: ScenarioPreset) {
    setSelPreset(p.id);
    setEntity(p.entity);
    setFracPct(Math.round(p.disruption_fraction * 100));
    setDays(p.disruption_days);
    setEscalation(p.escalation_profile);
    setBypass(p.bypass_compromised_frac >= 0.5);
    setSprPolicy(p.spr_policy);
    setDemandPct(Math.round(p.demand_destruction_pct * 100));
  }

  // Auto-select first preset when loaded
  useEffect(() => {
    if (presets && presets.length > 0 && !selPreset) applyPreset(presets[0]);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [presets]);

  // Polling loop
  useEffect(() => {
    if (!run.running || !run.runId) return;
    const id = setInterval(async () => {
      const env = await api.scenarioStatus(run.runId!);
      if (!env.data) return;
      const st = env.data;
      setRun((r) => ({ ...r, stage: st.stage, pct: st.pct }));
      if (st.stage === "done" && st.scenario_id) {
        clearInterval(id);
        setRun((r) => ({ ...r, running: false }));
        onRunComplete(st.scenario_id!, selPreset ? (presets?.find((p) => p.id === selPreset)?.label ?? entity) : entity);
      } else if (st.stage === "error") {
        clearInterval(id);
        setRun((r) => ({ ...r, running: false, error: st.error ?? "Run failed" }));
      }
    }, 1200);
    return () => clearInterval(id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run.running, run.runId]);

  async function handleRun() {
    setRun({ runId: null, running: true, stage: "scenario", pct: 0, error: null });
    const body: ScenarioRunRequest = {
      entity,
      disruption_fraction: fracPct / 100,
      disruption_days: days,
      escalation_profile: escalation,
      bypass_compromised_frac: bypass ? 1.0 : 0.0,
      spr_policy: sprPolicy,
      demand_destruction_pct: demandPct / 100,
      run_downstream: runDownstream,
    };
    const env = await api.runScenario(body);
    if (!env.data) {
      setRun({ runId: null, running: false, stage: "error", pct: 0, error: "Failed to start run" });
      return;
    }
    setRun((r) => ({ ...r, runId: env.data!.run_id }));
  }

  function handleSelectCard(card: ScenarioCard) {
    if (card.payload_available) {
      onLoadScenarioId(card.scenario_id, card.label);
    } else {
      // Payload expired — pre-fill the builder from the card so the user can re-run.
      setEntity(card.trigger_entity);
      setFracPct(Math.round(Math.max(0.1, Math.min(1, card.gap_mbpd / 2.19)) * 100));
    }
  }

  function openPromoteDialog(card: ScenarioCard) {
    setPromoteTarget(card);
    setPromoteLabel(card.label);
    setPromoteBlurb("");
  }

  async function confirmPromote() {
    if (!promoteTarget || !promoteLabel.trim()) return;
    await api.promoteScenario({
      scenario_id: promoteTarget.scenario_id,
      label: promoteLabel.trim(),
      blurb: promoteBlurb.trim() || undefined,
    });
    setPromoteTarget(null);
    await reloadPresets();
  }

  async function deleteCustomPreset(id: string) {
    const slug = id.replace(/^custom_/, "");
    await api.unpromoteScenario(slug);
    await reloadPresets();
  }

  return (
    <div className="sim-builder">
      <div className="label-sm" style={{ marginBottom: 10 }}>Scenario Presets</div>
      <div className="sim-presets">
        {(presets ?? []).map((p) => (
          <div key={p.id} className={`sim-preset-card${selPreset === p.id ? " active" : ""}`} style={{ position: "relative" }}>
            <button className="sim-preset-card-btn" onClick={() => applyPreset(p)}>
              <div className="sim-preset-label">
                {p.custom && <span className="c-cyan" style={{ marginRight: 4 }}>★</span>}
                {p.label}
              </div>
              <div className="sim-preset-blurb">{p.blurb}</div>
            </button>
            {p.custom && (
              <button
                className="sim-preset-delete"
                title="Remove custom preset"
                onClick={(e) => { e.stopPropagation(); deleteCustomPreset(p.id); }}
              >
                ×
              </button>
            )}
          </div>
        ))}
      </div>

      <div className="sim-divider" />

      <ScenarioLibrary onSelectCard={handleSelectCard} onPromote={openPromoteDialog} />

      <div className="sim-divider" />

      <div className="sim-field">
        <label className="sim-label">Entity</label>
        <input className="sim-input" value={entity} onChange={(e) => setEntity(e.target.value)} />
      </div>

      <div className="sim-field">
        <label className="sim-label">Severity <span className="sim-val">{fracPct}%</span></label>
        <input type="range" className="sim-range" min={0} max={100} value={fracPct} onChange={(e) => setFracPct(+e.target.value)} />
      </div>

      <div className="sim-field">
        <label className="sim-label">Duration <span className="sim-val">{days}d</span></label>
        <input type="range" className="sim-range" min={1} max={90} value={days} onChange={(e) => setDays(+e.target.value)} />
      </div>

      <div className="sim-field">
        <label className="sim-label">Escalation</label>
        <div className="sim-seg">
          {(["constant", "escalating", "resolving"] as const).map((v) => (
            <button key={v} className={`sim-seg-btn${escalation === v ? " on" : ""}`} onClick={() => setEscalation(v)}>{v}</button>
          ))}
        </div>
      </div>

      <div className="sim-field">
        <label className="sim-label">SPR Policy</label>
        <div className="sim-seg">
          {(["aggressive", "moderate", "none"] as const).map((v) => (
            <button key={v} className={`sim-seg-btn${sprPolicy === v ? " on" : ""}`} onClick={() => setSprPolicy(v)}>{v}</button>
          ))}
        </div>
      </div>

      <div className="sim-field">
        <label className="sim-label">Demand Destruction <span className="sim-val">{demandPct}%</span></label>
        <input type="range" className="sim-range" min={0} max={30} value={demandPct} onChange={(e) => setDemandPct(+e.target.value)} />
      </div>

      <div className="sim-field sim-field-row">
        <label className="sim-label">Bypass Compromised</label>
        <button className={`sim-toggle${bypass ? " on" : ""}`} onClick={() => setBypass((v) => !v)}>{bypass ? "YES" : "NO"}</button>
      </div>

      <div className="sim-field sim-field-row">
        <label className="sim-label">Run Procurement + Reserve</label>
        <button className={`sim-toggle${runDownstream ? " on" : ""}`} onClick={() => setRunDownstream((v) => !v)}>{runDownstream ? "YES" : "NO"}</button>
      </div>

      <div className="sim-divider" />

      {run.error && <div className="sim-error">{run.error}</div>}

      {run.running && (
        <div className="sim-progress">
          <div className="sim-progress-label mono">{STAGE_LABEL[run.stage ?? "scenario"]}</div>
          <div className="sim-progress-track">
            <div className="sim-progress-bar" style={{ width: `${run.pct}%` }} />
          </div>
        </div>
      )}

      <button
        className="btn-run press"
        disabled={run.running}
        onClick={handleRun}
        style={{ width: "100%", marginTop: 12 }}
      >
        <span className="btn-run-sheen" />
        <IconPlay width={13} height={13} />
        {run.running ? "Running…" : "Run Simulation"}
      </button>

      {promoteTarget && (
        <div className="sim-promote-overlay" onClick={() => setPromoteTarget(null)}>
          <div className="sim-promote-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="label-sm">Promote to Preset</div>
            <input
              className="sim-input"
              placeholder="Preset label"
              value={promoteLabel}
              onChange={(e) => setPromoteLabel(e.target.value)}
              style={{ marginTop: 8 }}
            />
            <input
              className="sim-input"
              placeholder="Blurb (optional)"
              value={promoteBlurb}
              onChange={(e) => setPromoteBlurb(e.target.value)}
              style={{ marginTop: 6 }}
            />
            <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
              <button className="sim-toggle" onClick={() => setPromoteTarget(null)}>Cancel</button>
              <button className="sim-toggle on" onClick={confirmPromote} disabled={!promoteLabel.trim()}>Promote</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
