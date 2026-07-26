/**
 * @module patterns/coverage-footprints
 * @description Builds the ground footprint polygon of each survey image so the
 * planner can draw a coverage overlay — the actual rectangles the camera captures
 * along the route, revealing overlap and gaps. Pure geometry: for each route point
 * it places a `width x height` metre rectangle (from the camera + altitude via
 * {@link computeFootprint}) centred on the point and rotated to the local flight
 * heading (the bearing along the leg). No store access, no side effects.
 * @license GPL-3.0-only
 */

import { offsetPoint, bearing } from "@/lib/drawing/geo-utils";
import { computeFootprint, type CameraProfile } from "@/lib/patterns/gsd-calculator";

/** Minimal point accepted by the footprint builder. */
export interface FootprintPoint {
  lat: number;
  lon: number;
}

/**
 * Ground footprint of one image as four `[lat, lon]` corners (clockwise from the
 * forward-right), centred on `(lat, lon)`, `widthM` across-track by `heightM`
 * along-track, rotated so `headingDeg` points along-track.
 */
export function buildFootprintPolygon(
  lat: number,
  lon: number,
  headingDeg: number,
  widthM: number,
  heightM: number,
): [number, number][] {
  const halfAlong = heightM / 2;
  const halfAcross = widthM / 2;
  // Corner = step along-track (heading) then across-track (heading + 90).
  const corner = (along: number, across: number): [number, number] => {
    const [la, lo] = offsetPoint(lat, lon, headingDeg, along);
    return offsetPoint(la, lo, headingDeg + 90, across);
  };
  return [
    corner(halfAlong, halfAcross),
    corner(halfAlong, -halfAcross),
    corner(-halfAlong, -halfAcross),
    corner(-halfAlong, halfAcross),
  ];
}

/**
 * Build a footprint polygon for every route point. Each point's heading is the
 * bearing to the next point (the last point reuses the bearing from its
 * predecessor), so footprints align with the flown legs. Returns an empty array
 * when there is nothing to draw (no points, no altitude, or a zero-size footprint).
 *
 * @param points   ordered route points (the survey capture waypoints)
 * @param camera   camera profile driving the footprint size
 * @param altitude flight altitude AGL in metres
 * @param maxCount safety cap on how many footprints to build (default 2000) so a
 *                 huge route cannot lock the map; the caller should surface when
 *                 the route exceeds it rather than silently drawing a subset.
 */
export function buildFootprintPolygons(
  points: readonly FootprintPoint[],
  camera: CameraProfile,
  altitude: number,
  maxCount = 2000,
): [number, number][][] {
  if (points.length === 0 || !Number.isFinite(altitude) || altitude <= 0) return [];
  const { width, height } = computeFootprint(altitude, camera);
  if (!(width > 0) || !(height > 0)) return [];

  const n = Math.min(points.length, maxCount);
  const polys: [number, number][][] = [];
  for (let i = 0; i < n; i++) {
    const p = points[i];
    let headingDeg: number;
    const next = points[i + 1];
    if (next) {
      headingDeg = bearing(p.lat, p.lon, next.lat, next.lon);
    } else {
      const prev = points[i - 1];
      headingDeg = prev ? bearing(prev.lat, prev.lon, p.lat, p.lon) : 0;
    }
    polys.push(buildFootprintPolygon(p.lat, p.lon, headingDeg, width, height));
  }
  return polys;
}
