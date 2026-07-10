import { useEffect, useMemo, useState, useCallback } from "react";
import KnowledgeGraphMap from "../components/KnowledgeGraphMap";
import WikiDrawer from "../components/WikiDrawer";
import { Panel, Badge, Meter, OfflineHint } from "../components/ui/ui";
import { IconBrain, IconCheck } from "../components/icons";
import { api, useApi } from "../api/hooks";
import type { GraphNode, RiskHistoryPoint } from "../api/types";
import { useVoice, voiceStore } from "../voice/useVoiceStore";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
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

const TYPE_LEGEND: [string, string][] = [
  ["Corridor",   "rgb(230,84,74)"],
  ["Supplier",   "rgb(90,160,220)"],
  ["Refinery",   "rgb(45,190,165)"],
  ["Crude Grade","rgb(168,120,230)"],
  ["Port",       "rgb(70,195,225)"],
  ["SPR",        "rgb(233,196,106)"],
  ["Authority",  "rgb(150,165,190)"],
  ["Event",      "rgb(244,162,97)"],
];

export default function GlobalIntelligence() {
  const { data: graph, live } = useApi(api.graph);
  const { data: sprCurve } = useApi(api.sprCurve);
  const [active, setActive] = useState<string[]>(TYPE_FILTERS);
  const [colorBy, setColorBy] = useState<"risk" | "type">("risk");
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [showFlows, setShowFlows] = useState(false);
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [blastMode, setBlastMode] = useState(false);
  const [blastNode, setBlastNode] = useState<GraphNode | null>(null);
  const [riskHistory, setRiskHistory] = useState<RiskHistoryPoint[]>([]);
  const [historyEntity, setHistoryEntity] = useState<string | null>(null);

  const toggle = (t: string) =>
    setActive((a) => (a.includes(t) ? a.filter((x) => x !== t) : [...a, t]));

  // Fetch risk history when a node is selected.
  const handleNodeClick = useCallback((node: GraphNode) => {
    setSelected(node);
    if (blastMode) {
      setBlastNode(node);
    }
    // Load risk history for the timeline panel.
    setHistoryEntity(node.name);
    api.riskHistory(node.name, 24).then((env) => {
      setRiskHistory(env.data ?? []);
    });
  }, [blastMode]);

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
    handleNodeClick(node);
    voiceStore.focusEntity(null);
  }, [focusedByVoice, graph, handleNodeClick]);
  useEffect(() => {
    if (!drawerByVoice) return;
    const node =
      graph?.nodes.find((n) => n.name === drawerByVoice) ??
      ({ id: drawerByVoice, name: drawerByVoice, type: "Entity", lat: null, lon: null, score: 0, band: "CALM", degree: 0 } as GraphNode);
    handleNodeClick(node);
    voiceStore.openDrawer(null);
  }, [drawerByVoice, graph, handleNodeClick]);

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
            <button className={`gi-colorby-btn${colorBy === "risk" ? " on" : ""}`} onClick={() => setColorBy("risk")}>Risk</button>
            <button className={`gi-colorby-btn${colorBy === "type" ? " on" : ""}`} onClick={() => setColorBy("type")}>Type</button>
            <button className={`gi-colorby-btn${showFlows ? " on" : ""}`} onClick={() => setShowFlows((v) => !v)} title="Animate supply flows">Flows</button>
            <button className={`gi-colorby-btn${showHeatmap ? " on" : ""}`} onClick={() => setShowHeatmap((v) => !v)} title="Risk density heatmap">Heat</button>
            <button className={`gi-colorby-btn${blastMode ? " on" : ""}`} onClick={() => { setBlastMode((v) => !v); setBlastNode(null); }} title="Click a node to see its blast radius">Blast</button>
          </div>
        </div>
        <div className="gi-map card">
          <KnowledgeGraphMap
            graph={filtered}
            colorBy={colorBy}
            selectedId={selected?.id ?? null}
            onNodeClick={handleNodeClick}
            showFlows={showFlows}
            showHeatmap={showHeatmap}
            blastRadiusId={blastMode ? (blastNode?.id ?? null) : null}
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
          {colorBy === "type" && (
            <div className="gi-legend glass">
              <span className="label-sm">Entity Type</span>
              {TYPE_LEGEND.map(([name, c]) => (
                <span key={name} className="gi-legend-item">
                  <span className="gi-legend-dot" style={{ background: c }} /> {name}
                </span>
              ))}
            </div>
          )}
          <div className="gi-hint mono">
            {blastMode ? "BLAST MODE · Click a node to see its 2-hop impact radius" : "Click any node to open its wiki page"}
          </div>
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

        {/* ── Risk timeline ─────────────────────────────────────────────── */}
        {historyEntity && (
          <div className="gi-section">
            <div className="label-sm">
              24h Risk Timeline · <span className="c-cyan">{historyEntity}</span>
            </div>
            {riskHistory.length > 0 ? (
              <div style={{ height: 100 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={riskHistory.map((p) => ({
                    t: new Date(p.valid_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
                    score: Math.round(p.score * 100),
                    ais: Math.round(p.factor_ais * 100),
                    price: Math.round(p.factor_price * 100),
                    sanctions: Math.round(p.factor_sanctions * 100),
                  }))} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                    <XAxis dataKey="t" tick={{ fontSize: 9, fill: "#8892a4" }} interval="preserveStartEnd" />
                    <YAxis tick={{ fontSize: 9, fill: "#8892a4" }} domain={[0, 100]} />
                    <Tooltip
                      contentStyle={{ background: "#131318", border: "1px solid #2a2a35", fontSize: 11 }}
                      labelStyle={{ color: "#8892a4" }}
                    />
                    <Area type="monotone" dataKey="score" stroke="#4bb8d9" fill="rgba(75,184,217,0.18)" strokeWidth={1.5} dot={false} name="Total" />
                    <Area type="monotone" dataKey="ais" stroke="#2dd4bf" fill="none" strokeWidth={1} dot={false} name="AIS" strokeDasharray="3 2" />
                    <Area type="monotone" dataKey="price" stroke="#f4a261" fill="none" strokeWidth={1} dot={false} name="Price" strokeDasharray="3 2" />
                    <Area type="monotone" dataKey="sanctions" stroke="#e76f51" fill="none" strokeWidth={1} dot={false} name="Sanction" strokeDasharray="3 2" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="gi-situation" style={{ fontSize: 11, color: "var(--text-3)" }}>
                No history yet — signal data accumulates over time.
              </p>
            )}
          </div>
        )}

        {/* ── SPR depletion curve ───────────────────────────────────────── */}
        {sprCurve && (
          <div className="gi-section">
            <div className="label-sm">
              SPR Depletion Curve
              <span className="mono" style={{ marginLeft: 8, fontSize: 9, color: "var(--text-3)" }}>
                {sprCurve.current_fill_mmt.toFixed(1)} MMT · {sprCurve.days_cover.toFixed(0)}d cover
              </span>
            </div>
            <div style={{ height: 100 }}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={sprCurve.projection} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                  <XAxis dataKey="day" tick={{ fontSize: 9, fill: "#8892a4" }} label={{ value: "days", position: "insideRight", offset: 0, fontSize: 9, fill: "#8892a4" }} />
                  <YAxis tick={{ fontSize: 9, fill: "#8892a4" }} />
                  <Tooltip
                    formatter={(v: unknown) => [`${v} MMT`]}
                    contentStyle={{ background: "#131318", border: "1px solid #2a2a35", fontSize: 11 }}
                    labelFormatter={(l) => `Day ${l}`}
                  />
                  <Area
                    type="monotone"
                    dataKey="fill_mmt"
                    stroke="#e9c46a"
                    fill="rgba(233,196,106,0.15)"
                    strokeWidth={1.5}
                    dot={false}
                    name="Fill (MMT)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div className="gi-updated mono" style={{ marginTop: 4 }}>
              <span>CAPACITY {sprCurve.total_capacity_mmt.toFixed(1)} MMT</span>
              <span style={{ color: sprCurve.fill_pct < 30 ? "var(--red)" : sprCurve.fill_pct < 60 ? "var(--amber)" : "var(--green)" }}>
                {sprCurve.fill_pct.toFixed(1)}% FULL
              </span>
            </div>
          </div>
        )}
      </aside>

      <WikiDrawer
        node={selected}
        onClose={() => setSelected(null)}
        graph={graph ?? undefined}
        onNavigate={(n) => {
          if (n.lat != null && n.lon != null) handleNodeClick(n);
        }}
      />
    </div>
  );
}
