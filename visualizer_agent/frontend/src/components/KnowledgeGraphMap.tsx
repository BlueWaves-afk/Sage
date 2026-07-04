import { useMemo, useState } from "react";
import DeckGL from "@deck.gl/react";
import { ScatterplotLayer, LineLayer, TextLayer } from "@deck.gl/layers";
import { CollisionFilterExtension } from "@deck.gl/extensions";
import { Map as BaseMap } from "react-map-gl/maplibre";
import type { GraphData, GraphNode } from "../api/types";
import { useTheme, basemapFor } from "../theme";

// Risk-band → colour (traffic-light gradient, matching the Obsidian graph config).
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

// Relationship-type colouring — a "structural" corridor→refinery FEEDS edge reads
// very differently from a BYPASS_ROUTE (a reroute *around* risk) or an EXPOSES edge
// (literally how risk propagates from a disrupted corridor to a refinery). Styling
// every edge identically made the map look like "everything connects to everything";
// this makes the relationship kind and its risk weight visible at a glance.
const RELATION_STYLE: Record<string, { color: [number, number, number]; width: number }> = {
  BYPASS_ROUTE: { color: [80, 200, 130], width: 1.6 },       // reroute around risk — green
  EXPOSES: { color: [230, 90, 70], width: 2.2 },              // risk propagation — red, thick
  FEEDS: { color: [90, 150, 210], width: 1.1 },                // corridor → port throughput
  SUPPLIES: { color: [90, 150, 210], width: 1.0 },             // port → refinery throughput
  EXPORTS_VIA: { color: [140, 160, 190], width: 0.8 },
  CONFIGURED_FOR: { color: [110, 140, 175], width: 0.5 },      // grade compatibility — least salient
  SANCTIONED_BY: { color: [220, 130, 60], width: 1.3 },
};
const DEFAULT_RELATION_STYLE = { color: [110, 140, 175] as [number, number, number], width: 0.7 };

const GREY: [number, number, number] = [110, 114, 122];

/** Blend a colour toward neutral grey — used to visually "grey out" de-emphasised
 * nodes/edges, not just fade their opacity (fading alone reads as "thin", not
 * "de-prioritised", on a dark basemap). */
function desaturate(rgb: [number, number, number], amount: number): [number, number, number] {
  const a = Math.min(1, Math.max(0, amount));
  return [
    Math.round(rgb[0] + (GREY[0] - rgb[0]) * a),
    Math.round(rgb[1] + (GREY[1] - rgb[1]) * a),
    Math.round(rgb[2] + (GREY[2] - rgb[2]) * a),
  ];
}

