/**
 * @module gsd-solver
 * @description GSD-first survey solver. Inverts the Ground Sample Distance math
 * to answer the questions an operator actually asks: "what altitude gives me this
 * GSD?" and "how fast can I fly before motion blur ruins the shot?".
 *
 * Consistent with {@link module:gsd-calculator}: GSD (m/px) = (sensorWidth * altitude)
 * / (focalLength * imageWidth). These solvers work in centimetres-per-pixel because
 * that is the unit operators plan surveys in (1-5 cm/px is the common range).
 * @license GPL-3.0-only
 */

import type { CameraProfile } from "./gsd-calculator";

/**
 * Solve for the flight altitude that yields a target GSD. Exact inverse of
 * {@link computeGSD}: starting from GSD_m = (sensorWidth * altitude) /
 * (focalLength * imageWidth), altitude = GSD_m * focalLength * imageWidth / sensorWidth.
 *
 * @param gsdCmPerPx Desired ground sample distance in centimetres per pixel
 * @param camera     Camera profile (focalLength mm, sensorWidth mm, imageWidth px)
 * @returns Required flight altitude in metres AGL, or 0 for invalid inputs
 */
export function solveAltitudeForGSD(
  gsdCmPerPx: number,
  camera: CameraProfile,
): number {
  if (
    gsdCmPerPx <= 0 ||
    camera.sensorWidth <= 0 ||
    camera.focalLength <= 0 ||
    camera.imageWidth <= 0
  ) {
    return 0;
  }
  const gsdMetres = gsdCmPerPx / 100;
  return (gsdMetres * camera.focalLength * camera.imageWidth) / camera.sensorWidth;
}

/**
 * Maximum ground speed that keeps motion blur under a pixel tolerance.
 * During the exposure the camera moves blurMetres = speed * exposure across the
 * scene; that smear is blurMetres / gsd_m pixels wide. Holding blur at the
 * tolerance and solving for speed:
 *   speed = blurTolerancePx * gsd_m / exposure
 *
 * @param gsdCmPerPx     Ground sample distance in centimetres per pixel
 * @param exposureTimeS  Shutter/exposure time in seconds (e.g. 1/500 = 0.002)
 * @param blurTolerancePx Acceptable motion blur in pixels (default 1)
 * @returns Maximum safe ground speed in metres/second, or 0 for invalid inputs
 */
export function maxSafeGroundSpeed(
  gsdCmPerPx: number,
  exposureTimeS: number,
  blurTolerancePx = 1,
): number {
  if (gsdCmPerPx <= 0 || exposureTimeS <= 0 || blurTolerancePx <= 0) return 0;
  const gsdMetres = gsdCmPerPx / 100;
  return (blurTolerancePx * gsdMetres) / exposureTimeS;
}

/**
 * Motion blur, in pixels, produced by flying at a given ground speed for a given
 * exposure. blurMetres = speed * exposure; blurPx = blurMetres / gsd_m.
 *
 * @param speed         Ground speed in metres/second
 * @param exposureTimeS Shutter/exposure time in seconds
 * @param gsdCmPerPx    Ground sample distance in centimetres per pixel
 * @returns Motion blur in pixels, or 0 for invalid inputs
 */
export function motionBlurPixels(
  speed: number,
  exposureTimeS: number,
  gsdCmPerPx: number,
): number {
  if (gsdCmPerPx <= 0 || exposureTimeS <= 0 || speed < 0) return 0;
  const blurMetres = speed * exposureTimeS;
  const gsdMetres = gsdCmPerPx / 100;
  return blurMetres / gsdMetres;
}
