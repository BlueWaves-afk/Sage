import { useState } from "react";
import { useAgentTrace } from "../api/hooks";
import type { AgentTraceEvent } from "../api/types";
import "./agenttrace.css";

const SYSTEM_LABEL: Record<string, string> = {
  "1": "System 1 · Sensing",
  "2": "System 2 · Scenario",
  "3": "System 3 · Procurement",
  "4": "System 4 · Reserve",
};

const AGENT_ICON: Record<string, string> = {
  ais: "\u{1F6F0}",          // satellite
  news: "\u{1F4F0}",         // newspaper
  prices: "\u{1F4C8}",       // chart increasing
  sanctions: "\u{1F6A7}",    // construction/barrier
  fusion: "\u{1F9EE}",       // abacus (fusion/calc)
  scenario: "\u{1F30A}",     // wave (cascade)
  procurement: "\u{1F69A}",  // truck
  reserve: "\u{1FEE9}",      // barrel-ish (jar as stand-in)
};

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const s = Math.round(diffMs / 1000);
  if (s < 5) return "now";
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  return `${Math.round(m / 60)}h ago`;
}

function TraceRow({ ev }: { ev: AgentTraceEvent }) {
  return (
    <div className={`trace-row trace-${ev.status}`}>
      <span className="trace-icon">{AGENT_ICON[ev.agent] ?? "⚙️"}</span>
      <div className="trace-body">
        <div className="trace-sys">
          {SYSTEM_LABEL[ev.system] ?? `System ${ev.system}`}
          {ev.origin && <span className={`trace-origin trace-origin-${ev.origin}`}>{ev.origin}</span>}
        </div>
        <div className="trace-action">
          {ev.status === "started" && <span className="trace-spinner" />}
          {ev.action}
        </div>
      </div>
      <span className="trace-time mono">{timeAgo(ev.ts)}</span>
    </div>
  );
}

export default function AgentTraceFeed() {
  const { events, connected } = useAgentTrace();
  const [collapsed, setCollapsed] = useState(false);

  const activeCount = events.filter((e) => e.status === "started").length;

  return (
    <div className={`agent-trace-panel${collapsed ? " collapsed" : ""}`}>
      <button className="agent-trace-header" onClick={() => setCollapsed((v) => !v)}>
        <span className={`agent-trace-dot${connected ? " live" : ""}`} />
        <span className="label-sm">Agent Activity</span>
        {activeCount > 0 && <span className="agent-trace-badge">{activeCount} running</span>}
        <span className="agent-trace-toggle">{collapsed ? "▾" : "▴"}</span>
      </button>
      {!collapsed && (
        <div className="agent-trace-list">
          {events.length === 0 && (
            <div className="agent-trace-empty">No agent activity yet — waiting for System 1 signals or a scenario run.</div>
          )}
          {events.map((ev, i) => (
            <TraceRow key={`${ev.ts}-${i}`} ev={ev} />
          ))}
        </div>
      )}
    </div>
  );
}
