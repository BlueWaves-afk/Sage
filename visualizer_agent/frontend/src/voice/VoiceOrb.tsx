import { useEffect, useRef, useState } from "react";
import { useVoice, voiceStore } from "./useVoiceStore";
import type { VoiceClient } from "./voiceClient";
import "./voice.css";

// Floating voice control. Two interactions:
//   - Click to enable/disable voice (mic permission prompt happens here on first
//     enable; browsers reject getUserMedia calls not tied to a user gesture)
//   - Hold to push-to-talk once enabled (spacebar works as a fallback)
//
// The UI reflects the store's orb state — the client mutates the store, this
// component only reads it. That's what makes the same UI work regardless of
// whether the trigger is voice, keyboard, or click.

export default function VoiceOrb({ client }: { client: VoiceClient | null }) {
  const orb = useVoice((s) => s.orb);
  const enabled = useVoice((s) => s.enabled);
  const connected = useVoice((s) => s.connected);
  const interim = useVoice((s) => s.interimTranscript);
  const status = useVoice((s) => s.currentStatus);
  const lastMsg = useVoice((s) => s.transcript[s.transcript.length - 1]);
  const [expanded, setExpanded] = useState(false);
  const holdTimer = useRef<number | null>(null);

  // Space-to-talk while orb is enabled but nothing else has focus.
  useEffect(() => {
    if (!enabled || !client) return;
    let holding = false;
    const isTypingTarget = (el: EventTarget | null) => {
      const t = el as HTMLElement | null;
      if (!t) return false;
      const tag = t.tagName;
      return tag === "INPUT" || tag === "TEXTAREA" || (t as HTMLElement).isContentEditable;
    };
    const down = (e: KeyboardEvent) => {
      if (e.code !== "Space" || holding || isTypingTarget(e.target)) return;
      e.preventDefault();
      holding = true;
      startPTT();
    };
    const up = (e: KeyboardEvent) => {
      if (e.code !== "Space" || !holding) return;
      e.preventDefault();
      holding = false;
      stopPTT();
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, client]);

  async function startPTT() {
    if (!client || !enabled) return;
    try {
      await client.startMicCapture();
    } catch {
      /* mic denied — startMicCapture already set a status message */
    }
  }
  function stopPTT() {
    client?.stopMicCapture();
  }

  function toggleEnabled() {
    if (!enabled) {
      voiceStore.setEnabled(true);
      voiceStore.setStatus("Hold the orb (or space) to talk");
    } else {
      voiceStore.setEnabled(false);
      client?.stop();
    }
  }

  // Pointer-driven push-to-talk (click-and-hold on the orb itself).
  function onPointerDown(e: React.PointerEvent) {
    if (!enabled) {
      toggleEnabled();
      return;
    }
    e.currentTarget.setPointerCapture(e.pointerId);
    holdTimer.current = window.setTimeout(() => {
      void startPTT();
    }, 60); // small delay so a single quick click doesn't fire the mic
  }
  function onPointerUp() {
    if (holdTimer.current) {
      window.clearTimeout(holdTimer.current);
      holdTimer.current = null;
    }
    if (orb === "listening") stopPTT();
  }

  const ringClass = enabled ? `orb-ring orb-${orb}` : "orb-ring orb-off";
  const label =
    !enabled ? "Voice off"
      : !connected ? "Connecting…"
      : orb === "listening" ? "Listening"
      : orb === "thinking" ? "Thinking"
      : orb === "speaking" ? "Speaking"
      : "Hold to talk";

  return (
    <div className={`voice-dock${expanded ? " expanded" : ""}`}>
      {(interim || status || lastMsg) && expanded && (
        <div className="voice-caption">
          {status && <div className="voice-caption-status">{status}</div>}
          {lastMsg && (
            <div className={`voice-caption-msg voice-caption-${lastMsg.role}`}>
              <span className="voice-caption-role">{lastMsg.role === "user" ? "You" : "SAGE"}</span>
              <span className="voice-caption-text">{lastMsg.text}</span>
            </div>
          )}
          {interim && <div className="voice-caption-interim">{interim}</div>}
        </div>
      )}
      <button
        className="voice-btn"
        aria-label={label}
        title={label}
        onPointerDown={onPointerDown}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onClick={() => setExpanded((v) => !v)}
      >
        <span className={ringClass} />
        <span className="orb-icon" aria-hidden>
          {enabled ? <MicSVG /> : <MicOffSVG />}
        </span>
      </button>
    </div>
  );
}

function MicSVG() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="3" width="6" height="12" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0M12 18v3M8 21h8" />
    </svg>
  );
}
function MicOffSVG() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="3" width="6" height="12" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0M12 18v3M8 21h8M3 3l18 18" />
    </svg>
  );
}
