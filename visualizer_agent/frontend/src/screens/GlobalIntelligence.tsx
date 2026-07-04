import { useEffect, useMemo, useState } from "react";
import KnowledgeGraphMap from "../components/KnowledgeGraphMap";
import WikiDrawer from "../components/WikiDrawer";
import { Panel, Badge, Meter, OfflineHint } from "../components/ui/ui";
import { IconBrain, IconCheck } from "../components/icons";
import { api, useApi } from "../api/hooks";
import type { GraphNode } from "../api/types";
import { useVoice, voiceStore } from "../voice/useVoiceStore";
import "./intelligence.css";

// Entity types double as the map's layer filters.
const TYPE_FILTERS = ["Corridor", "Supplier", "Refinery", "CrudeGrade", "Port", "SPRCavern", "Authority", "GeoEvent"];
const TYPE_LABEL: Record<string, string> = {
  Corridor: "Corridors",
  Supplier: "Suppliers",
  Refinery: "Refineries",
  CrudeGrade: "Crude Grades",
  Port: "Ports",
  SPRCavern: "SPR",
  Authority: "Authorities",
  GeoEvent: "Events",
};
const BAND_LEGEND: [string, string][] = [
  ["CALM", "#2a9d8f"],
  ["WATCH", "#e9c46a"],
  ["ELEVATED", "#f4a261"],
  ["ACTION", "#e76f51"],
  ["CRITICAL", "#e63946"],
];

