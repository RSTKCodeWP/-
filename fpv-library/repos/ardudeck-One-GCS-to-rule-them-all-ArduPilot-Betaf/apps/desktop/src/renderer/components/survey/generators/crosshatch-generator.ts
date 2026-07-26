/**
 * Crosshatch (Double Grid) Pattern Generator
 * Runs the grid generator twice: once at gridAngle, once at gridAngle + 90.
 * Produces double coverage for 3D reconstruction.
 *
 * Optional second-pass altitude offset (config.crossGridAltitudeOffset, % of
 * relative altitude): the perpendicular pass flies higher (or lower) than the
 * first. Flying the two directions at two different heights improves
 * photogrammetric 3D reconstruction. The offset changes the second pass's
 * footprint and therefore its line spacing, exactly as a real altitude change
 * would, and the per-waypoint altitudes are carried on the result so the
 * mission builder emits the correct height for each leg.
 */
import type { SurveyConfig, SurveyResult } from '../survey-types';
import { generateGrid, routeTransitLatLng } from './grid-generator';
import { computeSurveyStats } from '../survey-stats';

export function generateCrosshatch(config: SurveyConfig): SurveyResult {
  // First pass at original angle
  const pass1 = generateGrid(config);

  // Second pass at 90 degrees, optionally at a different altitude.
  const offsetPct = config.crossGridAltitudeOffset ?? 0;
  const pass2Altitude =
    offsetPct !== 0 ? config.altitude * (1 + offsetPct / 100) : config.altitude;
  const pass2Config: SurveyConfig = {
    ...config,
    gridAngle: (config.gridAngle + 90) % 360,
    altitude: pass2Altitude,
  };
  const pass2 = generateGrid(pass2Config);

  // Combine results. The junction leg between the passes is a transit like
  // any other - route it around no-fly holes.
  const junction =
    pass1.waypoints.length > 0 && pass2.waypoints.length > 0
      ? routeTransitLatLng(
          pass1.waypoints[pass1.waypoints.length - 1]!,
          pass2.waypoints[0]!,
          config.holes ?? [],
        )
      : [];
  const waypoints = [...pass1.waypoints, ...junction, ...pass2.waypoints];
  const photoPositions = [...pass1.photoPositions, ...pass2.photoPositions];
  const footprints = [...pass1.footprints, ...pass2.footprints];
  const lineCount = pass1.stats.lineCount + pass2.stats.lineCount;

  const stats = computeSurveyStats(config, waypoints, photoPositions, lineCount);

  const result: SurveyResult = { waypoints, photoPositions, footprints, stats };

  // Only carry explicit per-waypoint altitudes when the two passes actually
  // differ; the common case stays on the uniform config.altitude path.
  if (offsetPct !== 0) {
    result.altitudes = [
      ...pass1.waypoints.map(() => config.altitude),
      ...junction.map(() => config.altitude),
      ...pass2.waypoints.map(() => pass2Altitude),
    ];
  }

  return result;
}
