import { useMemo, useState, useEffect, useRef } from "react";
import DeckGL from "@deck.gl/react";
import { WebMercatorViewport, FlyToInterpolator } from "@deck.gl/core";
import { ScatterplotLayer, LineLayer, TextLayer, ArcLayer, PathLayer } from "@deck.gl/layers";
import { HeatmapLayer } from "@deck.gl/aggregation-layers";
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
  Corridor:        [230,  84,  74],
  Supplier:        [ 90, 160, 220],
  Refinery:        [ 45, 190, 165],
  CrudeGrade:      [168, 120, 230],
  Port:            [ 70, 195, 225],
  SPRCavern:       [233, 196, 106],
  Authority:       [150, 165, 190],
  GeoEvent:        [244, 162,  97],
  ProductionField: [255, 140,  50],   // G7 — amber/orange for wellheads
  DistributionHub: [120, 210, 100],   // G7 — green for demand hubs
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

// Gold ring for nodes in top percentile of degree.
const GOLD: [number, number, number, number] = [212, 175, 55, 255];
// What percentile qualifies as a hub (top 10%).
const HUB_PERCENTILE = 0.90;
// Fixed node radius — uniform for all nodes.
const NODE_R = 5;
// Padding (pixels) when fitting the viewport to a selection's neighbourhood.
const FIT_PAD = 80;

const GREY: [number, number, number] = [110, 114, 122];

// G8 — Static shipping lane polylines (public data, EIA chokepoints + Admiralty lanes)
// Each route has [lon, lat] waypoints and a corridor_id that maps to risk_score
const SHIPPING_LANES: { id: string; name: string; path: [number, number][] }[] = [
  {
    id: "corridor_hormuz",
    name: "Strait of Hormuz",
    path: [[50.0,26.5],[56.4,26.2],[57.8,24.5],[60.0,22.5],[63.5,20.5],[67.0,21.0],[70.0,22.5]],
  },
  {
    id: "corridor_bab_el_mandeb",
    name: "Bab-el-Mandeb",
    path: [[32.5,30.2],[33.5,27.0],[37.0,22.0],[43.3,12.5],[47.0,11.5],[51.5,12.0],[56.0,14.5],[60.0,20.0],[63.5,20.5],[67.0,21.0],[70.0,22.5]],
  },
  {
    id: "corridor_suez",
    name: "Suez Canal",
    path: [[30.0,31.8],[32.5,30.2]],
  },
  {
    id: "corridor_malacca",
    name: "Strait of Malacca",
    path: [[102.0,2.5],[98.0,4.0],[94.5,6.5],[88.0,9.0],[80.0,12.0],[74.0,18.0],[70.0,22.5]],
  },
  {
    id: "bypass_cape",
    name: "Cape of Good Hope (Bypass)",
    path: [[30.0,31.8],[15.0,10.0],[5.0,-10.0],[18.4,-34.0],[30.0,-28.0],[40.0,-15.0],[48.0,-5.0],[58.0,0.0],[65.0,10.0],[70.0,22.5]],
  },
  {
    id: "bypass_petroline",
    name: "Petroline (East–West Pipeline)",
    path: [[50.0,26.5],[46.5,24.8],[43.5,22.5],[39.5,20.0],[37.0,17.5]],
  },
];

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

type ViewState = {
  longitude: number;
  latitude: number;
  zoom: number;
  pitch?: number;
  bearing?: number;
  transitionDuration?: number;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  transitionInterpolator?: any;
};

export interface KnowledgeGraphMapProps {
  graph: GraphData;
  onNodeClick?: (node: GraphNode) => void;
  selectedId?: string | null;
  initialView?: { longitude: number; latitude: number; zoom: number };
  colorBy?: "risk" | "type";
  showFlows?: boolean;
  showHeatmap?: boolean;
  showRoutes?: boolean;
  blastRadiusId?: string | null;
  // corridor id → risk score (0–1), used to color route polylines
  corridorRisk?: Record<string, number>;
}

