/**
 * @module terrain-clearance
 * @description Continuous along-leg terrain-clearance analysis. A mission leg is
 * a straight line between two waypoints; the terrain BETWEEN them can rise above
 * the flight path even when both endpoints are safely clear, so clearance must be
 * checked along the whole path (at each terrain profile sample), not just at the
 * waypoints. Pure module: no React, no store, no I/O — fully unit-testable.
 * @license GPL-3.0-only
 */

/** Default minimum above-ground-level clearance, in metres. */
export const DEFAULT_MIN_TERRAIN_CLEARANCE = 5;

/** One sample along the path: cumulative distance + the flight path's height above ground there. */
export interface ClearanceSample {
  /** Cumulative distance along the path, in metres. */
  distance: number;
  /** Flight-path height above terrain at this distance, in metres (may be negative). */
  agl: number;
}

/** A contiguous stretch of the path where clearance drops below the minimum. */
export interface CollisionSegment {
  /** Distance (m) where the conflict starts. */
  startDistance: number;
  /** Distance (m) where the conflict ends. */
  endDistance: number;
  /** The lowest clearance (m, may be negative) within the segment. */
  minAgl: number;
}

/**
 * Find the contiguous segments of a path where the flight-path clearance drops
 * below `minClearance`. Samples must be ordered by ascending distance. A single
 * conflicting sample yields a zero-length segment at its distance.
 */
export function findCollisionSegments(
  samples: readonly ClearanceSample[],
  minClearance: number = DEFAULT_MIN_TERRAIN_CLEARANCE,
): CollisionSegment[] {
  const segments: CollisionSegment[] = [];
  let current: CollisionSegment | null = null;
  for (const s of samples) {
    const conflicting = s.agl < minClearance;
    if (conflicting) {
      if (current === null) {
        current = { startDistance: s.distance, endDistance: s.distance, minAgl: s.agl };
      } else {
        current.endDistance = s.distance;
        current.minAgl = Math.min(current.minAgl, s.agl);
      }
    } else if (current !== null) {
      segments.push(current);
      current = null;
    }
  }
  if (current !== null) segments.push(current);
  return segments;
}

/** True when any sample breaches the clearance minimum. */
export function hasTerrainConflict(
  samples: readonly ClearanceSample[],
  minClearance: number = DEFAULT_MIN_TERRAIN_CLEARANCE,
): boolean {
  return samples.some((s) => s.agl < minClearance);
}
