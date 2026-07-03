// Small data-fetching + WebSocket hooks. No external state library — the app is
// read-mostly and these keep it dependency-light.

import { useEffect, useRef, useState } from "react";
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
 * Subscribe to the /ws event stream. Falls back to a simulated pipeline sweep
 * when the socket can't connect, so the pipeline bar animates in the demo.
 */
export function usePipeline() {
  const [active, setActive] = useState<Stage | null>(null);
  const [connected, setConnected] = useState(false);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let closed = false;

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
      ws.onclose = () => {
        setConnected(false);
        if (!closed) startSim();
      };
      ws.onerror = () => ws?.close();
    } catch {
      startSim();
    }

    // Simulated sweep for offline demo mode.
    function startSim() {
      let i = 0;
      timer.current = window.setInterval(() => {
        setActive(WS_STAGES[i % WS_STAGES.length]);
        i++;
      }, 1100);
    }

    return () => {
      closed = true;
      ws?.close();
      if (timer.current) window.clearInterval(timer.current);
    };
  }, []);

  return { active, connected };
}

export { api };
