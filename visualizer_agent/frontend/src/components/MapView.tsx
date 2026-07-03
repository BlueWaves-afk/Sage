import { useMemo } from "react";
import DeckGL from "@deck.gl/react";
import { ScatterplotLayer, ArcLayer, TextLayer } from "@deck.gl/layers";
import { Map } from "react-map-gl/maplibre";
import type { RiskScore } from "../api/types";
import { useTheme, basemapFor } from "../theme";

const RISK_RGB: Record<string, [number, number, number]> = {
  CALM: [63, 184, 127],
  WATCH: [217, 180, 60],
  ELEVATED: [217, 154, 43],
  ACTION: [217, 122, 99],
  CRITICAL: [216, 82, 79],
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
  const { theme } = useTheme();
  const layers = useMemo(() => {
    const geoNodes = nodes.filter((n) => n.lat != null && n.lon != null);

    const scatter = new ScatterplotLayer<RiskScore>({
      id: "risk-nodes",
      data: geoNodes,
      getPosition: (d) => [d.lon!, d.lat!],
      getRadius: (d) => 20000 + d.score * 60000,
      radiusUnits: "meters",
      getFillColor: (d) => [...(RISK_RGB[d.band] ?? RISK_RGB.WATCH), 220],
      getLineColor: (d) => [...(RISK_RGB[d.band] ?? RISK_RGB.WATCH), 255],
      lineWidthMinPixels: 1,
      stroked: true,
      radiusMinPixels: 4,
      radiusMaxPixels: 26,
      pickable: true,
    });

    const labels = new TextLayer<RiskScore>({
      id: "risk-labels",
      data: geoNodes,
      getPosition: (d) => [d.lon!, d.lat!],
      getText: (d) => d.entity,
      getSize: 10,
      getColor: [184, 188, 198, 235],
      getPixelOffset: [0, -16],
      fontFamily: "Inter, sans-serif",
      fontWeight: 600,
      getTextAnchor: "middle",
      background: true,
      getBackgroundColor: [16, 16, 20, 210],
      backgroundPadding: [4, 2],
    });

    // Thin, flat, low-opacity supply routes — functional reference lines, not
    // decorative glowing arcs. No curvature (height 0) to avoid overlapping bloom.
    const supplyArcs = arcs
      ? new ArcLayer<RiskScore>({
          id: "supply-arcs",
          data: geoNodes.filter((n) => n.entity.includes("Strait") || n.entity.includes("Bab")),
          getSourcePosition: (d) => [d.lon!, d.lat!],
          getTargetPosition: () => JAMNAGAR,
          getSourceColor: [110, 140, 175, 90],
          getTargetColor: [110, 140, 175, 90],
          getWidth: 1,
          getHeight: 0,
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
      <Map reuseMaps mapStyle={basemapFor(theme)} attributionControl={false} />
    </DeckGL>
  );
}
