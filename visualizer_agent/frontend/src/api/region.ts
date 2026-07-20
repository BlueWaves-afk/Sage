// Multi-tenant region selector. SAGE serves multiple import-dependent economies
// from the same engine (India on graph "sage", Japan on "sage_jp"). The frontend
// picks which tenant's API to talk to via an nginx path prefix:
//   india → ""     → /api/...   → api-gateway   (graph "sage")
//   japan → "/jp"  → /jp/api/.. → api-gateway-jp (graph "sage_jp")
// The choice is persisted in localStorage; switching reloads the page.

export type Region = "india" | "japan";

export const REGIONS: { id: Region; label: string; flag: string }[] = [
  { id: "india", label: "India", flag: "🇮🇳" },
  { id: "japan", label: "Japan", flag: "🇯🇵" },
];

const KEY = "sage_region";

export function currentRegion(): Region {
  try {
    return localStorage.getItem(KEY) === "japan" ? "japan" : "india";
  } catch {
    return "india";
  }
}

/** nginx path prefix for the active tenant's API/WS. "" for India, "/jp" for Japan. */
export function apiPrefix(region: Region = currentRegion()): string {
  return region === "japan" ? "/jp" : "";
}

/** Persist the region and hard-reload so every panel re-fetches from the new tenant. */
export function switchRegion(region: Region): void {
  try {
    localStorage.setItem(KEY, region);
  } catch {
    /* ignore */
  }
  window.location.reload();
}
