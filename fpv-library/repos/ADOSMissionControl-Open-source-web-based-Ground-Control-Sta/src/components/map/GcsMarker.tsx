/**
 * @module GcsMarker
 * @description Leaflet GCS position marker — green crosshair with pulsing accuracy ring.
 * Reads from gcs-location-store and settings-store. Returns null when disabled or no fix.
 * @license GPL-3.0-only
 */

"use client";

import { useMemo } from "react";
import { Circle, Marker, Tooltip } from "react-leaflet";
import L from "leaflet";
import { useGcsLocationStore } from "@/stores/gcs-location-store";
import { useSettingsStore } from "@/stores/settings-store";

const GCS_COLOR = "#22c55e";

function makeGcsIcon(): L.DivIcon {
  return L.divIcon({
    className: "",
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    html: `<div style="width:28px;height:28px;position:relative">
      <div style="position:absolute;inset:2px;border-radius:50%;border:1.5px solid ${GCS_COLOR};animation:gcs-pulse 2s ease-in-out infinite"></div>
      <svg width="28" height="28" viewBox="0 0 28 28" xmlns="http://www.w3.org/2000/svg" style="position:absolute;inset:0">
        <line x1="14" y1="4" x2="14" y2="11" stroke="${GCS_COLOR}" stroke-width="1.5"/>
        <line x1="14" y1="17" x2="14" y2="24" stroke="${GCS_COLOR}" stroke-width="1.5"/>
        <line x1="4" y1="14" x2="11" y2="14" stroke="${GCS_COLOR}" stroke-width="1.5"/>
        <line x1="17" y1="14" x2="24" y2="14" stroke="${GCS_COLOR}" stroke-width="1.5"/>
        <circle cx="14" cy="14" r="3" fill="${GCS_COLOR}" fill-opacity="0.8"/>
      </svg>
    </div>`,
  });
}

const gcsIcon = makeGcsIcon();

export function GcsMarker() {
  const locationEnabled = useSettingsStore((s) => s.locationEnabled);
  const position = useGcsLocationStore((s) => s.position);

  const tooltipText = useMemo(() => {
    if (!position) return "";
    return `GCS | ${position.lat.toFixed(6)}, ${position.lon.toFixed(6)}`;
  }, [position]);

  if (!locationEnabled || !position) return null;

  return (
    <>
      {/* Accuracy circle */}
      <Circle
        center={[position.lat, position.lon]}
        radius={position.accuracy}
        pathOptions={{
          color: GCS_COLOR,
          weight: 1,
          dashArray: "4 4",
          fillColor: GCS_COLOR,
          fillOpacity: 0.06,
        }}
      />

      {/* Crosshair marker */}
      <Marker
        position={[position.lat, position.lon]}
        icon={gcsIcon}
        zIndexOffset={1000}
      >
        <Tooltip direction="top" offset={[0, -14]}>
          <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10 }}>
            {tooltipText}
          </span>
        </Tooltip>
      </Marker>
    </>
  );
}
