import { apiPrefix } from "./region";
// Small data-fetching + WebSocket hooks. No external state library — the app is
// read-mostly and these keep it dependency-light.

import { useEffect, useState } from "react";
import { api, type Envelope } from "./client";
import type { AgentTraceEvent } from "./types";

/** Fetch on mount and automatically recover after a transient cold-start failure. */
export function useApi<T>(fetcher: () => Promise<Envelope<T>>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [live, setLive] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;

    const load = async (background = false) => {
      if (!background) setLoading(true);
      const env = await fetcher();
      if (cancelled) return;
      setData(env.data);
      setLive(env.live);
      setLoading(false);
      if (!env.live) retryTimer = setTimeout(() => load(true), 5000);
    };

    load();
    return () => {
      cancelled = true;
      if (retryTimer) clearTimeout(retryTimer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, live, loading };
}

export const WS_STAGES = [
  "SENSE",
  "TRIAGE",
  "SAGE",
  "SANDBOX",
  "SCENARIO",
  "PROCURE",
  "RESERVE",
] as const;

export type Stage = (typeof WS_STAGES)[number];

/**
 * Subscribe to the /ws event stream for real pipeline-stage events. If the socket
 * can't connect, the pipeline bar stays idle (no simulated sweep) — the bar only
 * ever reflects real LangGraph stage transitions pushed by the backend.
 */
export function usePipeline() {
  const [active, setActive] = useState<Stage | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let ws: WebSocket | null = null;

    const base = import.meta.env.VITE_WS_BASE ?? `ws://${location.host}`;
    try {
      ws = new WebSocket(`${base}${apiPrefix()}/ws`);
      ws.onopen = () => setConnected(true);
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.stage && WS_STAGES.includes(msg.stage)) setActive(msg.stage);
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onclose = () => setConnected(false);
      ws.onerror = () => ws?.close();
    } catch {
      setConnected(false);
    }

    return () => {
      ws?.close();
    };
  }, []);

  return { active, connected };
}

const TRACE_BUFFER_CAP = 30;

/**
 * Live "what is SAGE doing right now" feed. Cold-starts from the bounded
 * Redis-backed history (`/api/agent-trace/recent`) so the feed isn't empty on
 * first load, then appends live events pushed over the same `/ws` channel the
 * pipeline bar already uses (discriminated by `type: "agent_trace"`).
 */
export function useAgentTrace() {
  const [events, setEvents] = useState<AgentTraceEvent[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.agentTraceRecent(TRACE_BUFFER_CAP).then((env) => {
      if (!cancelled && env.data) setEvents(env.data);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let ws: WebSocket | null = null;
    const base = import.meta.env.VITE_WS_BASE ?? `ws://${location.host}`;
    try {
      ws = new WebSocket(`${base}${apiPrefix()}/ws`);
      ws.onopen = () => setConnected(true);
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === "agent_trace") {
            setEvents((prev) => [msg as AgentTraceEvent, ...prev].slice(0, TRACE_BUFFER_CAP));
          }
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onclose = () => setConnected(false);
      ws.onerror = () => ws?.close();
    } catch {
      setConnected(false);
    }
    return () => {
      ws?.close();
    };
  }, []);

  return { events, connected };
}

export { api };
