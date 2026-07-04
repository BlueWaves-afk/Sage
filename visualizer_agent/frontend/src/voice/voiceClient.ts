import type { NavigateFunction } from "react-router-dom";
import type { ClientVoiceMessage, ServerVoiceMessage, VoiceOrbState } from "./types";
import { voiceStore } from "./useVoiceStore";
import { applyVoiceAction } from "./voiceActions";

// One WebSocket per session. This is intentionally NOT a LiveKit connection
// (see .claude/design/voice_interface_design.md — LiveKit is the production
// upgrade path; v1 uses a plain WebSocket so we don't take a LiveKit server
// dependency to demo). The transport is different; the UX / action taxonomy /
// wiring is identical.

// Vite proxies /ws → :8000 in dev; in prod, VITE_WS_BASE points at the gateway.
const WS_PATH = "/ws/voice";
const WS_BASE = import.meta.env.VITE_WS_BASE ?? `ws://${location.host}`;

export interface VoiceClient {
  sendText: (text: string) => void;
  stop: () => void;
  disconnect: () => void;
  startMicCapture: () => Promise<void>;
  stopMicCapture: () => void;
}

interface StartOpts {
  navigate: NavigateFunction;
}

/** Open a WebSocket to the voice bridge and wire it into the store. Returns
 *  a small handle for the orb to call — the caller doesn't touch raw sockets. */
export function connectVoiceBridge({ navigate }: StartOpts): VoiceClient {
  let ws: WebSocket | null = null;
  let audioCtx: AudioContext | null = null;
  let mediaStream: MediaStream | null = null;
  let recorderNode: ScriptProcessorNode | null = null;
  let source: MediaStreamAudioSourceNode | null = null;
  // Simple queue of TTS audio blobs — replayed in order so long replies play
  // as one continuous utterance rather than overlapping.
  let audioQueue: HTMLAudioElement[] = [];
  let closed = false;

  const url = `${WS_BASE}${WS_PATH}`;
  try {
    ws = new WebSocket(url);
  } catch (exc) {
    console.error("[voice] failed to open ws:", exc);
    voiceStore.setStatus("Voice bridge unreachable");
    return noopClient();
  }

  ws.binaryType = "arraybuffer";

  ws.onopen = () => {
    voiceStore.setConnected(true);
    voiceStore.setOrb("idle");
    send({ kind: "hello", sampleRate: 16000 });
  };

  ws.onmessage = (ev) => {
    let msg: ServerVoiceMessage | null = null;
    try {
      msg = JSON.parse(ev.data as string) as ServerVoiceMessage;
    } catch {
      return; // ignore anything that isn't structured JSON
    }
    switch (msg.kind) {
      case "state":
        voiceStore.setOrb(msg.state);
        break;
      case "transcript":
        if (msg.final) {
          voiceStore.appendMessage({ role: "user", text: msg.text, at: Date.now() });
          voiceStore.setInterim("");
        } else {
          voiceStore.setInterim(msg.text);
        }
        break;
      case "reply":
        voiceStore.appendMessage({ role: "sage", text: msg.text, at: Date.now() });
        break;
      case "action":
        applyVoiceAction(msg.action, navigate);
        break;
      case "audio":
        playAudioChunk(msg.format, msg.base64);
        break;
      case "error":
        console.warn("[voice] server error:", msg.message);
        voiceStore.setStatus(msg.message);
        break;
    }
  };

  ws.onclose = () => {
    voiceStore.setConnected(false);
    voiceStore.setOrb("off");
    stopMicCapture();
  };
  ws.onerror = (e) => {
    console.warn("[voice] ws error", e);
  };

  function send(msg: ClientVoiceMessage) {
    if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
  }

  function playAudioChunk(format: "wav" | "mp3" | "pcm16", base64: string) {
    const mime =
      format === "mp3" ? "audio/mpeg" : format === "wav" ? "audio/wav" : "audio/wav"; // pcm16 backend wraps as wav
    const bin = atob(base64);
    const buf = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
    const blob = new Blob([buf], { type: mime });
    const el = new Audio(URL.createObjectURL(blob));
    audioQueue.push(el);
    el.onended = () => {
      URL.revokeObjectURL(el.src);
      audioQueue = audioQueue.filter((a) => a !== el);
      if (audioQueue.length === 0) setOrbIfMatch("speaking", "idle");
    };
    setOrbIfMatch("thinking", "speaking");
    void el.play().catch(() => {
      /* autoplay may be blocked until first user interaction — first click on
         the orb counts as gesture, so subsequent chunks will play. */
    });
  }

  function setOrbIfMatch(from: VoiceOrbState, to: VoiceOrbState) {
    if (voiceStore.get().orb === from) voiceStore.setOrb(to);
  }

  async function startMicCapture(): Promise<void> {
    if (mediaStream) return; // already capturing
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
      });
    } catch (exc) {
      voiceStore.setStatus("Mic permission denied");
      throw exc;
    }
    audioCtx = new AudioContext({ sampleRate: 16000 });
    source = audioCtx.createMediaStreamSource(mediaStream);
    // ScriptProcessorNode is deprecated but universally supported; AudioWorklet
    // would be nicer but adds a separate module file to load. Given the audio
    // rate here is trivial (16kHz mono), the perf cost is negligible.
    recorderNode = audioCtx.createScriptProcessor(2048, 1, 1);
    recorderNode.onaudioprocess = (e) => {
      if (ws?.readyState !== WebSocket.OPEN) return;
      const float32 = e.inputBuffer.getChannelData(0);
      const pcm16 = float32ToPcm16(float32);
      send({ kind: "audio", base64: b64FromBytes(new Uint8Array(pcm16.buffer)) });
    };
    source.connect(recorderNode);
    recorderNode.connect(audioCtx.destination); // ScriptProcessor needs a sink
    voiceStore.setOrb("listening");
  }

  function stopMicCapture() {
    try {
      recorderNode?.disconnect();
      source?.disconnect();
    } catch {
      /* ignore */
    }
    recorderNode = null;
    source = null;
    if (audioCtx && audioCtx.state !== "closed") void audioCtx.close();
    audioCtx = null;
    mediaStream?.getTracks().forEach((t) => t.stop());
    mediaStream = null;
    if (voiceStore.get().orb === "listening") {
      send({ kind: "end_of_turn" });
      voiceStore.setOrb("thinking");
    }
  }

  function noopClient(): VoiceClient {
    return {
      sendText: () => {},
      stop: () => {},
      disconnect: () => {},
      startMicCapture: async () => {},
      stopMicCapture: () => {},
    };
  }

  return {
    sendText: (text) => send({ kind: "text", text }),
    stop: () => {
      audioQueue.forEach((a) => {
        try { a.pause(); } catch { /* ignore */ }
      });
      audioQueue = [];
      send({ kind: "stop" });
      voiceStore.setOrb("idle");
    },
    disconnect: () => {
      if (closed) return;
      closed = true;
      stopMicCapture();
      ws?.close();
    },
    startMicCapture,
    stopMicCapture,
  };
}

// ── Audio helpers ──────────────────────────────────────────────────────────

function float32ToPcm16(input: Float32Array): Int16Array {
  const out = new Int16Array(input.length);
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i]));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out;
}

function b64FromBytes(bytes: Uint8Array): string {
  // btoa on a raw string is UTF-16-unsafe; go through binary string explicitly.
  let s = "";
  for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
  return btoa(s);
}
