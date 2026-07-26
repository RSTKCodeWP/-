/**
 * Survey Statistics Calculator
 */
import type { CameraPreset, LatLng, SurveyConfig, SurveyStats } from './survey-types';
import { distanceLatLng, polygonArea } from './geo-math';

/**
 * Returns the effective survey footprint. If the camera preset has a
 * manualCorridorWidth set (e.g. rover/lawnmower mode with no camera), that
 * value is returned as both width and height so downstream spacing math
 * collapses to "lines spaced at corridor width". Otherwise computes from
 * sensor + focal length + altitude.
 */
export function getEffectiveFootprint(
  camera: CameraPreset,
  altitude: number,
): { width: number; height: number } {
  if (camera.manualCorridorWidth && camera.manualCorridorWidth > 0) {
    const w = camera.manualCorridorWidth;
    return { width: w, height: w };
  }
  return calculateFootprint(camera.sensorWidth, camera.sensorHeight, camera.focalLength, altitude);
}

/**
 * Returns the effective line/photo spacing for the survey. In manual mode the
 * overlap sliders don't apply (there's no camera footprint to overlap), so
 * spacing is the corridor width directly. Critically, this also prevents the
 * default 60% side overlap from collapsing lineSpacing into something tiny
 * (e.g. 0.6 m for a 1.5 m mower deck), which would otherwise produce tens of
 * thousands of waypoints and crash the renderer.
 */
export function getEffectiveSpacing(
  camera: CameraPreset,
  footprintWidth: number,
  footprintHeight: number,
  frontOverlap: number,
  sideOverlap: number,
): { lineSpacing: number; photoSpacing: number } {
  if (camera.manualCorridorWidth && camera.manualCorridorWidth > 0) {
    const w = camera.manualCorridorWidth;
    return { lineSpacing: w, photoSpacing: w };
  }
  return calculateSpacing(footprintWidth, footprintHeight, frontOverlap, sideOverlap);
}

/**
 * Calculate GSD (Ground Sample Distance) in cm/pixel.
 */
export function calculateGSD(
  sensorWidth: number,   // mm
  focalLength: number,   // mm
  imageWidth: number,     // pixels
  altitude: number,       // meters
): number {
  // GSD = (sensorWidth_mm * altitude_m) / (focalLength_mm * imageWidth_px) * 100 (for cm)
  return (sensorWidth * altitude * 100) / (focalLength * imageWidth);
}

/**
 * Inverse of {@link calculateGSD}: the altitude (m) that yields a target GSD
 * (cm/px) for a camera. Lets the planner work GSD-first - surveyors think in
 * cm/px, not metres. Returns 0 for invalid camera inputs.
 */
export function calculateAltitudeForGSD(
  sensorWidth: number,   // mm
  focalLength: number,   // mm
  imageWidth: number,     // pixels
  gsd: number,            // cm/px
): number {
  if (sensorWidth <= 0) return 0;
  return (gsd * focalLength * imageWidth) / (sensorWidth * 100);
}

/**
 * Number of battery swaps a flight needs: total flight time divided by the
 * usable endurance per battery, rounded up. `enduranceMinutes` should already
 * bake in the operator's reserve margin. Returns 0 when inputs are unusable.
 */
export function estimateBatteryCount(flightTimeSeconds: number, enduranceMinutes: number): number {
  if (enduranceMinutes <= 0 || flightTimeSeconds <= 0) return 0;
  return Math.ceil(flightTimeSeconds / 60 / enduranceMinutes);
}

/**
 * Rough captured-data estimate in GB. Uses sensor resolution as a proxy:
 * ~1.2 MB per megapixel approximates a JPEG+RAW pair from a mapping payload.
 * Deliberately an estimate for storage/offload planning, not an exact size.
 */
export function estimateDataSizeGb(photoCount: number, imageWidth: number, imageHeight: number): number {
  const megapixels = (imageWidth * imageHeight) / 1_000_000;
  const mbPerPhoto = megapixels * 1.2;
  return (photoCount * mbPerPhoto) / 1024;
}

/**
 * Calculate survey footprint dimensions.
 */
export function calculateFootprint(
  sensorWidth: number,
  sensorHeight: number,
  focalLength: number,
  altitude: number,
): { width: number; height: number } {
  return {
    width: (sensorWidth * altitude) / focalLength,
    height: (sensorHeight * altitude) / focalLength,
  };
}

/**
 * Calculate line and photo spacing from overlap.
 */
export function calculateSpacing(
  footprintWidth: number,
  footprintHeight: number,
  frontOverlap: number,  // percentage
  sideOverlap: number,   // percentage
): { lineSpacing: number; photoSpacing: number } {
  return {
    lineSpacing: footprintWidth * (1 - sideOverlap / 100),
    photoSpacing: footprintHeight * (1 - frontOverlap / 100),
  };
}

/**
 * Calculate total flight distance from waypoints.
 */
export function calculateFlightDistance(waypoints: LatLng[]): number {
  let total = 0;
  for (let i = 1; i < waypoints.length; i++) {
    total += distanceLatLng(waypoints[i - 1]!, waypoints[i]!);
  }
  return total;
}

/**
 * Compute full survey stats from config and generated data.
 */
export function computeSurveyStats(
  config: SurveyConfig,
  waypoints: LatLng[],
  photoPositions: LatLng[],
  lineCount: number,
): SurveyStats {
  const { camera, altitude, speed } = config;
  // GSD is meaningless without a real camera; report 0 in manual mode.
  const isManual = !!(camera.manualCorridorWidth && camera.manualCorridorWidth > 0);
  const gsd = isManual ? 0 : calculateGSD(camera.sensorWidth, camera.focalLength, camera.imageWidth, altitude);
  const { width: footprintWidth, height: footprintHeight } = getEffectiveFootprint(camera, altitude);
  const { lineSpacing, photoSpacing } = getEffectiveSpacing(
    camera, footprintWidth, footprintHeight, config.frontOverlap, config.sideOverlap,
  );
  const flightDistance = calculateFlightDistance(waypoints);
  const flightTime = speed > 0 ? flightDistance / speed : 0;
  const areaCovered = polygonArea(config.polygon);

  return {
    gsd,
    flightDistance,
    flightTime,
    photoCount: photoPositions.length,
    lineCount,
    areaCovered,
    footprintWidth,
    footprintHeight,
    lineSpacing,
    photoSpacing,
  };
}