export default function KnowledgeGraphMap({
  graph,
  onNodeClick,
  selectedId,
  initialView = { longitude: 48, latitude: 24, zoom: 3.1 },
  colorBy = "risk",
  showFlows = false,
  showHeatmap = false,
  showRoutes = true,
  blastRadiusId = null,
  corridorRisk = {},
}: KnowledgeGraphMapProps) {
  const [hoverId, setHoverId] = useState<string | null>(null);
  // Animation tick for flow pulses (0–1 looping).
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!showFlows) return;
    let raf: number;
    const start = performance.now();
    const loop = (now: number) => {
      setTick(((now - start) % 3000) / 3000);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [showFlows]);
  const { theme } = useTheme();
  const light = theme === "light";
  const labelText: [number, number, number, number] = light ? [30, 45, 70, 255] : [210, 224, 240, 235];
  const labelOutline: [number, number, number, number] = light ? [255, 255, 255, 255] : [8, 14, 24, 255];

  const [viewState, setViewState] = useState<ViewState>(initialView);
  const containerRef = useRef<HTMLDivElement>(null);

  // Adjacency map — who's connected to whom.
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

  // Hub threshold: top HUB_PERCENTILE of degree values.
  const hubThreshold = useMemo(() => {
    const placed = graph.nodes.filter((n) => n.lat != null && n.lon != null);
    if (placed.length === 0) return Infinity;
    const degrees = placed.map((n) => n.degree).sort((a, b) => a - b);
    const idx = Math.floor(degrees.length * HUB_PERCENTILE);
    return degrees[idx] ?? Infinity;
  }, [graph.nodes]);

  // Fly to fit the selected node + its neighbours whenever selection changes.
  useEffect(() => {
    if (!selectedId) return;
    const byId = new Map(graph.nodes.filter((n) => n.lat != null && n.lon != null).map((n) => [n.id, n]));
    const center = byId.get(selectedId);
    if (!center) return;

    const neighbors = adjacency.get(selectedId) ?? new Set<string>();
    const pts: [number, number][] = [[center.lon!, center.lat!]];
    for (const nid of neighbors) {
      const n = byId.get(nid);
      if (n) pts.push([n.lon!, n.lat!]);
    }

    if (pts.length === 1) {
      // No neighbours visible — just zoom to the node itself.
      setViewState((vs) => ({
        ...vs,
        longitude: center.lon!,
        latitude: center.lat!,
        zoom: Math.max(vs.zoom, 5),
        transitionDuration: 700,
        transitionInterpolator: new FlyToInterpolator({ speed: 1.4 }),
      }));
      return;
    }

    const lons = pts.map((p) => p[0]);
    const lats = pts.map((p) => p[1]);
    const minLon = Math.min(...lons), maxLon = Math.max(...lons);
    const minLat = Math.min(...lats), maxLat = Math.max(...lats);

    const w = containerRef.current?.clientWidth ?? window.innerWidth;
    const h = containerRef.current?.clientHeight ?? window.innerHeight;

    try {
      const vp = new WebMercatorViewport({ width: w, height: h });
      const fitted = vp.fitBounds(
        [[minLon, minLat], [maxLon, maxLat]],
        { padding: FIT_PAD }
      );
      setViewState({
        longitude: fitted.longitude,
        latitude: fitted.latitude,
        zoom: Math.min(fitted.zoom, 7),
        transitionDuration: 700,
        transitionInterpolator: new FlyToInterpolator({ speed: 1.4 }),
      });
    } catch {
      // fitBounds can fail on degenerate inputs — fall back to centering.
      setViewState((vs) => ({
        ...vs,
        longitude: (minLon + maxLon) / 2,
        latitude: (minLat + maxLat) / 2,
        transitionDuration: 600,
        transitionInterpolator: new FlyToInterpolator({ speed: 1.2 }),
      }));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  // Blast-radius: collect all nodes within 2 hops of blastRadiusId.
  const blastSet = useMemo(() => {
    if (!blastRadiusId) return new Set<string>();
    const visited = new Set<string>([blastRadiusId]);
    let frontier = [blastRadiusId];
    for (let hop = 0; hop < 2; hop++) {
      const next: string[] = [];
      for (const id of frontier) {
        for (const nb of adjacency.get(id) ?? []) {
          if (!visited.has(nb)) { visited.add(nb); next.push(nb); }
        }
      }
      frontier = next;
    }
    return visited;
  }, [blastRadiusId, adjacency]);

  const layers = useMemo(() => {
    const placed = graph.nodes.filter((n) => n.lat != null && n.lon != null);
    const byId   = new Map(placed.map((n) => [n.id, n]));

    const color = (n: GraphNode): [number, number, number] =>
      colorBy === "type" ? TYPE_RGB[n.type] ?? [120, 140, 170] : BAND_RGB[n.band] ?? BAND_RGB.CALM;

    const isHub = (n: GraphNode) => n.degree >= hubThreshold;

    const focusId          = hoverId ?? selectedId;
    const neighborsOfFocus = focusId ? adjacency.get(focusId) : undefined;
    const inFocusSet       = (id: string) => !focusId || id === focusId || !!neighborsOfFocus?.has(id);

    const baselinePriority = (n: GraphNode) =>
      isHub(n) || n.band === "ACTION" || n.band === "CRITICAL" || n.band === "ELEVATED" ? 1 : 0.55;

    const nodeEmphasis = (n: GraphNode) =>
      focusId ? (inFocusSet(n.id) ? 1 : 0.12) : baselinePriority(n);

    // ── Edges — hidden at rest, revealed only when a node is focused ────────
    const edgeData = graph.edges
      .map((e) => {
        const s = byId.get(e.source);
        const t = byId.get(e.target);
        if (!s || !t) return null;
        const touchesFocus = focusId != null && (e.source === focusId || e.target === focusId);
        const style        = RELATION_STYLE[e.relation] ?? DEFAULT_RELATION_STYLE;
        const riskWeight   = Math.max(s.score, t.score);
        return { s, t, touchesFocus, style, riskWeight };
      })
      .filter(Boolean) as {
        s: GraphNode; t: GraphNode; touchesFocus: boolean;
        style: { color: [number, number, number]; width: number };
        riskWeight: number;
      }[];

    const edges = new LineLayer<(typeof edgeData)[number]>({
      id: "kg-edges",
      data: edgeData,
      getSourcePosition: (d) => [d.s.lon!, d.s.lat!],
      getTargetPosition: (d) => [d.t.lon!, d.t.lat!],
      getColor: (d) => {
        // Fully invisible at rest. Only appear when something is focused.
        if (!focusId) return [0, 0, 0, 0];
        if (d.touchesFocus) {
          const [r, g, b] = d.style.color;
          return [r, g, b, 210];
        }
        // Edges between in-focus neighbours: very faint.
        const bothInFocus = inFocusSet(d.s.id) && inFocusSet(d.t.id);
        if (bothInFocus) {
          const base = desaturate(d.style.color, 0.5);
          return [...base, Math.round(25 + d.riskWeight * 40)] as [number, number, number, number];
        }
        return [0, 0, 0, 0];
      },
      getWidth: (d) => {
        if (!focusId) return 0;
        if (d.touchesFocus) return d.style.width * 0.9 + d.riskWeight * 0.8;
        return 0.4;
      },
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

    // ── Gold hub rings — top percentile only ────────────────────────────────
    const hubNodes = placed.filter(isHub);
    const hubRings = new ScatterplotLayer<GraphNode>({
      id: "kg-hub-rings",
      data: hubNodes,
      getPosition: (d) => [d.lon!, d.lat!],
      getRadius:   () => NODE_R + 2.5,
      radiusUnits: "pixels",
      getFillColor: [0, 0, 0, 0],
      getLineColor: (d) => {
        const e = nodeEmphasis(d);
        return [GOLD[0], GOLD[1], GOLD[2], Math.round(GOLD[3] * Math.max(e, 0.2))];
      },
      lineWidthUnits: "pixels",
      getLineWidth: 2,
      stroked: true,
      filled:  false,
      pickable: false,
      updateTriggers: { getLineColor: [hoverId, selectedId] },
    });

    // ── Nodes ───────────────────────────────────────────────────────────────
    const nodes = new ScatterplotLayer<GraphNode>({
      id: "kg-nodes",
      data: placed,
      getPosition: (d) => [d.lon!, d.lat!],
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
        if (d.id === selectedId) return [235, 245, 255, 255];
        if (d.id === hoverId)    return [255, 255, 255, 240];
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

    // ── Heatmap — risk density ───────────────────────────────────────────────
    const heatmapData = placed.map((n) => ({
      coordinates: [n.lon!, n.lat!] as [number, number],
      weight: n.score,
    }));
    const heatmap = showHeatmap ? new HeatmapLayer({
      id: "kg-heatmap",
      data: heatmapData,
      getPosition: (d) => d.coordinates,
      getWeight: (d) => d.weight,
      radiusPixels: 80,
      intensity: 1.2,
      threshold: 0.05,
      colorRange: [
        [45, 178, 158, 40],
        [233, 196, 106, 100],
        [244, 162, 97, 160],
        [231, 111, 81, 200],
        [230, 57, 70, 230],
      ] as [number, number, number, number][],
    }) : null;

    // ── Flow arcs — corridor supply routes ───────────────────────────────────
    // Corridor edges between placed nodes only; animated via offset.
    const corridorEdges = graph.edges
      .filter((e) => {
        const s = byId.get(e.source);
        const t = byId.get(e.target);
        return s && t && (s.type === "Corridor" || t.type === "Corridor" || s.type === "Port" || t.type === "Port");
      })
      .map((e) => ({ s: byId.get(e.source)!, t: byId.get(e.target)! }))
      .filter((d) => d.s && d.t);

    const flows = showFlows && corridorEdges.length > 0 ? new ArcLayer({
      id: "kg-flows",
      data: corridorEdges,
      getSourcePosition: (d) => [d.s.lon!, d.s.lat!],
      getTargetPosition: (d) => [d.t.lon!, d.t.lat!],
      getSourceColor: [70, 195, 225, 60],
      getTargetColor: [70, 195, 225, 200],
      getWidth: 1.5,
      widthUnits: "pixels",
      greatCircle: true,
      getHeight: 0.3,
    }) : null;

    // Animated pulse dots on flows
    const pulseData = showFlows
      ? corridorEdges.flatMap((d, i) => {
          const t = (tick + i * 0.17) % 1;
          const lon = d.s.lon! + (d.t.lon! - d.s.lon!) * t;
          const lat = d.s.lat! + (d.t.lat! - d.s.lat!) * t;
          return [{ lon, lat, alpha: Math.sin(t * Math.PI) }];
        })
      : [];

    const flowPulses = showFlows && pulseData.length > 0
      ? new ScatterplotLayer({
          id: "kg-flow-pulses",
          data: pulseData,
          getPosition: (d: { lon: number; lat: number; alpha: number }) => [d.lon, d.lat],
          getRadius: () => 4,
          radiusUnits: "pixels",
          getFillColor: (d: { lon: number; lat: number; alpha: number }) => [
            70, 220, 255, Math.round(d.alpha * 220),
          ],
          pickable: false,
          updateTriggers: { getPosition: tick, getFillColor: tick },
        })
      : null;

    // ── Blast radius highlight ───────────────────────────────────────────────
    const blastNodes = blastRadiusId
      ? placed.filter((n) => blastSet.has(n.id) && n.id !== blastRadiusId)
      : [];
    const blastRings = blastRadiusId
      ? new ScatterplotLayer<GraphNode>({
          id: "kg-blast-rings",
          data: blastNodes,
          getPosition: (d) => [d.lon!, d.lat!],
          getRadius: () => NODE_R + 8,
          radiusUnits: "pixels",
          getFillColor: [0, 0, 0, 0],
          getLineColor: [255, 120, 50, 200],
          lineWidthUnits: "pixels",
          getLineWidth: 1.5,
          stroked: true,
          filled: false,
          pickable: false,
        })
      : null;

    // ── G8 Route polylines — shipping lane geometries as PathLayer ───────────
    function riskToLaneColor(risk: number): [number, number, number, number] {
      if (risk >= 0.70) return [230, 57, 70, 200];   // ACTION/CRITICAL — red
      if (risk >= 0.45) return [244, 162, 97, 190];   // ELEVATED — orange
      if (risk >= 0.25) return [233, 196, 106, 160];  // WATCH — amber
      return [70, 195, 225, 120];                      // CALM — cyan
    }
    const routeLaneData = SHIPPING_LANES.map((lane) => ({
      ...lane,
      risk: corridorRisk[lane.id] ?? 0,
      isBypass: lane.id.startsWith("bypass"),
    }));
    type RouteLane = { id: string; name: string; path: [number, number][]; risk: number; isBypass: boolean };
    const routePaths = showRoutes ? new PathLayer<RouteLane>({
      id: "kg-route-paths",
      data: routeLaneData,
      getPath: (d) => d.path,
      getColor: (d) => riskToLaneColor(d.risk),
      getWidth: (d) => d.isBypass ? 1.5 : 2.5,
      widthUnits: "pixels",
      widthMinPixels: 1,
      widthMaxPixels: 5,
      pickable: true,
      jointRounded: true,
      capRounded: true,
      miterLimit: 2,
    }) : null;

    return [
      routePaths,
      heatmap,
      flows,
      flowPulses,
      edges,
      blastRings,
      selectionRing,
      hubRings,
      nodes,
      labels,
    ].filter(Boolean);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph, onNodeClick, selectedId, colorBy, hoverId, theme, adjacency, hubThreshold, light, labelText, labelOutline, showHeatmap, showFlows, showRoutes, corridorRisk, tick, blastRadiusId, blastSet]);

  return (
    <div ref={containerRef} style={{ position: "absolute", inset: 0 }}>
      <DeckGL
        viewState={viewState}
        onViewStateChange={({ viewState: vs }) => setViewState(vs as ViewState)}
        controller={true}
        layers={layers}
        getCursor={({ isDragging }) => (isDragging ? "grabbing" : hoverId ? "pointer" : "grab")}
        getTooltip={({ object }) => {
          const n = object as GraphNode | undefined;
          if (!n?.name) return null;
          const hub = n.degree >= hubThreshold;
          return {
            html: `<b>${n.name}</b><br/>${n.type} · ${n.band} ${(n.score * 100).toFixed(0)}%` +
              (hub
                ? ` · <span style="color:#d4af37">★ ${n.degree} links</span>`
                : ` · ${n.degree} links`),
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
    </div>
  );
}
