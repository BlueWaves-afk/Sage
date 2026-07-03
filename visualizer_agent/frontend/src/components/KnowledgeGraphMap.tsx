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
  const edgeIdle: [number, number, number, number] = light ? [70, 110, 150, 70] : [110, 140, 175, 55];
  const labelText: [number, number, number, number] = light ? [30, 45, 70, 255] : [210, 224, 240, 235];
  const labelOutline: [number, number, number, number] = light ? [255, 255, 255, 255] : [8, 14, 24, 255];

  const layers = useMemo(() => {
    const placed = graph.nodes.filter((n) => n.lat != null && n.lon != null);
    const byId = new Map(placed.map((n) => [n.id, n]));

    const color = (n: GraphNode): [number, number, number] =>
      colorBy === "type" ? TYPE_RGB[n.type] ?? [120, 140, 170] : BAND_RGB[n.band] ?? BAND_RGB.CALM;

    // Obsidian-style node radius: small, gently scaled by connectivity.
    const radius = (n: GraphNode) => 2.5 + Math.sqrt(n.degree) * 1.15;

    const edgeData = graph.edges
      .map((e) => {
        const s = byId.get(e.source);
        const t = byId.get(e.target);
        if (!s || !t) return null;
        const active = hoverId === s.id || hoverId === t.id || selectedId === s.id || selectedId === t.id;
        return { s, t, active };
      })
      .filter(Boolean) as { s: GraphNode; t: GraphNode; active: boolean }[];

    // Thin, low-opacity edges; the ones touching the hovered/selected node brighten.
    const edges = new LineLayer<(typeof edgeData)[number]>({
      id: "kg-edges",
      data: edgeData,
      getSourcePosition: (d) => [d.s.lon!, d.s.lat!],
      getTargetPosition: (d) => [d.t.lon!, d.t.lat!],
      getColor: (d) => (d.active ? [56, 160, 210, 220] : edgeIdle),
      getWidth: (d) => (d.active ? 1.6 : 0.7),
      widthUnits: "pixels",
      updateTriggers: { getColor: [hoverId, selectedId, theme], getWidth: [hoverId, selectedId] },
    });

    // Soft halo only under the hovered/selected node.
    const focusNode = placed.find((n) => n.id === (hoverId ?? selectedId));
    const halo = new ScatterplotLayer<GraphNode>({
      id: "kg-halo",
      data: focusNode ? [focusNode] : [],
      getPosition: (d) => [d.lon!, d.lat!],
      getRadius: (d) => radius(d) + 6,
      radiusUnits: "pixels",
      getFillColor: [56, 198, 238, 45],
      stroked: false,
      pickable: false,
    });

    const nodes = new ScatterplotLayer<GraphNode>({
      id: "kg-nodes",
      data: placed,
      getPosition: (d) => [d.lon!, d.lat!],
      getRadius: radius,
      radiusUnits: "pixels",
      radiusMinPixels: 2.5,
      radiusMaxPixels: 12,
      getFillColor: (d) => [...color(d), 230],
      getLineColor: (d) =>
        d.id === selectedId ? [235, 245, 255, 255] : [...color(d).map((c) => Math.min(255, c + 45)) as [number, number, number], 255],
      lineWidthUnits: "pixels",
      getLineWidth: (d) => (d.id === selectedId ? 2 : 0.8),
      stroked: true,
      pickable: true,
      antialiasing: true,
      onClick: (info) => info.object && onNodeClick?.(info.object as GraphNode),
      onHover: (info) => setHoverId((info.object as GraphNode)?.id ?? null),
      updateTriggers: {
        getFillColor: [colorBy],
        getLineColor: [colorBy, selectedId],
        getLineWidth: [selectedId],
      },
    });

    // Labels declutter automatically via CollisionFilterExtension — higher-degree
    // nodes win the space, exactly like Obsidian hides labels until they fit.
    const labels = new TextLayer<GraphNode>({
      id: "kg-labels",
      data: placed,
      getPosition: (d) => [d.lon!, d.lat!],
      getText: (d) => d.name,
      getSize: 11,
      getColor: labelText,
      getPixelOffset: (d) => [0, -(radius(d) + 8)],
      getTextAnchor: "middle",
      getAlignmentBaseline: "bottom",
      fontFamily: "Inter, sans-serif",
      fontWeight: 600,
      outlineWidth: 3,
      outlineColor: labelOutline,
      updateTriggers: { getColor: [theme] },
      fontSettings: { sdf: true },
      // Collision filtering: priority = connectivity so hubs keep their labels
      // (props typed loosely — they belong to CollisionFilterExtension).
      extensions: [new CollisionFilterExtension()],
      ...({
        collisionEnabled: true,
        getCollisionPriority: (d: GraphNode) => d.degree + (d.id === selectedId ? 1000 : 0),
        collisionTestProps: { sizeScale: 2.4 },
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
      } as any),
    });

    return [edges, halo, nodes, labels];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph, onNodeClick, selectedId, colorBy, hoverId, theme]);

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
      <BaseMap reuseMaps mapStyle={basemapFor(theme)} attributionControl={false} />
    </DeckGL>
  );
}
