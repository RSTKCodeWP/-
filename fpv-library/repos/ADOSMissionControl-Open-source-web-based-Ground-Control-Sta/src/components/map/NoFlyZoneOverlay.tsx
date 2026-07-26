/**
 * @module NoFlyZoneOverlay
 * @description Renders static no-fly zone polygons on the Leaflet map.
 * Toggle via settings store. Red semi-transparent polygons for airports,
 * orange for military, yellow for other restricted areas.
 * @license GPL-3.0-only
 */

"use client";

import { Polygon, Tooltip } from "react-leaflet";
import { NO_FLY_ZONES, type NoFlyZone } from "@/lib/no-fly-zones";

const TYPE_COLORS: Record<NoFlyZone["type"], { stroke: string; fill: string }> = {
  airport: { stroke: "#ef4444", fill: "#ef4444" },
  military: { stroke: "#f97316", fill: "#f97316" },
  restricted: { stroke: "#eab308", fill: "#eab308" },
};

const TYPE_LABELS: Record<NoFlyZone["type"], string> = {
  airport: "Airport NFZ",
  military: "Military NFZ",
  restricted: "Restricted",
};

interface NoFlyZoneOverlayProps {
  visible?: boolean;
}

export function NoFlyZoneOverlay({ visible = true }: NoFlyZoneOverlayProps) {
  if (!visible) return null;

  return (
    <>
      {NO_FLY_ZONES.map((zone) => {
        const colors = TYPE_COLORS[zone.type];
        return (
          <Polygon
            key={zone.name}
            positions={zone.polygon}
            pathOptions={{
              color: colors.stroke,
              weight: 1.5,
              dashArray: "6 3",
              fillColor: colors.fill,
              fillOpacity: 0.1,
            }}
          >
            <Tooltip direction="center" sticky>
              <span
                style={{
                  fontFamily: "JetBrains Mono, monospace",
                  fontSize: 10,
                  color: colors.stroke,
                }}
              >
                {TYPE_LABELS[zone.type]}: {zone.name}
              </span>
            </Tooltip>
          </Polygon>
        );
      })}
    </>
  );
}
