/**
 * @module terrain/types
 * @description Types for terrain elevation data and terrain-following profiles.
 * @license GPL-3.0-only
 */

/** A single point along a terrain profile with position and elevation. */
export interface TerrainPoint {
  lat: number;
  lon: number;
  distance: number;    // meters from path start
  elevation: number;   // meters MSL
}

/** A complete terrain elevation profile along a waypoint path. */
export interface TerrainProfile {
  points: TerrainPoint[];
  minElevation: number;
  maxElevation: number;
}
