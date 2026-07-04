import { useMemo, useState, useCallback, useRef } from "react";
import DeckGL from "@deck.gl/react";
import { WebMercatorViewport } from "@deck.gl/core";
import { ScatterplotLayer, LineLayer, TextLayer } from "@deck.gl/layers";
import { CollisionFilterExtension } from "@deck.gl/extensions";
import { Map as BaseMap } from "react-map-gl/maplibre";
import type { GraphData, GraphNode } from "../api/types";
import { useTheme, basemapFor } from "../theme";

const BAND_RGB: Record<string, [number, number, number]> = {
  CALM: [45, 178, 158],
  WATCH: [233, 196, 106],
  ELEVATED: [244, 162, 97],
  ACTION: [231, 111, 81],
  CRITICAL: [230, 57, 70],
};

const TYPE_RGB: Record<string, [number, number, number]> = {
  Corridor: [230, 84, 74],
  Supplier: [90, 160, 220],
  Refinery: [45, 190, 165],
  CrudeGrade: [168, 120, 230],
  Port: [70, 195, 225],
  SPRCavern: [233, 196, 106],
  Authority: [150, 165, 190],
  GeoEvent: [244, 162, 97],
};

// Relation styles — kept same as before, but base alpha is applied much lower
// everywhere in the edge rendering so the map reads cleaner at rest.
const RELATION_STYLE: Record<string, { color: [number, number, number]; width: number }> = {
  BYPASS_ROUTE: { color: [80, 200, 130], width: 1.5 },
  EXPOSES:      { color: [230, 90, 70],  width: 2.0 },
  FEEDS:        { color: [90, 150, 210], width: 1.0 },
  SUPPLIES:     { color: [90, 150, 210], width: 0.9 },
  EXPORTS_VIA:  { color: [140, 160, 190], width: 0.7 },
  CONFIGURED_FOR: { color: [110, 140, 175], width: 0.4 },
  SANCTIONED_BY: { color: [220, 130, 60], width: 1.2 },
};
const DEFAULT_RELATION_STYLE = { color: [110, 140, 175] as [number, number, number], width: 0.6 };

const GREY: [number, number, number] = [110, 114, 122];

function desaturate(rgb: [number, number, number], amount: number): [number, number, number] {
  const a = Math.min(1, Math.max(0, amount));
  return [
    Math.round(rgb[0] + (GREY[0] - rgb[0]) * a),
    Math.round(rgb[1] + (GREY[1] - rgb[1]) * a),
    Math.round(rgb[2] + (GREY[2] - rgb[2]) * a),
  ];
}

const POP_TRANSITIONS = {
  getPosition: { duration: 280, easing: (t: number) => 1 - Math.pow(1 - t, 3) },
  getRadius: { duration: 220, easing: (t: number) => 1 - Math.pow(1 - t, 3) },
  getFillColor: 180,
  getLineColor: 180,
  getLineWidth: 180,
};
const EDGE_TRANSITIONS = { getColor: 180, getWidth: 180 };

