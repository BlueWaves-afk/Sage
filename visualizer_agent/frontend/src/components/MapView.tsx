import { useMemo } from "react";
import DeckGL from "@deck.gl/react";
import { ScatterplotLayer, ArcLayer, TextLayer } from "@deck.gl/layers";
import { Map } from "react-map-gl/maplibre";
import type { RiskScore } from "../api/types";

// Free CARTO dark basemap — no API token required.
const MAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

const RISK_RGB: Record<string, [number, number, number]> = {
  CALM: [52, 211, 138],
  WATCH: [245, 200, 60],
  ELEVATED: [245, 166, 35],
  ACTION: [239, 120, 60],
  CRITICAL: [239, 75, 75],
};

// India's key discharge hub, for supply arcs.
const JAMNAGAR: [number, number] = [70.0, 22.5];

export interface MapViewProps {
  nodes: RiskScore[];
  arcs?: boolean;
  initialView?: { longitude: number; latitude: number; zoom: number };
  interactive?: boolean;
}

export default function MapView({
  nodes,
  arcs = true,
  initialView = { longitude: 55, latitude: 22, zoom: 3.4 },
  interactive = true,
}: MapViewProps) {
  const layers = useMemo(() => {
    const geoNodes = nodes.filter((n) => n.lat != null && n.lon != null);

    const scatter = new ScatterplotLayer<RiskScore>({
      id: "risk-nodes",
      data: geoNodes,
      getPosition: (d) => [d.lon!, d.lat!],
      getRadius: (d) => 30000 + d.score * 90000,
      radiusUnits: "meters",
      getFillColor: (d) => [...(RISK_RGB[d.band] ?? RISK_RGB.WATCH), 180],
      getLineColor: (d) => [...(RISK_RGB[d.band] ?? RISK_RGB.WATCH), 255],
      lineWidthMinPixels: 1.5,
      stroked: true,
      radiusMinPixels: 6,
      radiusMaxPixels: 40,
      pickable: true,
    });

    const labels = new TextLayer<RiskScore>({
      id: "risk-labels",
      data: geoNodes,
      getPosition: (d) => [d.lon!, d.lat!],
      getText: (d) => d.entity,
      getSize: 11,
      getColor: [200, 216, 232, 220],
      getPixelOffset: [0, -18],
      fontFamily: "Inter, sans-serif",
      getTextAnchor: "middle",
      background: true,
      getBackgroundColor: [10, 18, 30, 160],
      backgroundPadding: [4, 2],
    });

    const supplyArcs = arcs
      ? new ArcLayer<RiskScore>({
          id: "supply-arcs",
          data: geoNodes.filter((n) => n.entity.includes("Strait") || n.entity.includes("Bab")),
          getSourcePosition: (d) => [d.lon!, d.lat!],
          getTargetPosition: () => JAMNAGAR,
          getSourceColor: (d) => [...(RISK_RGB[d.band] ?? RISK_RGB.WATCH), 200],
          getTargetColor: [56, 198, 238, 200],
          getWidth: (d) => 1.5 + d.score * 3,
          getHeight: 0.4,
        })
      : null;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return [supplyArcs, scatter, labels].filter(Boolean) as any[];
  }, [nodes, arcs]);

  return (
    <DeckGL
      initialViewState={initialView}
      controller={interactive}
      layers={layers}
      getTooltip={({ object }) =>
        object
          ? {
              html: `<b>${(object as RiskScore).entity}</b><br/>${(object as RiskScore).band} — ${((object as RiskScore).score * 100).toFixed(0)}%`,
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
      <Map reuseMaps mapStyle={MAP_STYLE} attributionControl={false} />
    </DeckGL>
  );
}