// Smooth GPU-interpolated "pop" transitions — no manual animation loop needed.
const POP_TRANSITIONS = {
  getRadius: { duration: 220, easing: (t: number) => 1 - Math.pow(1 - t, 3) },
  getFillColor: 180,
  getLineColor: 180,
  getLineWidth: 180,
};
const EDGE_TRANSITIONS = { getColor: 180, getWidth: 180 };

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

  // Adjacency map for the focus/fade interaction — who's a direct neighbour of whom.
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
    const byId = new Map(placed.map((n) => [n.id, n]));

    const color = (n: GraphNode): [number, number, number] =>
      colorBy === "type" ? TYPE_RGB[n.type] ?? [120, 140, 170] : BAND_RGB[n.band] ?? BAND_RGB.CALM;

    // Obsidian-style node radius: small, gently scaled by connectivity.
    const baseRadius = (n: GraphNode) => 2.5 + Math.sqrt(n.degree) * 1.15;

    // Focus = whatever's hovered, falling back to the current selection. A node is
    // "in focus" if it IS the focus or a direct neighbour of it; everything else is
    // lower priority and recedes (greyed + faded), per the graph's real adjacency —
    // not just a static "importance" ranking.
    const focusId = hoverId ?? selectedId;
    const neighborsOfFocus = focusId ? adjacency.get(focusId) : undefined;
    const inFocusSet = (id: string) => !focusId || id === focusId || !!neighborsOfFocus?.has(id);

    // Baseline priority (used only when nothing is focused): well-connected or
    // elevated-risk nodes stay vivid; sparse/calm nodes sit slightly receded, so the
    // graph reads with a visual hierarchy even at rest.
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
        // Risk weight: the riskier of the two connected nodes brightens/thickens the
        // edge, on top of its relation-type base style — a FEEDS edge touching a
        // CRITICAL corridor reads as more urgent than one touching a calm one.
        const riskWeight = Math.max(s.score, t.score);
        // Emphasis: edges directly touching the focused node stay prominent;
        // everything else — including edges between two "in-focus" neighbours —
        // fades hard, so attention stays on the focused node's own connections.
        const emphasis = focusId ? (touchesFocus ? 1 : 0.06) : Math.min(nodeEmphasis(s), nodeEmphasis(t));
        return { s, t, touchesFocus, relation: e.relation, style, riskWeight, emphasis };
      })
      .filter(Boolean) as {
        s: GraphNode; t: GraphNode; touchesFocus: boolean; relation: string;
        style: { color: [number, number, number]; width: number }; riskWeight: number; emphasis: number;
      }[];

    // Styled by relationship type + risk weight (not a uniform line for every edge):
    // BYPASS_ROUTE green, EXPOSES red/thick (literal risk propagation), structural
    // FEEDS/SUPPLIES thin blue, CONFIGURED_FOR faintest. Focus further dims whatever
    // isn't directly touching the hovered/selected node.
    const edges = new LineLayer<(typeof edgeData)[number]>({
      id: "kg-edges",
      data: edgeData,
      getSourcePosition: (d) => [d.s.lon!, d.s.lat!],
      getTargetPosition: (d) => [d.t.lon!, d.t.lat!],
      getColor: (d) => {
        if (d.touchesFocus) return [56, 160, 210, 235];
        const base = focusId ? desaturate(d.style.color, 1 - d.emphasis) : d.style.color;
        const [r, g, b] = base;
        // Riskier edges get more opaque, not just wider — low-risk structural
        // edges stay in the background, high-risk ones pop.
        const alpha = (light ? 60 + d.riskWeight * 140 : 45 + d.riskWeight * 160) * d.emphasis;
        return [r, g, b, Math.round(Math.min(230, alpha))];
      },
      getWidth: (d) => (d.touchesFocus ? 2.6 : (d.style.width + d.riskWeight * 1.8) * Math.max(0.4, d.emphasis)),
      widthUnits: "pixels",
      transitions: EDGE_TRANSITIONS,
      updateTriggers: {
        getColor: [hoverId, selectedId, theme],
        getWidth: [hoverId, selectedId],
      },
    });

    // Selection ring — a plain outlined circle, not a soft glow blob. Reads as
    // a precise selection indicator rather than decorative bloom.
    const focusNode = placed.find((n) => n.id === selectedId);
    const selectionRing = new ScatterplotLayer<GraphNode>({
      id: "kg-selection-ring",
      data: focusNode ? [focusNode] : [],
      getPosition: (d) => [d.lon!, d.lat!],
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
      getPosition: (d) => [d.lon!, d.lat!],
      // The hovered node itself pops (bigger); its neighbours get a gentle bump;
      // everything else holds its normal size — the size change plus the 220ms
      // eased transition below IS the "pop" animation, no manual RAF loop needed.
      getRadius: (d) => {
        const r = baseRadius(d);
        if (d.id === hoverId) return r * 1.55;
        if (focusId && inFocusSet(d.id)) return r * 1.12;
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
      onHover: (info) => setHoverId((info.object as GraphNode)?.id ?? null),
      updateTriggers: {
        getRadius: [hoverId, selectedId],
        getFillColor: [colorBy, hoverId, selectedId],
        getLineColor: [colorBy, hoverId, selectedId],
        getLineWidth: [hoverId, selectedId],
      },
    });

    // Labels declutter automatically via CollisionFilterExtension — higher-degree
    // nodes win the space, exactly like Obsidian hides labels until they fit.
    // Faded/greyed-out nodes' labels fade with them so attention follows focus.
    const labels = new TextLayer<GraphNode>({
      id: "kg-labels",
      data: placed,
      getPosition: (d) => [d.lon!, d.lat!],
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
      updateTriggers: { getColor: [theme, hoverId, selectedId], getSize: [hoverId] },
      fontSettings: { sdf: true },
      // Collision filtering: priority = connectivity so hubs keep their labels
      // (props typed loosely — they belong to CollisionFilterExtension).
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
  }, [graph, onNodeClick, selectedId, colorBy, hoverId, theme, adjacency]);

  return (
    <DeckGL
      initialViewState={initialView}
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
  );
}
