/**
 * @module build-sampled-properties
 * @description Builds CesiumJS SampledPositionProperty + SampledProperty<heading>
 * from a flight plan. Pure function — no React, no side effects.
 * @license GPL-3.0-only
 */

import {
  JulianDate,
  SampledPositionProperty,
  SampledProperty,
  LinearApproximation,
  Cartesian3,
  Math as CesiumMath,
} from "cesium";
import type { Waypoint } from "@/lib/types";
import type { FlightPlan } from "@/lib/simulation-utils";

export interface SampledProperties {
  sampledPosition: SampledPositionProperty;
  sampledHeading: SampledProperty;
  startJulian: JulianDate;
}

// Scratch JulianDate reused for intermediate computations to reduce allocations
const _scratch = new JulianDate();

/**
 * Compute cumulative Cartesian3 distances between consecutive positions.
 * Returns array of length positions.length where [0] = 0.
 */
function cumulativeDistances(positions: Cartesian3[]): number[] {
  const dists = [0];
  for (let i = 1; i < positions.length; i++) {
    dists.push(dists[i - 1] + Cartesian3.distance(positions[i - 1], positions[i]));
  }
  return dists;
}

/**
 * Build CesiumJS sampled properties from waypoints and a computed flight plan.
 *
 * When allPositions + waypointIndices are provided (from resolveAGLToAbsolute),
 * intermediate terrain-following sub-samples are included. Travel time is
 * distributed proportionally by Cartesian3 distance along intermediates so the
 * drone follows the terrain contour instead of cutting through hills.
 *
 * When only waypointPositions is provided (legacy), one sample per waypoint.
 *
 * Returns null if there are no waypoints or segments.
 */
export function buildSampledProperties(
  waypoints: Waypoint[],
  flightPlan: FlightPlan,
  waypointPositions?: Cartesian3[],
  allPositions?: Cartesian3[],
  waypointIndices?: number[]
): SampledProperties | null {
  if (waypoints.length === 0 || flightPlan.segments.length === 0) return null;

  const useIntermediates = !!allPositions && !!waypointIndices;

  const startJulian = JulianDate.fromDate(new Date(0)); // Arbitrary epoch
  const sampledPosition = new SampledPositionProperty();
  const sampledHeading = new SampledProperty(Number);

  // Linear interpolation — drone flies in straight lines between samples
  sampledPosition.setInterpolationOptions({
    interpolationAlgorithm: LinearApproximation,
    interpolationDegree: 1,
  });
  sampledHeading.setInterpolationOptions({
    interpolationAlgorithm: LinearApproximation,
    interpolationDegree: 1,
  });

  let t = JulianDate.clone(startJulian);

  for (let i = 0; i < waypoints.length; i++) {
    const wp = waypoints[i];
    // Waypoint position: from resolved array or computed from AGL
    const wpPos = useIntermediates
      ? allPositions[waypointIndices[i]]
      : waypointPositions?.[i] ?? Cartesian3.fromDegrees(wp.lon, wp.lat, wp.alt);

    // Heading for this segment (or last segment for final waypoint)
    const segIdx = Math.min(i, flightPlan.segments.length - 1);
    const hdgRad = -CesiumMath.toRadians(flightPlan.segments[segIdx].heading);

    // Arrival sample at waypoint
    sampledPosition.addSample(JulianDate.clone(t), wpPos);
    sampledHeading.addSample(JulianDate.clone(t), hdgRad);

    if (i < waypoints.length - 1) {
      const holdTime = wp.holdTime ?? 0;
      if (holdTime > 0) {
        // Duplicate position at departure = drone holds in place
        t = JulianDate.addSeconds(t, holdTime, _scratch);
        t = JulianDate.clone(t);
        sampledPosition.addSample(JulianDate.clone(t), wpPos);
        sampledHeading.addSample(JulianDate.clone(t), hdgRad);
      }

      // Travel to next waypoint
      const seg = flightPlan.segments[i];
      const travelTime = seg.duration - holdTime;

      if (travelTime > 0 && useIntermediates) {
        // Add intermediate terrain-following samples
        const startIdx = waypointIndices[i];
        const endIdx = waypointIndices[i + 1];
        const segPositions = allPositions.slice(startIdx, endIdx + 1);

        if (segPositions.length > 2) {
          // Distribute travel time proportionally by distance
          const cumDists = cumulativeDistances(segPositions);
          const totalDist = cumDists[cumDists.length - 1];

          // Add samples for intermediates (skip first = current wp, skip last = next wp arrival)
          for (let j = 1; j < segPositions.length - 1; j++) {
            const frac = totalDist > 0 ? cumDists[j] / totalDist : j / (segPositions.length - 1);
            const intermediateT = JulianDate.addSeconds(t, travelTime * frac, _scratch);
            sampledPosition.addSample(JulianDate.clone(intermediateT), segPositions[j]);
            sampledHeading.addSample(JulianDate.clone(intermediateT), hdgRad);
          }
        }

        // Heading sample just before arrival to prevent blending across segments
        const almostArrival = JulianDate.addSeconds(t, travelTime - 0.001, _scratch);
        sampledHeading.addSample(JulianDate.clone(almostArrival), hdgRad);
        t = JulianDate.addSeconds(t, travelTime, _scratch);
        t = JulianDate.clone(t);
      } else if (travelTime > 0) {
        // No intermediates — heading sample at end of segment
        const almostArrival = JulianDate.addSeconds(t, travelTime - 0.001, _scratch);
        sampledHeading.addSample(JulianDate.clone(almostArrival), hdgRad);
        t = JulianDate.addSeconds(t, travelTime, _scratch);
        t = JulianDate.clone(t);
      }
    } else if (wp.holdTime) {
      // Last waypoint hold
      t = JulianDate.addSeconds(t, wp.holdTime, _scratch);
      t = JulianDate.clone(t);
      sampledPosition.addSample(JulianDate.clone(t), wpPos);
      sampledHeading.addSample(JulianDate.clone(t), hdgRad);
    }
  }

  return { sampledPosition, sampledHeading, startJulian };
}