export default function GlobalIntelligence() {
  const { data: graph, live } = useApi(api.graph);
  const [active, setActive] = useState<string[]>(TYPE_FILTERS);
  const [colorBy, setColorBy] = useState<"risk" | "type">("risk");
  const [selected, setSelected] = useState<GraphNode | null>(null);

  const toggle = (t: string) =>
    setActive((a) => (a.includes(t) ? a.filter((x) => x !== t) : [...a, t]));

  const filtered = useMemo(() => {
    if (!graph) return { nodes: [], edges: [] };
    const nodes = graph.nodes.filter((n) => active.includes(n.type));
    const ids = new Set(nodes.map((n) => n.id));
    const edges = graph.edges.filter((e) => ids.has(e.source) && ids.has(e.target));
    return { nodes, edges };
  }, [graph, active]);

  const hubs = useMemo(
    () => [...(graph?.nodes ?? [])].sort((a, b) => b.degree - a.degree).slice(0, 4),
    [graph]
  );

  // Voice: `focus_entity` selects the graph node (drives map+drawer at once);
  // `open_wiki` just opens the drawer without moving the map.
  const focusedByVoice = useVoice((s) => s.focusedEntity);
  const drawerByVoice = useVoice((s) => s.drawerEntity);
  useEffect(() => {
    if (!focusedByVoice) return;
    // Try to resolve to a real graph node so the map camera has coordinates;
    // fall back to a bare stub (drawer still opens fine on the entity name).
    const node =
      graph?.nodes.find((n) => n.name === focusedByVoice) ??
      ({ id: focusedByVoice, name: focusedByVoice, type: "Entity", lat: null, lon: null, score: 0, band: "CALM", degree: 0 } as GraphNode);
    setSelected(node);
    voiceStore.focusEntity(null);
  }, [focusedByVoice, graph]);
  useEffect(() => {
    if (!drawerByVoice) return;
    const node =
      graph?.nodes.find((n) => n.name === drawerByVoice) ??
      ({ id: drawerByVoice, name: drawerByVoice, type: "Entity", lat: null, lon: null, score: 0, band: "CALM", degree: 0 } as GraphNode);
    setSelected(node);
    voiceStore.openDrawer(null);
  }, [drawerByVoice, graph]);

  return (
    <div className="gi">
      {/* Map column */}
      <div className="gi-map-col">
        <div className="gi-breadcrumb mono">
          KNOWLEDGE GRAPH <span className="gi-sep">›</span> GEOSPATIAL VIEW{" "}
          <span className="gi-sep">›</span>{" "}
          <span className="c-cyan">{filtered.nodes.length} NODES · {filtered.edges.length} EDGES</span>
          <OfflineHint live={live} />
        </div>
        <div className="gi-tabs">
          {TYPE_FILTERS.map((t) => (
            <button
              key={t}
              className={`gi-tab${active.includes(t) ? " active" : ""}`}
              onClick={() => toggle(t)}
            >
              {TYPE_LABEL[t]}
            </button>
          ))}
          <div className="gi-colorby">
            <button
              className={`gi-colorby-btn${colorBy === "risk" ? " on" : ""}`}
              onClick={() => setColorBy("risk")}
            >
              Risk
            </button>
            <button
              className={`gi-colorby-btn${colorBy === "type" ? " on" : ""}`}
              onClick={() => setColorBy("type")}
            >
              Type
            </button>
          </div>
        </div>
        <div className="gi-map card">
          <KnowledgeGraphMap
            graph={filtered}
            colorBy={colorBy}
            selectedId={selected?.id ?? null}
            onNodeClick={setSelected}
          />
          {colorBy === "risk" && (
            <div className="gi-legend glass">
              <span className="label-sm">Risk Band</span>
              {BAND_LEGEND.map(([name, c]) => (
                <span key={name} className="gi-legend-item">
                  <span className="gi-legend-dot" style={{ background: c }} /> {name}
                </span>
              ))}
            </div>
          )}
          <div className="gi-hint mono">Click any node to open its wiki page</div>
        </div>
      </div>

      {/* Briefing column */}
      <aside className="gi-brief">
        <div className="gi-brief-head">
          <span className="gi-brief-title">
            <IconBrain width={18} height={18} className="c-cyan" /> SAGE Briefing
          </span>
          <span className="mono gi-ver">VER: SAGE-V4.2</span>
        </div>

        <div className="gi-section">
          <div className="label-sm">Current Situation</div>
          <p className="gi-situation">
            The knowledge graph tracks {graph?.nodes.length ?? 0} entities — corridors, suppliers,
            refineries, crude grades, ports, reserves and authorities — linked by{" "}
            {graph?.edges.length ?? 0} structural relationships. Node colour reflects live fused risk;
            size reflects connectivity. Select a node to read its reconciled wiki assessment.
          </p>
        </div>

        <div className="gi-metrics">
          <div className="gi-metric card gi-metric-amber">
            <div className="label-sm">Highest Risk</div>
            <div className="gi-metric-value c-amber">
              {(graph?.nodes ?? []).reduce((m, n) => (n.score > m.score ? n : m), { score: 0, band: "CALM" } as GraphNode).band}
              <span className="gi-blip" />
            </div>
          </div>
          <div className="gi-metric card">
            <div className="label-sm">Graph Coverage</div>
            <div className="gi-metric-value c-cyan">{live ? "LIVE" : "DEMO"}</div>
            <Meter value={live ? 1 : 0.4} />
          </div>
        </div>

        <div className="gi-section">
          <div className="label-sm">Most Connected Hubs</div>
          <div className="gi-hubs">
            {hubs.map((n) => (
              <button key={n.id} className="gi-hub" onClick={() => setSelected(n)}>
                <span className="gi-hub-name">{n.name}</span>
                <span className="gi-hub-deg mono">{n.degree}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="gi-section">
          <div className="label-sm">Supporting Evidence</div>
          <div className="gi-evidence">
            {["Reuters", "AIS Live", "OFAC"].map((s) => (
              <span key={s} className="gi-evidence-chip">
                <IconCheck width={13} height={13} className="c-cyan" /> {s}
              </span>
            ))}
          </div>
          <div className="gi-updated mono">
            <span>SOURCE: FALKORDB GRAPH</span>
            <span>{live ? "SYNCED" : "CACHED"}</span>
          </div>
        </div>
      </aside>

      <WikiDrawer node={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
