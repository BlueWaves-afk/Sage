import type { NavigateFunction } from "react-router-dom";
import type { VoiceAction, KpiKey } from "./types";
import { voiceStore } from "./useVoiceStore";

// The action bus. Only place the app translates VoiceActions into real state
// mutations + router calls. Screens read the resulting store slices via
// useVoice(...) — they never handle raw actions. This keeps voice and mouse
// interactions equivalent: both end up calling the same store setters.

// Flash duration for KPI pulse — matches the .cc-kpi-flash CSS animation.
const FLASH_MS = 1400;
let flashTimer: number | null = null;

export function applyVoiceAction(action: VoiceAction, navigate: NavigateFunction) {
  switch (action.type) {
    case "navigate":
      navigate(action.route);
      voiceStore.setStatus(null);
      break;

    case "focus_entity":
      // Focusing an entity means: land on the graph explorer AND select the
      // node there. If we're already on it, don't re-navigate (avoids a route
      // remount that would drop the map camera state).
      if (window.location.pathname !== "/intelligence") navigate("/intelligence");
      voiceStore.focusEntity(action.entity);
      break;

    case "open_wiki":
      // Opens the shared WikiDrawer wherever the user is — every screen
      // subscribes to `drawerEntity` and renders <WikiDrawer />.
      voiceStore.openDrawer(action.entity);
      break;

    case "select_option":
      if (window.location.pathname !== "/response") navigate("/response");
      voiceStore.selectSupplier(action.supplier);
      break;

    case "flash_kpi":
      if (window.location.pathname !== "/command") navigate("/command");
      voiceStore.flashKpi(action.key);
      if (flashTimer) window.clearTimeout(flashTimer);
      flashTimer = window.setTimeout(() => voiceStore.flashKpi(null), FLASH_MS);
      break;

    case "run_scenario":
      if (window.location.pathname !== "/simulation") navigate("/simulation");
      voiceStore.triggerScenario(action.trigger_entity);
      voiceStore.setStatus(`Running ${action.trigger_entity} scenario…`);
      break;

    case "status":
      voiceStore.setStatus(action.text);
      break;

    case "toast":
      // Toast: we surface it briefly in the orb's status line. A full toast
      // system would be nice but isn't required for v1.
      voiceStore.setStatus(action.text);
      window.setTimeout(() => {
        // Only clear if the message is still the same one — avoid stomping a
        // more recent status set by a later action.
        if (voiceStore.get().currentStatus === action.text) voiceStore.setStatus(null);
      }, 3500);
      break;
  }
}

// Dev-only helper — lets us type queries into the orb in mock mode.
export function isKpiKey(key: string): key is KpiKey {
  return [
    "threat_level",
    "brent_usd_bbl",
    "spr_coverage_pct",
    "active_alerts",
    "monitoring_entities",
  ].includes(key);
}
