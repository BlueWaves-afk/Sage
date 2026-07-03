import { WS_STAGES, usePipeline } from "../api/hooks";
import "./pipeline.css";

// Autonomous-loop indicator: SENSE → TRIAGE → SAGE → SANDBOX → SCENARIO → PROCURE → RESERVE.
// Lights up each stage as LangGraph transitions fire over the WebSocket.
export default function PipelineBar() {
  const { active, connected } = usePipeline();
  const activeIdx = active ? WS_STAGES.indexOf(active) : -1;

  return (
    <div className="pipeline">
      <span className="label-sm pipeline-title">
        Autonomous Pipeline
        <span className={`pipeline-conn ${connected ? "on" : "sim"}`}>
          {connected ? "LIVE" : "SIM"}
        </span>
      </span>
      <div className="pipeline-track">
        {WS_STAGES.map((stage, i) => (
          <div
            key={stage}
            className={`pipeline-chevron${i === activeIdx ? " active" : ""}${
              i < activeIdx ? " done" : ""
            }${i === 0 ? " first" : ""}`}
          >
            <span className="pipeline-name">{stage}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
