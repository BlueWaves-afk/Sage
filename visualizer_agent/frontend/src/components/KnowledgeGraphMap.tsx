import { useMemo, useState } from "react";
import DeckGL from "@deck.gl/react";
import { ScatterplotLayer, LineLayer, TextLayer } from "@deck.gl/layers";
import { CollisionFilterExtension } from "@deck.gl/extensions";
import { Map as BaseMap } from "react-map-gl/maplibre";
import type { GraphData, GraphNode } from "../api/types";
import { useTheme, basemapFor } from "../theme";

const BAND_RGB: Record<string, [number, number, number]> = {
  CALM:     [45,  178, 158],
  WATCH:    [233, 196, 106],
  ELEVATED: [244, 162,  97],
  ACTION:   [231, 111,  81],
  CRITICAL: [230,  57,  70],
};

const TYPE_RGB: Record<string, [number, number, number]> = {
  Corridor:    [230,  84,  74],
  Supplier:    [ 90, 160, 220],
  Refinery:    [ 45, 190, 165],
  CrudeGrade:  [168, 120, 230],
  Port:        [ 70, 195, 225],
  SPRCavern:   [233, 196, 106],
  Authority:   [150, 165, 190],
  GeoEvent:    [244, 162,  97],
};

const RELATION_STYLE: Record<string, { color: [number, number, number]; width: number }> = {
  BYPASS_ROUTE:   { color: [ 80, 200, 130], width: 1.4 },
  EXPOSES:        { color: [230,  90,  70], width: 1.8 },
  FEEDS:          { color: [ 90, 150, 210], width: 0.9 },
  SUPPLIES:       { color: [ 90, 150, 210], width: 0.8 },
  EXPORTS_VIA:    { color: [140, 160, 190], width: 0.6 },
  CONFIGURED_FOR: { color: [110, 140, 175], width: 0.35 },
  SANCTIONED_BY:  { color: [220, 130,  60], width: 1.1 },
};
const DEFAULT_RELATION_STYLE = { color: [110, 140, 175] as [number, number, number], width: 0.55 };

// Gold border color for hub nodes (degree ≥ HUB_DEGREE).
const GOLD: [number, number, number, number] = [212, 175, 55, 255];
// Threshold above which a node is treated as a hub.
const HUB_DEGREE = 4;
// Fixed node radius — all nodes are the same size.
const NODE_R = 5;

const GREY: [number, number, number] = [110, 114, 122];

function desaturate(rgb: [number, number, number], amount: number): [number, number, number] {
  const a = Math.min(1, Math.max(0, amount));
  return [
    Math.round(rgb[0] + (GREY[0] - rgb[0]) * a),
    Math.round(rgb[1] + (GREY[1] - rgb[1]) * a),
    Math.round(rgb[2] + (GREY[2] - rgb[2]) * a),
  ];
}

const NODE_TRANSITIONS = {
  getRadius:    { duration: 200, easing: (t: number) => 1 - Math.pow(1 - t, 3) },
  getFillColor: 160,
  getLineColor: 160,
  getLineWidth: 160,
};
const EDGE_TRANSITIONS = { getColor: 160, getWidth: 160 };

export interface KnowledgeGraphMapProps {
  graph: GraphData;
  onNodeClick?: (node: GraphNode) => void;
  selectedId?: string | null;
  initialView?: { longitude: number; latitude: number; zoom: number };
  colorBy?: "risk" | "type";
}

