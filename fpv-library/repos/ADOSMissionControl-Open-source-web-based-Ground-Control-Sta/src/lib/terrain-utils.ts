/**
 * @module terrain-utils
 * @description Utilities for resolving AGL (Above Ground Level) waypoint altitudes
 * to absolute altitudes using CesiumJS terrain sampling. Adds intermediate
 * sub-sample points between waypoints for smooth terrain-following visualization.
 * @license GPL-3.0-only
 */

import {
  Cartographic,
  Cartesian3,
  sampleTerrainMostDetailed,
  type TerrainProvider,
} from "cesium";
import type { Waypoint } from "@/lib/types";
import { haversineDistance } from "@/lib/telemetry-utils";
import { loadGeoidGrid, mslToEllipsoidal } from "@/lib/terrain/geoid";

/** Spacing between intermediate sub-sample points (meters). */
const SUBSAMPLE_INTERVAL = 100;

/** Result of resolving AGL waypoints to absolute positions. */
export interface ResolvedPath {
  /** All positions along the path, including intermediate sub-samples. */
  positions: Cartesian3[];
  /** Indices into `positions` that correspond to original waypoints. */
  waypointIndices: number[];
  /** Terrain height (meters above ellipsoid) at each original waypoint. */
  terrainHeights: number[];
}

/**
 * Resolve waypoint altitudes to absolute (ellipsoidal) positions for Cesium.
 * Adds intermediate sub-sample points every ~100m between waypoints for smooth
 * terrain-following visualization.
 *
 * Frame-aware: an `absolute`-frame waypoint carries an MSL/AMSL altitude, so it
 * is placed at `mslToEllipsoidal(alt)` (geoid-corrected height above the
 * ellipsoid) and terrain is NOT added — it sits at the same absolute height
 * regardless of the ground below. `relative` / `terrain` / undefined frames stay
 * `terrainHeight + AGL`. A segment's sub-samples inherit the frame of its start
 * waypoint (an absolute leg holds constant MSL; a relative leg follows terrain).
 * The geoid grid is warmed here so the conversion is correct on first resolve
 * (absent grid -> honest MSL-as-ellipsoidal passthrough).
 */
export async function resolveAGLToAbsolute(
  waypoints: Waypoint[],
  terrainProvider: TerrainProvider
): Promise<ResolvedPath> {
  if (waypoints.length === 0) {
    return { positions: [], waypointIndices: [], terrainHeights: [] };
  }

  // Warm the bundled geoid grid so absolute-frame MSL->ellipsoidal is correct on
  // the first resolve. Cheap + cached + never throws; no-ops if the asset is
  // absent (then absolute frames pass through MSL unchanged).
  await loadGeoidGrid();

  // Build cartographic positions: original waypoints + intermediate points.
  // Track, per point, its geographic degrees, its altitude value, and whether
  // that altitude is an absolute (MSL) height rather than AGL.
  const cartographics: Cartographic[] = [];
  const lonLatDeg: Array<{ lat: number; lon: number }> = [];
  const altValues: number[] = [];
  const isAbsolute: boolean[] = [];
  const waypointIndices: number[] = [];

  for (let i = 0; i < waypoints.length; i++) {
    const wp = waypoints[i];
    const absolute = wp.frame === "absolute";

    // Record this index as an original waypoint
    waypointIndices.push(cartographics.length);
    cartographics.push(Cartographic.fromDegrees(wp.lon, wp.lat));
    lonLatDeg.push({ lat: wp.lat, lon: wp.lon });
    altValues.push(wp.alt);
    isAbsolute.push(absolute);

    // Add intermediate points to next waypoint for smooth terrain following
    if (i < waypoints.length - 1) {
      const next = waypoints[i + 1];
      const dist = haversineDistance(wp.lat, wp.lon, next.lat, next.lon);
      const numSub = Math.max(0, Math.floor(dist / SUBSAMPLE_INTERVAL) - 1);

      for (let s = 1; s <= numSub; s++) {
        const t = s / (numSub + 1);
        const lat = wp.lat + (next.lat - wp.lat) * t;
        const lon = wp.lon + (next.lon - wp.lon) * t;
        const alt = wp.alt + (next.alt - wp.alt) * t;

        cartographics.push(Cartographic.fromDegrees(lon, lat));
        lonLatDeg.push({ lat, lon });
        altValues.push(alt);
        isAbsolute.push(absolute); // sub-samples inherit the segment's start frame
      }
    }
  }

  // Sample terrain heights at all points
  const sampled = await sampleTerrainMostDetailed(terrainProvider, cartographics);

  // Build absolute Cartesian3 positions. Absolute-frame points are placed at the
  // geoid-corrected ellipsoidal height (no terrain add); AGL points at terrain +
  // AGL.
  const positions = sampled.map((carto, i) => {
    const { lat, lon } = lonLatDeg[i];
    const absoluteAlt = isAbsolute[i]
      ? mslToEllipsoidal(altValues[i], lat, lon)
      : (carto.height || 0) + altValues[i];
    return Cartesian3.fromRadians(carto.longitude, carto.latitude, absoluteAlt);
  });

  // Extract terrain heights at original waypoint positions only
  const terrainHeights = waypointIndices.map((idx) => sampled[idx].height || 0);

  return { positions, waypointIndices, terrainHeights };
}
