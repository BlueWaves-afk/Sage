import { useEffect, useState } from "react";
import { api } from "../../api/hooks";
import type { ScenarioCard } from "../../api/types";

interface Props {
  onSelectCard: (card: ScenarioCard) => void;
  onPromote: (card: ScenarioCard) => void;
}

type Filter = "all" | "auto" | "user";

function timeAgo(iso: string): string {
  if (!iso) return "";
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

const ORIGIN_BADGE: Record<string, { icon: string; label: string }> = {
  auto: { icon: "\u{1F6F0}", label: "Auto-detected" },
  user: { icon: "\u{1F464}", label: "My run" },
  preset: { icon: "★", label: "Preset" },
};

export default function ScenarioLibrary({ onSelectCard, onPromote }: Props) {
  const [filter, setFilter] = useState<Filter>("all");
  const [cards, setCards] = useState<ScenarioCard[]>([]);
  const [loading, setLoading] = useState(false);

  async function reload() {
    setLoading(true);
    const env = await api.scenarioLibrary(filter, 20);
    setCards(env.data ?? []);
    setLoading(false);
  }

  useEffect(() => {
    reload();
    // Poll slowly so freshly auto-triggered scenarios surface without a manual refresh.
    const id = setInterval(reload, 30000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  return (
    <div className="sim-library">
      <div className="label-sm" style={{ marginBottom: 8 }}>Scenario Library</div>
      <div className="sim-lib-filters">
        {(["all", "auto", "user"] as Filter[]).map((f) => (
          <button
            key={f}
            className={`sim-lib-filter${filter === f ? " on" : ""}`}
            onClick={() => setFilter(f)}
          >
            {f === "all" ? "All" : f === "auto" ? "Auto-detected" : "My runs"}
          </button>
        ))}
      </div>

      {loading && cards.length === 0 && (
        <div className="sim-lib-empty">Loading…</div>
      )}
      {!loading && cards.length === 0 && (
        <div className="sim-lib-empty">
          No scenarios yet. Run one, or wait for the monitor to auto-detect a threshold crossing.
        </div>
      )}

      <div className="sim-lib-list">
        {cards.map((c) => (
          <div key={c.scenario_id} className="sim-lib-card">
            <div className="sim-lib-card-head" onClick={() => onSelectCard(c)}>
              <span className="sim-lib-origin" title={ORIGIN_BADGE[c.origin]?.label ?? c.origin}>
                {ORIGIN_BADGE[c.origin]?.icon ?? "●"}
              </span>
              <span className="sim-lib-label">{c.label}</span>
              <span className="sim-lib-time mono">{timeAgo(c.created_at)}</span>
            </div>
            <div className="sim-lib-card-body" onClick={() => onSelectCard(c)}>
              <span className="mono">{c.trigger_entity}</span>
              <span className="c-coral mono">{c.gap_mbpd.toFixed(2)} mbpd</span>
              <span className="c-amber mono">+${c.price_impact_high.toFixed(0)}/bbl</span>
              {!c.payload_available && <span className="sim-lib-stale">expired — re-run</span>}
            </div>
            <button
              className="sim-lib-promote"
              onClick={(e) => { e.stopPropagation(); onPromote(c); }}
              title="Promote to a named preset"
            >
              Promote ★
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
