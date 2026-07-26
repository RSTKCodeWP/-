/**
 * @module CoverageOverlay
 * @description Draws the per-image camera footprint of each mission waypoint on the
 * planner map as translucent rectangles, so the operator can see the actual ground
 * a survey captures — where images overlap and where gaps open up. Display-only.
 * Renders nothing unless the coverage toggle is on, a camera is selected in the
 * survey config, and the plan has waypoints. The footprints are computed from the
 * real camera geometry + the survey altitude — never a fabricated coverage claim.
 * Must render inside a react-leaflet MapContainer.
 * @license GPL-3.0-only
 */
"use client";

import { useMemo } from "react";
import { Polygon } from "react-leaflet";
import { useMissionStore } from "@/stores/mission-store";
import { usePatternStore } from "@/stores/pattern-store";
import { CAMERA_PROFILES } from "@/lib/patterns/gsd-calculator";
import { buildFootprintPolygons } from "@/lib/patterns/coverage-footprints";

/** Cyan translucent fill for the footprint rectangles (a map-layer css colour, not app-UI). */
const FOOTPRINT_COLOR = "#22d3ee";

export function CoverageOverlay() {
  const waypoints = useMissionStore((s) => s.waypoints);
  const showCoverageOverlay = usePatternStore((s) => s.showCoverageOverlay);
  const surveyConfig = usePatternStore((s) => s.surveyConfig);

  const cameraName = (surveyConfig as { _cameraName?: string })._cameraName;
  const altitude = surveyConfig.altitude ?? 50;

  const footprints = useMemo(() => {
    if (!showCoverageOverlay) return [];
    const camera = CAMERA_PROFILES.find((c) => c.name === cameraName);
    if (!camera || waypoints.length === 0) return [];
    return buildFootprintPolygons(
      waypoints.map((w) => ({ lat: w.lat, lon: w.lon })),
      camera,
      altitude,
    );
  }, [showCoverageOverlay, cameraName, altitude, waypoints]);

  if (footprints.length === 0) return null;

  return (
    <>
      {footprints.map((positions, i) => (
        <Polygon
          key={i}
          positions={positions}
          pathOptions={{
            color: FOOTPRINT_COLOR,
            weight: 0.5,
            opacity: 0.6,
            fillColor: FOOTPRINT_COLOR,
            fillOpacity: 0.12,
            interactive: false,
          }}
        />
      ))}
    </>
  );
}
