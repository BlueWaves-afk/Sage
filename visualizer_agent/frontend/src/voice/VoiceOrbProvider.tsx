import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import VoiceOrb from "./VoiceOrb";
import { connectVoiceBridge, type VoiceClient } from "./voiceClient";
import { useVoice, voiceStore } from "./useVoiceStore";
import { api } from "../api/client";

// Mount once (in AppShell). Opens the WebSocket lazily — the moment the user
// enables voice — so the connection doesn't churn while voice is turned off.
export default function VoiceOrbProvider() {
  const navigate = useNavigate();
  const enabled = useVoice((s) => s.enabled);
  const [client, setClient] = useState<VoiceClient | null>(null);
  const clientRef = useRef<VoiceClient | null>(null);
  const [voiceMode, setVoiceMode] = useState<string>("mock");

  useEffect(() => {
    api.health().then((env) => {
      if (env.data?.voice_mode) setVoiceMode(env.data.voice_mode);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!enabled) {
      clientRef.current?.disconnect();
      clientRef.current = null;
      setClient(null);
      return;
    }
    const c = connectVoiceBridge({ navigate });
    clientRef.current = c;
    setClient(c);
    return () => {
      c.disconnect();
    };
    // Only re-open when the user toggles enable — not on every navigate() change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);

  // If the drawer is closed by the user, clear the store slice so a subsequent
  // "open wiki" for the same entity re-triggers instead of no-op'ing.
  // Actual open logic lives in each screen (they read `drawerEntity` and pass
  // it to <WikiDrawer />). We just provide the reset seam.
  useEffect(() => {
    return () => voiceStore.reset();
  }, []);

  return <VoiceOrb client={client} voiceMode={voiceMode} />;
}