// How many pixels from the hovered node triggers cluster-spread.
const CLUSTER_PX = 36;
// How far apart to push cluster members (pixels).
const SPREAD_PX = 28;

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

  // Track the live viewport so we can project lat/lon → pixels for cluster detection.
  const [viewState, setViewState] = useState<{
    longitude: number; latitude: number; zoom: number;
    pitch?: number; bearing?: number;
  }>(initialView);
  const containerRef = useRef<HTMLDivElement>(null);

  // jitter: per-node geographic offset (lon, lat) applied when a cluster is spread.
  const [jitter, setJitter] = useState<Map<string, [number, number]>>(new Map());

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

  // Compute cluster repulsion whenever the hovered node changes.
  const handleHover = useCallback(
    (info: { object?: unknown }) => {
      const node = info.object as GraphNode | undefined;
      if (!node?.id) {
        setHoverId(null);
        setJitter(new Map());
        return;
      }
      setHoverId(node.id);

      const placed = graph.nodes.filter((n) => n.lat != null && n.lon != null);
      const w = containerRef.current?.clientWidth ?? window.innerWidth;
      const h = containerRef.current?.clientHeight ?? window.innerHeight;

      const vp = new WebMercatorViewport({
        width: w,
        height: h,
        longitude: viewState.longitude,
        latitude: viewState.latitude,
        zoom: viewState.zoom,
        pitch: viewState.pitch ?? 0,
        bearing: viewState.bearing ?? 0,
      });

      const [hx, hy] = vp.project([node.lon!, node.lat!]) as [number, number];

      // Find all nodes that overlap the hovered node on screen.
      const cluster = placed.filter((n) => {
        if (n.id === node.id) return false;
        const [px, py] = vp.project([n.lon!, n.lat!]) as [number, number];
        return Math.hypot(px - hx, py - hy) < CLUSTER_PX;
      });

      if (cluster.length === 0) {
        setJitter(new Map());
        return;
      }

      // Spread all cluster members (including the hovered one) evenly around their centroid.
      const all = [node, ...cluster];
      const cx = all.reduce((s, n) => {
        const [px] = vp.project([n.lon!, n.lat!]) as [number, number];
        return s + px;
      }, 0) / all.length;
      const cy = all.reduce((s, n) => {
        const [, py] = vp.project([n.lon!, n.lat!]) as [number, number];
        return s + py;
      }, 0) / all.length;

      const newJitter = new Map<string, [number, number]>();
      all.forEach((n, i) => {
        const angle = (2 * Math.PI * i) / all.length - Math.PI / 2;
        const tx = cx + Math.cos(angle) * SPREAD_PX;
        const ty = cy + Math.sin(angle) * SPREAD_PX;
        const [lon, lat] = vp.unproject([tx, ty]) as [number, number];
        newJitter.set(n.id, [lon - n.lon!, lat - n.lat!]);
      });
      setJitter(newJitter);
    },
    [graph.nodes, viewState]
  );

  const layers = useMemo(() => {
    const placed = graph.nodes.filter((n) => n.lat != null && n.lon != null);
    const byId = new Map(placed.map((n) => [n.id, n]));

    const color = (n: GraphNode): [number, number, number] =>
      colorBy === "type" ? TYPE_RGB[n.type] ?? [120, 140, 170] : BAND_RGB[n.band] ?? BAND_RGB.CALM;

    const baseRadius = (n: GraphNode) => 2.5 + Math.sqrt(n.degree) * 1.15;

    // Jittered position: base + geographic offset computed from pixel spread.
    const pos = (n: GraphNode): [number, number] => {
      const off = jitter.get(n.id);
      return off ? [n.lon! + off[0], n.lat! + off[1]] : [n.lon!, n.lat!];
    };

    const focusId = hoverId ?? selectedId;
    const neighborsOfFocus = focusId ? adjacency.get(focusId) : undefined;
    const inFocusSet = (id: string) => !focusId || id === focusId || !!neighborsOfFocus?.has(id);

    const baselinePriority = (n: GraphNode) =>
      n.degree >= 3 || n.band === "ACTION" || n.band === "CRITICAL" || n.band === "ELEVATED" ? 1 : 0.55;

    const nodeEmphasis = (n: GraphNode) => (focusId ? (inFocusSet(n.id) ? 1 : 0.12) : baselinePriority(n));

    const edgeData = graph.edges
      .map((e) => {
        const s = byId.get(e.source);
        const t = byId.get(e.target);
        if (!s || !t) return null;
        const touchesFocus = focusId != null && (e.source === focusId || e.target === focusId);
        const style = RELATION_STYLE[e.relation] ?? DEFAULT_RELATION_STYLE;
        const riskWeight = Math.max(s.score, t.score);
        const emphasis = focusId ? (touchesFocus ? 1 : 0.05) : Math.min(nodeEmphasis(s), nodeEmphasis(t));
        return { s, t, touchesFocus, relation: e.relation, style, riskWeight, emphasis };
      })
      .filter(Boolean) as {
        s: GraphNode; t: GraphNode; touchesFocus: boolean; relation: string;
        style: { color: [number, number, number]; width: number }; riskWeight: number; emphasis: number;
      }[];

    const edges = new LineLayer<(typeof edgeData)[number]>({
      id: "kg-edges",
      data: edgeData,
      // Use jittered positions so edges follow their nodes when spread.
      getSourcePosition: (d) => pos(d.s),
      getTargetPosition: (d) => pos(d.t),
      getColor: (d) => {
        if (d.touchesFocus) return [56, 160, 210, 210];
        const base = focusId ? desaturate(d.style.color, 1 - d.emphasis) : d.style.color;
        const [r, g, b] = base;
        // Much lower default alpha — edges read as delicate connective tissue, not bold lines.
        // High-risk edges get more visible; low-risk structural wiring nearly disappears.
        const alpha = (light
          ? 18 + d.riskWeight * 65
          : 12 + d.riskWeight * 55) * Math.max(d.emphasis, 0.05);
        return [r, g, b, Math.round(Math.min(200, alpha))];
      },
      getWidth: (d) =>
        d.touchesFocus
          ? 2.2
          : (d.style.width * 0.7 + d.riskWeight * 1.2) * Math.max(0.25, d.emphasis),
      widthUnits: "pixels",
      transitions: EDGE_TRANSITIONS,
      updateTriggers: {
        getSourcePosition: [jitter],
        getTargetPosition: [jitter],
        getColor: [hoverId, selectedId, theme],
        getWidth: [hoverId, selectedId],
      },
    });

    const focusNode = placed.find((n) => n.id === selectedId);
    const selectionRing = new ScatterplotLayer<GraphNode>({
      id: "kg-selection-ring",
      data: focusNode ? [focusNode] : [],
      getPosition: (d) => pos(d),
      getRadius: (d) => baseRadius(d) + 5,
      radiusUnits: "pixels",
      getFillColor: [0, 0, 0, 0],
      getLineColor: [75, 184, 221, 255],
      lineWidthUnits: "pixels",
      getLineWidth: 1,
      stroked: true,
      filled: false,
      pickable: false,
    });

    const nodes = new ScatterplotLayer<GraphNode>({
      id: "kg-nodes",
      data: placed,
      getPosition: (d) => pos(d),
      getRadius: (d) => {
        const r = baseRadius(d);
        if (d.id === hoverId) return r * 1.55;
        if (focusId && inFocusSet(d.id)) return r * 1.1;
        return r;
      },
      radiusUnits: "pixels",
      radiusMinPixels: 2,
      radiusMaxPixels: 20,
      getFillColor: (d) => {
        const e = nodeEmphasis(d);
        const base = e < 1 ? desaturate(color(d), 1 - e) : color(d);
        return [...base, Math.round(90 + 140 * e)] as [number, number, number, number];
      },
      getLineColor: (d) => {
        if (d.id === selectedId) return [235, 245, 255, 255];
        if (d.id === hoverId) return [255, 255, 255, 255];
        const e = nodeEmphasis(d);
        const base = e < 1 ? desaturate(color(d), 1 - e) : color(d);
        const lit = base.map((c) => Math.min(255, c + 45)) as [number, number, number];
        return [...lit, Math.round(100 + 155 * e)] as [number, number, number, number];
      },
      lineWidthUnits: "pixels",
      getLineWidth: (d) => (d.id === selectedId ? 2 : d.id === hoverId ? 2.2 : 0.8),
      stroked: true,
      pickable: true,
      antialiasing: true,
      transitions: POP_TRANSITIONS,
      onClick: (info) => info.object && onNodeClick?.(info.object as GraphNode),
      onHover: handleHover,
      updateTriggers: {
        getPosition: [jitter],
        getRadius: [hoverId, selectedId],
        getFillColor: [colorBy, hoverId, selectedId],
        getLineColor: [colorBy, hoverId, selectedId],
        getLineWidth: [hoverId, selectedId],
      },
    });

    const labels = new TextLayer<GraphNode>({
      id: "kg-labels",
      data: placed,
      getPosition: (d) => pos(d),
      getText: (d) => d.name,
      getSize: (d) => (d.id === hoverId ? 13 : 11),
      getColor: (d) => {
        const e = nodeEmphasis(d);
        const [r, g, b, a] = labelText;
        return [r, g, b, Math.round(a * (0.35 + 0.65 * e))];
      },
      getPixelOffset: (d) => [0, -(baseRadius(d) + (d.id === hoverId ? 10 : 8))],
      getTextAnchor: "middle",
      getAlignmentBaseline: "bottom",
      fontFamily: "Inter, sans-serif",
      fontWeight: 600,
      outlineWidth: 3,
      outlineColor: labelOutline,
      transitions: { getSize: 150, getColor: 180 },
      updateTriggers: {
        getPosition: [jitter],
        getColor: [theme, hoverId, selectedId],
        getSize: [hoverId],
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

    return [edges, selectionRing, nodes, labels];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph, onNodeClick, selectedId, colorBy, hoverId, theme, adjacency, jitter, handleHover, light, labelText, labelOutline]);

  return (
    <div ref={containerRef} style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0 }}>
      <DeckGL
        viewState={viewState}
        onViewStateChange={({ viewState: vs }) =>
          setViewState(vs as typeof viewState)
        }
        controller={true}
        layers={layers}
        getCursor={({ isDragging }) => (isDragging ? "grabbing" : hoverId ? "pointer" : "grab")}
        getTooltip={({ object }) =>
          object && (object as GraphNode).name
            ? {
                html: `<b>${(object as GraphNode).name}</b><br/>${(object as GraphNode).type} · ${
                  (object as GraphNode).band
                } ${((object as GraphNode).score * 100).toFixed(0)}% · ${(object as GraphNode).degree} links`,
                style: {
                  background: "#131318",
                  color: "#eef0f4",
                  fontSize: "11px",
                  padding: "5px 8px",
                  borderRadius: "3px",
                  border: "1px solid #34343f",
                },
              }
            : null
        }
        style={{ position: "absolute", top: "0", left: "0", right: "0", bottom: "0" }}
      >
        <BaseMap reuseMaps mapStyle={basemapFor(theme)} attributionControl={false} />
      </DeckGL>
    </div>
  );
}
