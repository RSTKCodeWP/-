/**
 * @module simulation/sampled-track-source
 * @description Time-sampled track abstraction for the mission simulation viewer.
 * A SampledTrackSource is anything the viewer can ask for a position/attitude at
 * an elapsed time: a kinematic path derived from planned waypoints, a recorded
 * flight replay, or a live telemetry feed. The viewer's sampled memo generalizes
 * from a single mission path to an array of these so multiple tracks (planned +
 * replayed + live) can share one clock.
 *
 * Pure logic — no React, no store, no map/Cesium imports. Fully unit-testable.
 * @license GPL-3.0-only
 */

import type { Waypoint } from "@/lib/types";
import { computeFlightPlan, interpolatePosition } from "@/lib/simulation-utils";

/** A single position/attitude sample at one instant along a track. */
export interface TrackSample {
  lat: number;
  lon: number;
  /** Meters. Frame follows the source (AGL for a kinematic waypoint path). */
  alt: number;
  /** Heading in degrees, 0-360. */
  headingDeg: number;
  /** Ground speed in meters per second. */
  speedMps: number;
}

/**
 * Where a track's samples come from.
 * - `kinematic`: interpolated from planned waypoints at a constant speed.
 * - `replay`: read back from a recorded flight log.
 * - `live`: streamed from a connected vehicle's telemetry.
 */
export type TrackSourceTier = "kinematic" | "replay" | "live";

/**
 * A time-addressable source of position/attitude samples. The viewer drives one
 * shared clock and asks each source for its state at the current elapsed time.
 */
export interface SampledTrackSource {
  /** Stable identity for this track within a tracks[] set. */
  id: string;
  sourceTier: TrackSourceTier;
  /**
   * Total playable length in seconds. For a kinematic source this equals the
   * planned flight plan's total duration (segment travel + hold times).
   */
  duration: number;
  /**
   * Return the sample at `tSeconds` elapsed, or `null` when the source has no
   * data to report at that time (e.g. an empty path, or a replay/live source
   * queried outside its recorded window).
   */
  sampleAt(tSeconds: number): TrackSample | null;
}

/**
 * Build a kinematic track source from planned waypoints.
 *
 * This is the generalization the simulation viewer consumes: it delegates to the
 * same `computeFlightPlan` + `interpolatePosition` the viewer already uses, so a
 * kinematic track stays byte-identical to the current single-path sampling.
 * `speedMps` is the default cruise speed; per-waypoint `speed` and `holdTime`
 * overrides still apply exactly as in the underlying flight plan.
 *
 * `sampleAt` clamps to the first waypoint at or before t=0 and to the last
 * waypoint at or after `duration`, matching the viewer's clamped playback. It
 * returns `null` only when there are no waypoints.
 */
export function makeKinematicTrackSource(
  waypoints: Waypoint[],
  speedMps: number,
  id = "kinematic"
): SampledTrackSource {
  const flightPlan = computeFlightPlan(waypoints, speedMps);

  return {
    id,
    sourceTier: "kinematic",
    duration: flightPlan.totalDuration,
    sampleAt(tSeconds: number): TrackSample | null {
      if (waypoints.length === 0) return null;
      const pos = interpolatePosition(flightPlan.segments, waypoints, tSeconds);
      return {
        lat: pos.lat,
        lon: pos.lon,
        alt: pos.alt,
        headingDeg: pos.heading,
        speedMps: pos.speed,
      };
    },
  };
}
