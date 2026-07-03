import { useMemo } from "react";
import DeckGL from "@deck.gl/react";
import { ScatterplotLayer, LineLayer, TextLayer } from "@deck.gl/layers";
import { Map as BaseMap } from "react-map-gl/maplibre";
import type { GraphData, GraphNode } from "../api/types";

const MAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

// Risk-band → colour (traffic-light gradient, matching the Obsidian graph config).
const BAND_RGB: Record<string, [number, number, number]> = {
  CALM: [42, 157, 143],
  WATCH: [233, 196, 106],
  ELEVATED: [244, 162, 97],
  ACTION: [231, 111, 81],
  CRITICAL: [230, 57, 70],
};

// Entity type → accent (used for the thin ring around each node).
const TYPE_RGB: Record<string, [number, number, number]> = {
  Corridor: [230, 57, 70],
  Supplier: [69, 123, 157],
  Refinery: [42, 157, 143],
  CrudeGrade: [157, 78, 221],
  Port: [0, 180, 216],
  SPRCavern: [233, 196, 106],
  Authority: [141, 153, 174],
  GeoEvent: [244, 162, 97],
};

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
  const layers = useMemo(() => {
    const placed = graph.nodes.filter((n) => n.lat != null && n.lon != null);
    const byId = new Map(placed.map((n) => [n.id, n]));

    // Edges as great-circle-ish straight lines between node positions.
    const edgeData = graph.edges
      .map((e) => {
        const s = byId.get(e.source);
        const t = byId.get(e.target);
        if (!s || !t) return null;
        return { s, t, relation: e.relation };
      })
      .filter(Boolean) as { s: GraphNode; t: GraphNode; relation: string }[];

    const edges = new LineLayer<(typeof edgeData)[number]>({
      id: "kg-edges",
      data: edgeData,
      getSourcePosition: (d) => [d.s.lon!, d.s.lat!],
      getTargetPosition: (d) => [d.t.lon!, d.t.lat!],
      getColor: [90, 130, 170, 90],
      getWidth: 1,
      widthUnits: "pixels",
    });

    const color = (n: GraphNode): [number, number, number] =>
      colorBy === "type" ? TYPE_RGB[n.type] ?? [120, 140, 170] : BAND_RGB[n.band] ?? BAND_RGB.CALM;

    // Halo for the selected node.
    const halo = new ScatterplotLayer<GraphNode>({
      id: "kg-halo",
      data: placed.filter((n) => n.id === selectedId),
      getPosition: (d) => [d.lon!, d.lat!],
      getRadius: (d) => 18 + d.degree * 3,
      radiusUnits: "pixels",
      getFillColor: [56, 198, 238, 60],
      stroked: false,
      pickable: false,
    });

    const nodes = new ScatterplotLayer<GraphNode>({
      id: "kg-nodes",
      data: placed,
      getPosition: (d) => [d.lon!, d.lat!],
      getRadius: (d) => 5 + Math.sqrt(d.degree) * 3, // prominence via link count
      radiusUnits: "pixels",
      radiusMinPixels: 4,
      radiusMaxPixels: 26,
      getFillColor: (d) => [...color(d), 235],
      getLineColor: (d) => [...color(d), 255],
      lineWidthMinPixels: 1.5,
      stroked: true,
      pickable: true,
      onClick: (info) => info.object && onNodeClick?.(info.object as GraphNode),
      updateTriggers: { getFillColor: [colorBy], getLineColor: [colorBy] },
    });

    // Labels only for well-connected hubs to avoid clutter.
    const labels = new TextLayer<GraphNode>({
      id: "kg-labels",
      data: placed.filter((n) => n.degree >= 3 || n.id === selectedId),
      getPosition: (d) => [d.lon!, d.lat!],
      getText: (d) => d.name,
      getSize: 11,
      getColor: [206, 220, 236, 230],
      getPixelOffset: [0, -14],
      getTextAnchor: "middle",
      fontFamily: "Inter, sans-serif",
      fontWeight: 600,
      background: true,
      getBackgroundColor: [10, 18, 30, 190],
      backgroundPadding: [5, 2],
    });

    return [edges, halo, nodes, labels];
  }, [graph, onNodeClick, selectedId, colorBy]);

  return (
    <DeckGL
      initialViewState={initialView}
      controller={true}
      layers={layers}
      getCursor={({ isHovering }) => (isHovering ? "pointer" : "grab")}
      getTooltip={({ object }) =>
        object && (object as GraphNode).name
          ? {
              html: `<b>${(object as GraphNode).name}</b><br/>${(object as GraphNode).type} · ${
                (object as GraphNode).band
              } ${((object as GraphNode).score * 100).toFixed(0)}% · ${(object as GraphNode).degree} links`,
              style: {
                background: "#0f1a2b",
                color: "#eef3fa",
                fontSize: "12px",
                padding: "6px 10px",
                borderRadius: "6px",
                border: "1px solid #21344f",
              },
            }
          : null
      }
      style={{ position: "absolute", top: "0", left: "0", right: "0", bottom: "0" }}
    >
      <BaseMap reuseMaps mapStyle={MAP_STYLE} attributionControl={false} />
    </DeckGL>
  );
}
