import { currentRegion, switchRegion, REGIONS, type Region } from "../../api/region";

/**
 * Multi-tenant context-bundle switcher. Lets an operator flip the whole dashboard
 * between import-dependent economies (India / Japan) instantiated from the same
 * engine. Selecting a region persists the choice and reloads so every panel
 * re-fetches from that tenant's api-gateway (routed by nginx path prefix).
 */
export default function RegionSwitcher() {
  const region = currentRegion();
  const active = REGIONS.find((r) => r.id === region) ?? REGIONS[0];

  return (
    <label className="region-switch" title="Switch context bundle (tenant)">
      <span className="region-switch-label">CONTEXT</span>
      <span className="region-switch-flag">{active.flag}</span>
      <select
        className="region-switch-select"
        value={region}
        onChange={(e) => switchRegion(e.target.value as Region)}
      >
        {REGIONS.map((r) => (
          <option key={r.id} value={r.id}>
            {r.flag} {r.label}
          </option>
        ))}
      </select>
    </label>
  );
}
