/**
 * @module patterns/orbit-generator
 * @description Generates circular orbit flight patterns around a point of interest.
 *
 * Algorithm:
 * 1. Compute circumference, determine number of waypoints (min 8, max 360, ~5m spacing)
 * 2. Place points equally spaced on the circle starting from startAngle
 * 3. Reverse order if direction is counter-clockwise
 * 4. Repeat for the requested number of turns
 * 5. Insert ROI waypoint at the circle center so the camera always faces inward
 *
 * @license GPL-3.0-only
 */

import type { OrbitConfig, PatternResult, PatternWaypoint } from "./types";
import { haversineDistance, offsetPoint } from "@/lib/drawing/geo-utils";

export function generateOrbit(config: OrbitConfig): PatternResult {
  const { center, radius, direction, turns, startAngle, altitude, speed } = config;

  if (radius <= 0 || turns <= 0) {
    return { waypoints: [], stats: { totalDistance: 0, estimatedTime: 0, photoCount: 0, coveredArea: 0, transectCount: 0 } };
  }

  const circumference = 2 * Math.PI * radius;
  const spacing = 5; // meters between waypoints along the circle
  let pointsPerTurn = Math.round(circumference / spacing);
  pointsPerTurn = Math.max(8, Math.min(360, pointsPerTurn));

  const angleStep = 360 / pointsPerTurn;

  // Generate one orbit of points
  const singleOrbit: [number, number][] = [];
  for (let i = 0; i < pointsPerTurn; i++) {
    let angle = startAngle + i * angleStep;
    if (direction === "ccw") {
      angle = startAngle - i * angleStep;
    }
    // Normalize to 0-360
    angle = ((angle % 360) + 360) % 360;
    const pt = offsetPoint(center[0], center[1], angle, radius);
    singleOrbit.push(pt);
  }

  // Build waypoints: ROI first, then orbit points repeated for turns
  const waypoints: PatternWaypoint[] = [];

  // ROI at center so the drone always points toward the POI
  waypoints.push({
    lat: center[0],
    lon: center[1],
    alt: altitude,
    speed,
    command: "ROI",
  });

  for (let t = 0; t < turns; t++) {
    for (const pt of singleOrbit) {
      waypoints.push({
        lat: pt[0],
        lon: pt[1],
        alt: altitude,
        speed,
        command: "WAYPOINT",
      });
    }
  }

  // Stats
  let totalDistance = 0;
  const wpOnly = waypoints.filter((w) => w.command === "WAYPOINT");
  for (let i = 1; i < wpOnly.length; i++) {
    totalDistance += haversineDistance(
      wpOnly[i - 1].lat, wpOnly[i - 1].lon,
      wpOnly[i].lat, wpOnly[i].lon
    );
  }
  // Add closing segment (last point back to first for the loop)
  if (wpOnly.length > 1) {
    totalDistance += haversineDistance(
      wpOnly[wpOnly.length - 1].lat, wpOnly[wpOnly.length - 1].lon,
      wpOnly[0].lat, wpOnly[0].lon
    );
  }

  const coveredArea = Math.PI * radius * radius;
  const estimatedTime = speed > 0 ? totalDistance / speed : 0;

  return {
    waypoints,
    stats: {
      totalDistance,
      estimatedTime,
      photoCount: 0,
      coveredArea,
      transectCount: 0,
    },
  };
}
