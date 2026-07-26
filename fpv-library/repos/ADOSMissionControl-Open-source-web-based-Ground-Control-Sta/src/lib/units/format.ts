/**
 * @module units/format
 * @description Units-aware display formatters (metric / imperial). Geometry math
 * stays in meters everywhere; only the display layer converts. Phase-B repoints
 * the planner's label sites (map segment labels, stats bar, measure/drawing
 * labels, pattern stats) through these so the settings `units` toggle finally
 * drives what the operator sees.
 * @license GPL-3.0-only
 */

import type { UnitSystem } from "@/stores/settings-store-types";

const FT_PER_M = 3.280839895;
const MI_PER_M = 1 / 1609.344;
const FT2_PER_M2 = FT_PER_M * FT_PER_M;
const ACRE_PER_M2 = 1 / 4046.8564224;
const HA_PER_M2 = 1 / 10_000;
const MPH_PER_MS = 2.236936292;

/** Format a distance (meters) for display in the given unit system. */
export function formatDistance(meters: number, system: UnitSystem = "metric"): string {
  if (!Number.isFinite(meters)) return "—";
  if (system === "imperial") {
    const ft = meters * FT_PER_M;
    if (Math.abs(meters) >= 1609.344) return `${(meters * MI_PER_M).toFixed(2)} mi`;
    return `${Math.round(ft)} ft`;
  }
  if (Math.abs(meters) >= 1000) return `${(meters / 1000).toFixed(2)} km`;
  return `${Math.round(meters)} m`;
}

/** Format an area (square meters) for display in the given unit system. */
export function formatArea(sqMeters: number, system: UnitSystem = "metric"): string {
  if (!Number.isFinite(sqMeters)) return "—";
  if (system === "imperial") {
    if (sqMeters >= 4046.8564224) return `${(sqMeters * ACRE_PER_M2).toFixed(2)} ac`;
    return `${Math.round(sqMeters * FT2_PER_M2)} ft²`;
  }
  if (sqMeters >= 1e6) return `${(sqMeters / 1e6).toFixed(2)} km²`;
  if (sqMeters >= 10_000) return `${(sqMeters * HA_PER_M2).toFixed(2)} ha`;
  return `${Math.round(sqMeters)} m²`;
}

/** Format a speed (m/s) for display in the given unit system. */
export function formatSpeed(metersPerSecond: number, system: UnitSystem = "metric"): string {
  if (!Number.isFinite(metersPerSecond)) return "—";
  if (system === "imperial") return `${(metersPerSecond * MPH_PER_MS).toFixed(1)} mph`;
  return `${metersPerSecond.toFixed(1)} m/s`;
}

/** Format an altitude (meters) for display in the given unit system. */
export function formatAltitude(meters: number, system: UnitSystem = "metric"): string {
  if (!Number.isFinite(meters)) return "—";
  if (system === "imperial") return `${Math.round(meters * FT_PER_M)} ft`;
  return `${Math.round(meters)} m`;
}

/** Short unit suffix for the given quantity, for compact labels/axes. */
export function unitSuffix(kind: "distance" | "altitude" | "speed", system: UnitSystem = "metric"): string {
  if (system === "imperial") return kind === "speed" ? "mph" : "ft";
  return kind === "speed" ? "m/s" : "m";
}
