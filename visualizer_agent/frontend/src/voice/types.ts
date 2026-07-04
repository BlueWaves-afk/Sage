// Voice interface — action types + orb state.
// Matches the taxonomy in .claude/design/voice_interface_design.md §4.

// KPI keys are the same identifiers the /api/dashboard endpoint returns, so
// `flash_kpi` never invents a key that has no corresponding tile on-screen.
export type KpiKey =
  | "threat_level"
  | "brent_usd_bbl"
  | "spr_coverage_pct"
  | "active_alerts"
  | "monitoring_entities";

export type VoiceRoute =
  | "/command"
  | "/intelligence"
  | "/simulation"
  | "/response"
  | "/copilot"
  | "/";

/** Every action the voice brain can dispatch to drive the UI. */
export type VoiceAction =
  | { type: "navigate"; route: VoiceRoute }
  | { type: "focus_entity"; entity: string }
  | { type: "open_wiki"; entity: string }
  | { type: "flash_kpi"; key: KpiKey }
  | { type: "select_option"; supplier: string }
  | { type: "run_scenario"; trigger_entity: string }
  // Ambient — no side effect, just information the orb shows.
  | { type: "status"; text: string }
  // A one-shot toast, distinct from status which sticks in the orb.
  | { type: "toast"; text: string; tone?: "info" | "warn" | "error" };

/** Orb visible state — drives the animation ring around the button. */
export type VoiceOrbState =
  | "off" // voice disabled / mic off
  | "idle" // connected, waiting for wake-word / press
  | "listening" // capturing mic audio
  | "thinking" // waiting for brain
  | "speaking"; // TTS audio playing

export interface VoiceMessage {
  role: "user" | "sage";
  text: string;
  at: number; // client-side timestamp for ordering
}

/** Structured envelope for messages the backend sends on the WS. */
export type ServerVoiceMessage =
  | { kind: "transcript"; final: boolean; text: string }
  | { kind: "reply"; text: string }
  | { kind: "action"; action: VoiceAction }
  | { kind: "state"; state: VoiceOrbState }
  | { kind: "audio"; format: "wav" | "mp3" | "pcm16"; base64: string }
  | { kind: "error"; message: string };

/** What the client sends up. Kept intentionally small. */
export type ClientVoiceMessage =
  | { kind: "hello"; sampleRate: number }
  | { kind: "audio"; base64: string } // chunk of mic PCM16
  | { kind: "end_of_turn" } // sent when user stops holding PTT / VAD trips
  | { kind: "text"; text: string } // typed text — mock mode + accessibility path
  | { kind: "stop" }; // barge-in / cancel current TTS + brain call
