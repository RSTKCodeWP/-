/**
 * @module mission-transforms
 * @description Pure functions for transforming entire missions: move, rotate, scale.
 * All functions return new waypoint arrays — no mutation.
 * @license GPL-3.0-only
 */

import type { Waypoint } from "@/lib/types";

const DEG_TO_RAD = Math.PI / 180;
const RAD_TO_DEG = 180 / Math.PI;
const EARTH_RADIUS = 6371000; // meters

/**
 * Compute the geographic centroid of a set of waypoints.
 */
function centroid(waypoints: Waypoint[]): [number, number] {
  if (waypoints.length === 0) return [0, 0];
  let sumLat = 0;
  let sumLon = 0;
  for (const wp of waypoints) {
    sumLat += wp.lat;
    sumLon += wp.lon;
  }
  return [sumLat / waypoints.length, sumLon / waypoints.length];
}

/**
 * Move an entire mission by a lat/lon delta.
 * @param waypoints - Source waypoints
 * @param deltaLat - Latitude offset in degrees
 * @param deltaLon - Longitude offset in degrees
 * @returns New waypoint array with shifted positions
 */
export function moveMission(
  waypoints: Waypoint[],
  deltaLat: number,
  deltaLon: number,
): Waypoint[] {
  return waypoints.map((wp) => ({
    ...wp,
    lat: wp.lat + deltaLat,
    lon: wp.lon + deltaLon,
  }));
}

/**
 * Move an entire mission by a bearing and distance.
 * @param waypoints - Source waypoints
 * @param bearingDeg - Bearing in degrees from north (0-360)
 * @param distanceMeters - Distance to move in meters
 * @returns New waypoint array with shifted positions
 */
export function moveMissionByBearing(
  waypoints: Waypoint[],
  bearingDeg: number,
  distanceMeters: number,
): Waypoint[] {
  if (waypoints.length === 0) return [];
  // Calculate delta from first waypoint
  const ref = waypoints[0];
  const dest = offsetPoint(ref.lat, ref.lon, bearingDeg, distanceMeters);
  const deltaLat = dest[0] - ref.lat;
  const deltaLon = dest[1] - ref.lon;
  return moveMission(waypoints, deltaLat, deltaLon);
}

/**
 * Rotate an entire mission around its centroid.
 * @param waypoints - Source waypoints
 * @param angleDeg - Rotation angle in degrees (positive = clockwise)
 * @returns New waypoint array with rotated positions
 */
export function rotateMission(
  waypoints: Waypoint[],
  angleDeg: number,
): Waypoint[] {
  if (waypoints.length === 0) return [];
  const [cLat, cLon] = centroid(waypoints);
  return waypoints.map((wp) => {
    const [newLat, newLon] = rotatePoint(wp.lat, wp.lon, cLat, cLon, angleDeg);
    return { ...wp, lat: newLat, lon: newLon };
  });
}

/**
 * Rotate an entire mission around a specified center point.
 * @param waypoints - Source waypoints
 * @param angleDeg - Rotation angle in degrees (positive = clockwise)
 * @param centerLat - Center latitude
 * @param centerLon - Center longitude
 * @returns New waypoint array with rotated positions
 */
export function rotateMissionAroundPoint(
  waypoints: Waypoint[],
  angleDeg: number,
  centerLat: number,
  centerLon: number,
): Waypoint[] {
  return waypoints.map((wp) => {
    const [newLat, newLon] = rotatePoint(wp.lat, wp.lon, centerLat, centerLon, angleDeg);
    return { ...wp, lat: newLat, lon: newLon };
  });
}

/**
 * Scale an entire mission from its centroid.
 * @param waypoints - Source waypoints
 * @param factor - Scale factor (1.0 = no change, 2.0 = double size, 0.5 = half size)
 * @returns New waypoint array with scaled positions
 */
export function scaleMission(
  waypoints: Waypoint[],
  factor: number,
): Waypoint[] {
  if (waypoints.length === 0 || factor === 1) return [...waypoints];
  const [cLat, cLon] = centroid(waypoints);
  return waypoints.map((wp) => {
    const dLat = (wp.lat - cLat) * factor;
    const dLon = (wp.lon - cLon) * factor;
    return {
      ...wp,
      lat: cLat + dLat,
      lon: cLon + dLon,
    };
  });
}

/**
 * Scale an entire mission from a specified center point.
 */
export function scaleMissionFromPoint(
  waypoints: Waypoint[],
  factor: number,
  centerLat: number,
  centerLon: number,
): Waypoint[] {
  if (waypoints.length === 0 || factor === 1) return [...waypoints];
  return waypoints.map((wp) => {
    const dLat = (wp.lat - centerLat) * factor;
    const dLon = (wp.lon - centerLon) * factor;
    return {
      ...wp,
      lat: centerLat + dLat,
      lon: centerLon + dLon,
    };
  });
}

/**
 * Mirror/flip a mission along an axis through its centroid.
 * @param waypoints - Source waypoints
 * @param axis - "lat" flips east-west, "lon" flips north-south
 */
export function mirrorMission(
  waypoints: Waypoint[],
  axis: "lat" | "lon",
): Waypoint[] {
  if (waypoints.length === 0) return [];
  const [cLat, cLon] = centroid(waypoints);
  return waypoints.map((wp) => ({
    ...wp,
    lat: axis === "lon" ? 2 * cLat - wp.lat : wp.lat,
    lon: axis === "lat" ? 2 * cLon - wp.lon : wp.lon,
  }));
}

// ── Internal helpers ──────────────────────────────────────────

/**
 * Rotate a point around a center by angleDeg.
 * Uses equirectangular approximation (good enough for mission-scale distances).
 */
function rotatePoint(
  lat: number,
  lon: number,
  centerLat: number,
  centerLon: number,
  angleDeg: number,
): [number, number] {
  const angleRad = angleDeg * DEG_TO_RAD;
  const cosA = Math.cos(angleRad);
  const sinA = Math.sin(angleRad);
  // Apply longitude correction for latitude
  const lonScale = Math.cos(centerLat * DEG_TO_RAD);
  const dx = (lon - centerLon) * lonScale;
  const dy = lat - centerLat;
  const rx = dx * cosA - dy * sinA;
  const ry = dx * sinA + dy * cosA;
  return [
    centerLat + ry,
    centerLon + rx / lonScale,
  ];
}

/**
 * Move a point by bearing and distance (Vincenty direct formula simplified).
 */
function offsetPoint(
  lat: number,
  lon: number,
  bearingDeg: number,
  distanceMeters: number,
): [number, number] {
  const latRad = lat * DEG_TO_RAD;
  const bearingRad = bearingDeg * DEG_TO_RAD;
  const angDist = distanceMeters / EARTH_RADIUS;
  const newLatRad = Math.asin(
    Math.sin(latRad) * Math.cos(angDist) +
    Math.cos(latRad) * Math.sin(angDist) * Math.cos(bearingRad)
  );
  const newLonRad = lon * DEG_TO_RAD + Math.atan2(
    Math.sin(bearingRad) * Math.sin(angDist) * Math.cos(latRad),
    Math.cos(angDist) - Math.sin(latRad) * Math.sin(newLatRad)
  );
  return [newLatRad * RAD_TO_DEG, newLonRad * RAD_TO_DEG];
}
