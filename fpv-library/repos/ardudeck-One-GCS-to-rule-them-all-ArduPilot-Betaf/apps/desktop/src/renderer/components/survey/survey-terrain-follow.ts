/**
 * Continuous DEM terrain-follow for survey waypoints.
 *
 * Samples ground elevation at every waypoint from the Open-Meteo DEM (reusing
 * the cached/batched {@link getElevations}) and bakes an absolute (MSL) altitude
 * of `ground + AGL` into each one. The result is consumed as `SurveyResult.altitudes`
 * with the mission emitted in the GLOBAL (ASL) frame, so the vehicle holds a
 * constant height above ground without needing an onboard terrain database.
 *
 * The per-waypoint AGL is taken from any existing `result.altitudes` entry
 * (e.g. crosshatch second-pass offset) and otherwise falls back to the flat
 * `config.altitude`, so two-height patterns keep their relative spacing on top
 * of the terrain.
 */
import { getElevations } from '../../utils/elevation-api';
import type { SurveyResult, SurveyConfig } from './survey-types';

export interface TerrainFollowOutcome {
  /** Per-waypoint absolute (MSL) altitudes aligned 1:1 with result.waypoints. */
  altitudes: number[];
  /** Number of waypoints whose ground elevation could be resolved from the DEM. */
  resolved: number;
  /** Ground elevation spread across the surveyed area (m), for the UI readout. */
  terrainRange: { min: number; max: number } | null;
}

/**
 * Compute MSL altitudes that hold a constant AGL over the terrain for every
 * waypoint. Returns null when there are no waypoints or the DEM resolved nothing
 * (e.g. offline) so the caller can leave the flat altitude in place.
 */
export async function computeTerrainFollowAltitudes(
  result: SurveyResult,
  config: SurveyConfig,
): Promise<TerrainFollowOutcome | null> {
  const wps = result.waypoints;
  if (wps.length === 0) return null;

  const ground = await getElevations(wps.map((wp) => ({ lat: wp.lat, lon: wp.lng })));

  let resolved = 0;
  let min = Infinity;
  let max = -Infinity;
  const altitudes: number[] = wps.map((_, i) => {
    const agl = result.altitudes?.[i] ?? config.altitude;
    const g = ground[i];
    if (g === null || g === undefined) {
      // No DEM coverage for this point: fall back to a relative-style altitude so
      // a hole in the data degrades to "fly the configured height" rather than 0.
      return agl;
    }
    resolved += 1;
    if (g < min) min = g;
    if (g > max) max = g;
    return Math.round((g + agl) * 10) / 10;
  });

  if (resolved === 0) return null;

  return {
    altitudes,
    resolved,
    terrainRange: min <= max ? { min: Math.round(min), max: Math.round(max) } : null,
  };
}
