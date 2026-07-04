import { useSyncExternalStore } from "react";
import type { KpiKey, VoiceMessage, VoiceOrbState } from "./types";

// Minimal hand-rolled global store — Zustand-shaped but zero dependencies. This
// is intentional: the voice layer touches several screens (map focus, KPI
// flash, radar selection, drawer open), and prop-drilling all of that would
// pollute every screen's signature. One tiny module keeps the coupling in
// one place.

export interface VoiceState {
  // Orb / connection
  orb: VoiceOrbState;
  connected: boolean;
  enabled: boolean; // false = user has toggled voice off; UI hides orb

  // Conversation transcript — for a future full-panel view; the orb only
  // shows the latest user + latest sage entry.
  transcript: VoiceMessage[];
  interimTranscript: string; // in-flight STT, pre-finalization
  currentStatus: string | null; // e.g. "Running scenario…"

  // Action state — these are what the screens *subscribe* to.
  focusedEntity: string | null;   // GlobalIntelligence / KnowledgeGraphMap
  drawerEntity: string | null;    // Any screen with a WikiDrawer
  activeSupplier: string | null;  // ResponsePlanner radar
  flashedKpi: KpiKey | null;      // CommandCenter tile pulse
  runScenarioTrigger: string | null; // SimulationLab picks this up + clears it
}

type Listener = () => void;

const initial: VoiceState = {
  orb: "off",
  connected: false,
  enabled: false,
  transcript: [],
  interimTranscript: "",
  currentStatus: null,
  focusedEntity: null,
  drawerEntity: null,
  activeSupplier: null,
  flashedKpi: null,
  runScenarioTrigger: null,
};

let state: VoiceState = { ...initial };
const listeners = new Set<Listener>();

function set(partial: Partial<VoiceState>) {
  state = { ...state, ...partial };
  listeners.forEach((l) => l());
}

export const voiceStore = {
  get: () => state,
  subscribe: (l: Listener) => {
    listeners.add(l);
    return () => listeners.delete(l);
  },
  // Public setters (kept as named methods so screens can grep for who mutates
  // what — a plain `set()` would be too anonymous).
  setOrb: (orb: VoiceOrbState) => set({ orb }),
  setConnected: (connected: boolean) => set({ connected }),
  setEnabled: (enabled: boolean) => {
    // Turning voice off clears in-flight UI effects so nothing lingers.
    if (!enabled) set({ enabled, orb: "off", currentStatus: null, interimTranscript: "" });
    else set({ enabled });
  },
  appendMessage: (m: VoiceMessage) =>
    set({ transcript: [...state.transcript, m].slice(-40), interimTranscript: "" }),
  setInterim: (interimTranscript: string) => set({ interimTranscript }),
  setStatus: (currentStatus: string | null) => set({ currentStatus }),

  focusEntity: (entity: string | null) => set({ focusedEntity: entity }),
  openDrawer: (entity: string | null) => set({ drawerEntity: entity }),
  selectSupplier: (supplier: string | null) => set({ activeSupplier: supplier }),
  flashKpi: (key: KpiKey | null) => set({ flashedKpi: key }),
  triggerScenario: (entity: string | null) => set({ runScenarioTrigger: entity }),
  clearScenarioTrigger: () => set({ runScenarioTrigger: null }),

  reset: () => {
    state = { ...initial };
    listeners.forEach((l) => l());
  },
};

/** Hook. Selectors are just functions of state — screens can pick just the
 *  slice they care about, so they don't re-render on unrelated changes. */
export function useVoice<T>(selector: (s: VoiceState) => T): T {
  return useSyncExternalStore(
    voiceStore.subscribe,
    () => selector(voiceStore.get()),
    () => selector(initial)
  );
}
