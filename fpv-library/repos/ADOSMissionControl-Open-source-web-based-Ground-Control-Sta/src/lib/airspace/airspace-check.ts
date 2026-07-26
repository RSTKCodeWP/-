/**
 * @module airspace/airspace-check
 * @description Keyless static-ring airspace proximity gate. Flags mission
 * waypoints that fall within warning / error distance rings of a major airport,
 * using the offline {@link MAJOR_AIRPORTS} dataset (no OpenAIP, no network).
 * Pure logic — no store or React imports.
 * @license GPL-3.0-only
 */

import { nearestAirport, type Airport } from "./airports";

/** A point with a latitude and longitude. Any waypoint-like shape works. */
export interface LatLon {
  lat: number;
  lon: number;
}

/** Severity of an airport-proximity issue. */
export type AirspaceIssueLevel = "warn" | "error";

/** A single airport-proximity finding. */
export interface AirspaceProximityIssue {
  /** `"error"` inside the inner ring, `"warn"` inside the outer ring. */
  level: AirspaceIssueLevel;
  /** The nearest airport that triggered the issue. */
  airport: Airport;
  /** Closest-approach distance across the mission's waypoints (kilometers). */
  distanceKm: number;
  /** Index of the waypoint at the closest approach to this airport. */
  waypointIndex: number;
  /** Human-readable summary. */
  message: string;
}

/** Thresholds for the static rings. Defaults: warn at 8 km, error at 5 km. */
export interface AirspaceCheckOptions {
  /** Outer warning ring radius in kilometers. Default 8. */
  warnKm?: number;
  /** Inner error ring radius in kilometers. Default 5. */
  errorKm?: number;
}

/**
 * Check every waypoint against the static airport rings.
 *
 * For each airport that any waypoint approaches within `warnKm`, a single issue
 * is emitted at the closest approach (deduplicated per airport so a mission that
 * lingers near one field does not flood the panel). A waypoint inside `errorKm`
 * raises the issue to `"error"`; between `errorKm` and `warnKm` it is `"warn"`.
 *
 * @param waypoints ordered mission waypoints (lat/lon)
 * @param options ring radii; `errorKm` should be <= `warnKm`
 * @returns issues sorted by ascending closest-approach distance
 */
export function checkAirportProximity(
  waypoints: readonly LatLon[],
  options: AirspaceCheckOptions = {}
): AirspaceProximityIssue[] {
  const warnKm = options.warnKm ?? 8;
  const errorKmRaw = options.errorKm ?? 5;
  // Guard against a misconfigured errorKm > warnKm: the error ring can never be
  // larger than the warning ring.
  const errorKm = Math.min(errorKmRaw, warnKm);

  // Closest approach per airport (keyed by ICAO).
  const closest = new Map<
    string,
    { airport: Airport; distanceKm: number; waypointIndex: number }
  >();

  for (let i = 0; i < waypoints.length; i++) {
    const wp = waypoints[i];
    if (!Number.isFinite(wp.lat) || !Number.isFinite(wp.lon)) continue;

    const near = nearestAirport(wp.lat, wp.lon);
    if (near === null) continue;
    if (near.distanceKm > warnKm) continue;

    const prev = closest.get(near.airport.icao);
    if (prev === undefined || near.distanceKm < prev.distanceKm) {
      closest.set(near.airport.icao, {
        airport: near.airport,
        distanceKm: near.distanceKm,
        waypointIndex: i,
      });
    }
  }

  const issues: AirspaceProximityIssue[] = [];
  for (const entry of closest.values()) {
    const level: AirspaceIssueLevel = entry.distanceKm <= errorKm ? "error" : "warn";
    const ring = level === "error" ? errorKm : warnKm;
    const wpLabel = `WP${entry.waypointIndex + 1}`;
    const message =
      `${wpLabel} is ${entry.distanceKm.toFixed(1)} km from ${entry.airport.name} ` +
      `(${entry.airport.icao}), inside the ${ring} km ` +
      `${level === "error" ? "no-fly" : "caution"} ring.`;
    issues.push({
      level,
      airport: entry.airport,
      distanceKm: entry.distanceKm,
      waypointIndex: entry.waypointIndex,
      message,
    });
  }

  issues.sort((a, b) => a.distanceKm - b.distanceKm);
  return issues;
}
