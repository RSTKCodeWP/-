/**
 * Pure helpers for the Area Editor live briefing HUD.
 *
 * computeAreaHud accepts pre-computed inputs (areaM2, stats, endurance, image
 * dimensions) so it is unit-testable without any Zustand stores or survey
 * generator side-effects. The React component AreaEditorHud.tsx is responsible
 * for wiring those inputs from the relevant stores.
 *
 * aggregateAreaHud sums per-polygon HUD values into a single combined HUD for
 * display when multiple polygons are present. Battery count is re-derived from
 * the summed flight time rather than summing per-polygon counts.
 */

import { estimateBatteryCount, estimateDataSizeGb } from '../components/survey/survey-stats';
import type { SurveyStats } from '../components/survey/survey-types';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AreaHudInput {
  /** Polygon area in square metres (from polygonArea()). */
  areaM2: number;
  /** Stats from the survey generator, or null when ring < 3 or generator failed. */
  stats: SurveyStats | null;
  /** Usable endurance per battery in seconds (from getEstimatedFlightTime()). */
  enduranceSec: number;
  /** Camera image width in pixels (from the survey config camera preset). */
  imageWidth: number;
  /** Camera image height in pixels (from the survey config camera preset). */
  imageHeight: number;
}

export interface AreaHud {
  /** Area in hectares, or null when no stats are available. */
  areaHa: number | null;
  /** Ground sample distance in cm/px, or null. */
  gsdCm: number | null;
  /** Number of photos, or null. */
  photoCount: number | null;
  /** Estimated captured data in GB, or null. */
  dataGb: number | null;
  /** Total flight path length in metres, or null. */
  flightDistanceM: number | null;
  /** Estimated flight time in seconds, or null. */
  flightTimeSec: number | null;
  /** Number of batteries required, or null when endurance or flight time is unknown. */
  batteryCount: number | null;
}

// ---------------------------------------------------------------------------
// Core computation
// ---------------------------------------------------------------------------

/**
 * Derive the Area Editor HUD metrics from pre-computed survey inputs.
 *
 * When stats is null (ring < 3 points or generator returned nothing) all fields
 * are null. areaHa is derived from the stats.areaCovered value so it is null
 * in that case too - the caller should derive areaM2 from polygonArea() and
 * only pass it alongside valid stats.
 */
export function computeAreaHud(input: AreaHudInput): AreaHud {
  const { stats, enduranceSec, imageWidth, imageHeight } = input;

  if (!stats) {
    return {
      areaHa: null,
      gsdCm: null,
      photoCount: null,
      dataGb: null,
      flightDistanceM: null,
      flightTimeSec: null,
      batteryCount: null,
    };
  }

  const areaHa = stats.areaCovered / 10_000;
  const gsdCm = stats.gsd;
  const photoCount = stats.photoCount;
  const flightDistanceM = stats.flightDistance;
  const flightTimeSec = stats.flightTime;

  const dataGb = estimateDataSizeGb(photoCount, imageWidth, imageHeight);

  const rawBatteryCount = estimateBatteryCount(flightTimeSec, enduranceSec / 60);
  const batteryCount = rawBatteryCount > 0 ? rawBatteryCount : null;

  return {
    areaHa,
    gsdCm,
    photoCount,
    dataGb,
    flightDistanceM,
    flightTimeSec,
    batteryCount,
  };
}

// ---------------------------------------------------------------------------
// Multi-polygon aggregation
// ---------------------------------------------------------------------------

/**
 * Aggregate an array of per-polygon AreaHud values into a single combined HUD.
 *
 * Rules:
 * - areaHa, photoCount, flightDistanceM, flightTimeSec, dataGb: summed across
 *   all non-null values; null when ALL are null.
 * - batteryCount: re-derived from the summed flightTimeSec vs the shared
 *   endurance passed in, so it is NOT just summed.
 * - gsdCm: taken from the first non-null value (polygons share survey config,
 *   so GSD is the same for all; only the active one is shown).
 *
 * @param perPolygon  Array of AreaHud values, one per polygon.
 * @param enduranceSec  Per-battery endurance in seconds (needed to re-derive batteryCount).
 */
export function aggregateAreaHud(perPolygon: AreaHud[], enduranceSec: number): AreaHud {
  if (perPolygon.length === 0) {
    return {
      areaHa: null,
      gsdCm: null,
      photoCount: null,
      dataGb: null,
      flightDistanceM: null,
      flightTimeSec: null,
      batteryCount: null,
    };
  }

  function sumNullable(vals: (number | null)[]): number | null {
    const defined = vals.filter((v): v is number => v !== null);
    return defined.length > 0 ? defined.reduce((a, b) => a + b, 0) : null;
  }

  const areaHa = sumNullable(perPolygon.map((h) => h.areaHa));
  const photoCount = sumNullable(perPolygon.map((h) => h.photoCount));
  const flightDistanceM = sumNullable(perPolygon.map((h) => h.flightDistanceM));
  const flightTimeSec = sumNullable(perPolygon.map((h) => h.flightTimeSec));
  const dataGb = sumNullable(perPolygon.map((h) => h.dataGb));

  const gsdCm = perPolygon.map((h) => h.gsdCm).find((v) => v !== null) ?? null;

  // Re-derive battery count from total flight time so we don't double-count
  // the 1-battery minimum per polygon.
  let batteryCount: number | null = null;
  if (flightTimeSec !== null) {
    const raw = estimateBatteryCount(flightTimeSec, enduranceSec / 60);
    batteryCount = raw > 0 ? raw : null;
  }

  return {
    areaHa,
    gsdCm,
    photoCount,
    dataGb,
    flightDistanceM,
    flightTimeSec,
    batteryCount,
  };
}