export default function KnowledgeGraphMap({
  graph,
  onNodeClick,
  selectedId,
  initialView = { longitude: 48, latitude: 24, zoom: 3.1 },
  colorBy = "risk",
}: KnowledgeGraphMapProps) {
  const [hoverId, setHoverId] = useState<string | null>(null);
  const { theme } = useTheme();
  const light = theme === "light";
  const labelText: [number, number, number, number] = light ? [30, 45, 70, 255] : [210, 224, 240, 235];
  const labelOutline: [number, number, number, number] = light ? [255, 255, 255, 255] : [8, 14, 24, 255];

  const adjacency = useMemo(() => {
    const adj = new Map<string, Set<string>>();
    for (const e of graph.edges) {
      if (!adj.has(e.source)) adj.set(e.source, new Set());
      if (!adj.has(e.target)) adj.set(e.target, new Set());
      adj.get(e.source)!.add(e.target);
      adj.get(e.target)!.add(e.source);
    }
    return adj;
  }, [graph.edges]);

  const layers = useMemo(() => {
    const placed = graph.nodes.filter((n) => n.lat != null && n.lon != null);
    const byId   = new Map(placed.map((n) => [n.id, n]));

    const color = (n: GraphNode): [number, number, number] =>
      colorBy === "type" ? TYPE_RGB[n.type] ?? [120, 140, 170] : BAND_RGB[n.band] ?? BAND_RGB.CALM;

    const isHub = (n: GraphNode) => n.degree >= HUB_DEGREE;

    const focusId          = hoverId ?? selectedId;
    const neighborsOfFocus = focusId ? adjacency.get(focusId) : undefined;
    const inFocusSet       = (id: string) => !focusId || id === focusId || !!neighborsOfFocus?.has(id);

    // At rest, high-risk or hub nodes sit at full emphasis; quiet nodes recede slightly.
    const baselinePriority = (n: GraphNode) =>
      isHub(n) || n.band === "ACTION" || n.band === "CRITICAL" || n.band === "ELEVATED" ? 1 : 0.55;

    const nodeEmphasis = (n: GraphNode) =>
      focusId ? (inFocusSet(n.id) ? 1 : 0.12) : baselinePriority(n);

    // ── Edges ──────────────────────────────────────────────────────────────
    const edgeData = graph.edges
      .map((e) => {
        const s = byId.get(e.source);
        const t = byId.get(e.target);
        if (!s || !t) return null;
        const touchesFocus = focusId != null && (e.source === focusId || e.target === focusId);
        const style        = RELATION_STYLE[e.relation] ?? DEFAULT_RELATION_STYLE;
        const riskWeight   = Math.max(s.score, t.score);
        const emphasis     = focusId
          ? (touchesFocus ? 1 : 0.05)
          : Math.min(nodeEmphasis(s), nodeEmphasis(t));
        return { s, t, touchesFocus, style, riskWeight, emphasis };
      })
      .filter(Boolean) as {
        s: GraphNode; t: GraphNode; touchesFocus: boolean;
        style: { color: [number, number, number]; width: number };
        riskWeight: number; emphasis: number;
      }[];

    const edges = new LineLayer<(typeof edgeData)[number]>({
      id: "kg-edges",
      data: edgeData,
      getSourcePosition: (d) => [d.s.lon!, d.s.lat!],
      getTargetPosition: (d) => [d.t.lon!, d.t.lat!],
      getColor: (d) => {
        if (d.touchesFocus) return [56, 160, 210, 200];
        const base  = focusId ? desaturate(d.style.color, 1 - d.emphasis) : d.style.color;
        const [r, g, b] = base;
        // Very low baseline alpha — edges read as thin filaments, not strokes.
        const alpha = (light ? 16 + d.riskWeight * 60 : 10 + d.riskWeight * 50)
          * Math.max(d.emphasis, 0.05);
        return [r, g, b, Math.round(Math.min(195, alpha))];
      },
      getWidth: (d) =>
        d.touchesFocus
          ? 2.0
          : (d.style.width * 0.65 + d.riskWeight * 1.0) * Math.max(0.2, d.emphasis),
      widthUnits: "pixels",
      transitions: EDGE_TRANSITIONS,
      updateTriggers: {
        getColor: [hoverId, selectedId, theme],
        getWidth: [hoverId, selectedId],
      },
    });

    // ── Selection ring ──────────────────────────────────────────────────────
    const focusNode = placed.find((n) => n.id === selectedId);
    const selectionRing = new ScatterplotLayer<GraphNode>({
      id: "kg-selection-ring",
      data: focusNode ? [focusNode] : [],
      getPosition:  (d) => [d.lon!, d.lat!],
      getRadius:    () => NODE_R + 5,
      radiusUnits:  "pixels",
      getFillColor: [0, 0, 0, 0],
      getLineColor: [75, 184, 221, 255],
      lineWidthUnits: "pixels",
      getLineWidth: 1.5,
      stroked: true,
      filled:  false,
      pickable: false,
    });

    // ── Hub glow rings (gold border for high-degree nodes) ─────────────────
    // Drawn below the main nodes so the border is visible as a ring around them.
    const hubNodes = placed.filter(isHub);
    const hubRings = new ScatterplotLayer<GraphNode>({
      id: "kg-hub-rings",
      data: hubNodes,
      getPosition: (d) => [d.lon!, d.lat!],
      // Slightly larger than the node so the gold border peeks out all around.
      getRadius: () => NODE_R + 2.5,
      radiusUnits: "pixels",
      getFillColor: [0, 0, 0, 0],
      getLineColor: (d) => {
        const e = nodeEmphasis(d);
        return [GOLD[0], GOLD[1], GOLD[2], Math.round(GOLD[3] * Math.max(e, 0.15))];
      },
      lineWidthUnits: "pixels",
      getLineWidth: 2,
      stroked: true,
      filled:  false,
      pickable: false,
      updateTriggers: {
        getLineColor: [hoverId, selectedId],
      },
    });

    // ── Main node layer ────────────────────────────────────────────────────
    const nodes = new ScatterplotLayer<GraphNode>({
      id: "kg-nodes",
      data: placed,
      getPosition: (d) => [d.lon!, d.lat!],
      // Fixed radius for all nodes — hovered node gets a subtle pop only.
      getRadius: (d) => (d.id === hoverId ? NODE_R * 1.3 : NODE_R),
      radiusUnits: "pixels",
      radiusMinPixels: 3,
      radiusMaxPixels: 12,
      getFillColor: (d) => {
        const e    = nodeEmphasis(d);
        const base = e < 1 ? desaturate(color(d), 1 - e) : color(d);
        return [...base, Math.round(100 + 130 * e)] as [number, number, number, number];
      },
      getLineColor: (d) => {
        // Hub nodes get the gold outline drawn by the separate hubRings layer;
        // here we just need a subtle rim for non-hub nodes and white on hover/select.
        if (d.id === selectedId) return [235, 245, 255, 255];
        if (d.id === hoverId)    return [255, 255, 255, 240];
        // Non-hub: faint lighter version of the node colour.
        const e    = nodeEmphasis(d);
        const base = e < 1 ? desaturate(color(d), 1 - e) : color(d);
        const lit  = base.map((c) => Math.min(255, c + 40)) as [number, number, number];
        return [...lit, Math.round(80 + 120 * e)] as [number, number, number, number];
      },
      lineWidthUnits: "pixels",
      getLineWidth: (d) => (d.id === selectedId || d.id === hoverId ? 1.5 : 0.7),
      stroked:   true,
      pickable:  true,
      antialiasing: true,
      transitions: NODE_TRANSITIONS,
      onClick: (info) => info.object && onNodeClick?.(info.object as GraphNode),
      onHover: (info) => setHoverId((info.object as GraphNode)?.id ?? null),
      updateTriggers: {
        getRadius:    [hoverId],
        getFillColor: [colorBy, hoverId, selectedId],
        getLineColor: [colorBy, hoverId, selectedId],
        getLineWidth: [hoverId, selectedId],
      },
    });

    // ── Labels ─────────────────────────────────────────────────────────────
    const labels = new TextLayer<GraphNode>({
      id: "kg-labels",
      data: placed,
      getPosition: (d) => [d.lon!, d.lat!],
      getText:     (d) => d.name,
      getSize:     (d) => (d.id === hoverId ? 13 : 11),
      getColor:    (d) => {
        const e = nodeEmphasis(d);
        const [r, g, b, a] = labelText;
        return [r, g, b, Math.round(a * (0.3 + 0.7 * e))];
      },
      getPixelOffset:       () => [0, -(NODE_R + 7)],
      getTextAnchor:        "middle",
      getAlignmentBaseline: "bottom",
      fontFamily: "Inter, sans-serif",
      fontWeight: 600,
      outlineWidth: 3,
      outlineColor: labelOutline,
      transitions: { getSize: 150, getColor: 160 },
      updateTriggers: {
        getColor: [theme, hoverId, selectedId],
        getSize:  [hoverId],
      },
      fontSettings: { sdf: true },
      extensions: [new CollisionFilterExtension()],
      ...({
        collisionEnabled: true,
        getCollisionPriority: (d: GraphNode) =>
          d.degree + (d.id === selectedId ? 1000 : 0) + (d.id === hoverId ? 2000 : 0),
        collisionTestProps: { sizeScale: 2.4 },
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
      } as any),
    });

    // Hub rings drawn before nodes so the gold border is underneath the fill.
    return [edges, selectionRing, hubRings, nodes, labels];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph, onNodeClick, selectedId, colorBy, hoverId, theme, adjacency, light, labelText, labelOutline]);

  return (
    <DeckGL
      initialViewState={initialView}
      controller={true}
      layers={layers}
      getCursor={({ isDragging }) => (isDragging ? "grabbing" : hoverId ? "pointer" : "grab")}
      getTooltip={({ object }) => {
        const n = object as GraphNode | undefined;
        if (!n?.name) return null;
        return {
          html: `<b>${n.name}</b><br/>${n.type} · ${n.band} ${(n.score * 100).toFixed(0)}%` +
            (n.degree >= HUB_DEGREE ? ` · <span style="color:#d4af37">★ hub · ${n.degree} links</span>` : ` · ${n.degree} links`),
          style: {
            background: "#131318",
            color: "#eef0f4",
            fontSize: "11px",
            padding: "5px 8px",
            borderRadius: "3px",
            border: "1px solid #34343f",
          },
        };
      }}
      style={{ position: "absolute", top: "0", left: "0", right: "0", bottom: "0" }}
    >
      <BaseMap reuseMaps mapStyle={basemapFor(theme)} attributionControl={false} />
    </DeckGL>
  );
}
