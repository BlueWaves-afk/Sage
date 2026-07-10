// Small data-fetching + WebSocket hooks. No external state library — the app is
// read-mostly and these keep it dependency-light.

import { useEffect, useState } from "react";
import { api, type Envelope } from "./client";

/** Fetch once on mount; expose data, live-flag, and loading. */
export function useApi<T>(fetcher: () => Promise<Envelope<T>>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [live, setLive] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetcher().then((env) => {
      if (cancelled) return;
      setData(env.data);
      setLive(env.live);
      setLoading(false);
    });
    return () => {
      cancelled = true;
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
      ws = new WebSocket(`${base}/ws`);
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

export { api };
