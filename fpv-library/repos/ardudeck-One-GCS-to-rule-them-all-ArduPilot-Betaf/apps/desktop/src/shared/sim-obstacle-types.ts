/**
 * User-authored simulator obstacles.
 *
 * Obstacles are stored in geographic coordinates (anchored to a test site) so
 * they persist across sessions, render identically in the 3D world and on the
 * map, and convert 1:1 into ArduPilot exclusion fences (the "fence hack" that
 * makes the flight controller genuinely avoid them).
 */
export interface AuthoredObstacle {
  id: string;
  lat: number;
  lon: number;
  shape: 'cylinder' | 'box';
  /** Cylinder radius, or box half-extent, in metres. */
  radius: number;
  /** Visual height in metres (fences are 2D, height is for the 3D view). */
  height: number;
  label?: string;
}

/** Persisted shape: obstacle sets keyed by site id (rounded home lat/lon). */
export interface SimObstacleStoreSchema {
  sites: Record<string, AuthoredObstacle[]>;
}
