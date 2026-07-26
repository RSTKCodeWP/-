/**
 * @module gsd-calculator
 * @description Ground Sample Distance (GSD) calculator for survey/mapping missions.
 * Computes GSD, image footprint, line spacing (sidelap), and trigger distance (frontlap)
 * given a camera profile and flight altitude.
 * @license GPL-3.0-only
 */

/** Camera sensor and lens profile used for GSD calculations. */
export interface CameraProfile {
  name: string;
  sensorWidth: number;   // mm
  sensorHeight: number;  // mm
  focalLength: number;   // mm
  imageWidth: number;    // pixels
  imageHeight: number;   // pixels
}

/** Built-in camera profiles for common survey/mapping cameras. */
export const CAMERA_PROFILES: CameraProfile[] = [
  { name: "GoPro Hero 12", sensorWidth: 6.17, sensorHeight: 4.55, focalLength: 2.7, imageWidth: 5312, imageHeight: 3984 },
  { name: "Sony A7R IV", sensorWidth: 35.7, sensorHeight: 23.8, focalLength: 35, imageWidth: 9504, imageHeight: 6336 },
  { name: "DJI Mavic 3", sensorWidth: 17.3, sensorHeight: 13.0, focalLength: 12.29, imageWidth: 5280, imageHeight: 3956 },
  { name: "DJI Mini 4 Pro", sensorWidth: 9.7, sensorHeight: 7.3, focalLength: 6.72, imageWidth: 4032, imageHeight: 3024 },
  { name: "Ricoh GR III", sensorWidth: 23.5, sensorHeight: 15.6, focalLength: 18.3, imageWidth: 6000, imageHeight: 4000 },
  { name: 'Generic 1/2.3"', sensorWidth: 6.17, sensorHeight: 4.55, focalLength: 4.5, imageWidth: 4000, imageHeight: 3000 },
];

/**
 * Compute Ground Sample Distance (GSD) in meters per pixel.
 * GSD = (sensorWidth * altitude) / (focalLength * imageWidth)
 *
 * @param altitude    Flight altitude in meters AGL
 * @param focalLength Lens focal length in mm
 * @param sensorWidth Sensor width in mm
 * @param imageWidth  Image width in pixels
 * @returns GSD in meters/pixel
 */
export function computeGSD(
  altitude: number,
  focalLength: number,
  sensorWidth: number,
  imageWidth: number,
): number {
  if (altitude < 0 || sensorWidth <= 0 || focalLength <= 0 || imageWidth <= 0) return 0;
  // sensorWidth is in mm, altitude in m => multiply by 0.001 to get m, then cancel
  // GSD (m/px) = (sensorWidth_mm * altitude_m) / (focalLength_mm * imageWidth_px)
  return (sensorWidth * altitude) / (focalLength * imageWidth);
}

/**
 * Compute image footprint on the ground at a given altitude.
 *
 * @param altitude Flight altitude in meters AGL
 * @param camera   Camera profile
 * @returns Footprint width and height in meters
 */
export function computeFootprint(
  altitude: number,
  camera: CameraProfile,
): { width: number; height: number } {
  const gsdW = computeGSD(altitude, camera.focalLength, camera.sensorWidth, camera.imageWidth);
  const gsdH = computeGSD(altitude, camera.focalLength, camera.sensorHeight, camera.imageHeight);
  return {
    width: gsdW * camera.imageWidth,
    height: gsdH * camera.imageHeight,
  };
}

/**
 * Compute line spacing for a given sidelap percentage.
 * Line spacing = footprint_width * (1 - sidelap)
 *
 * @param altitude Flight altitude in meters AGL
 * @param camera   Camera profile
 * @param sidelap  Desired sidelap as a fraction (0 to 1), e.g. 0.6 for 60%
 * @returns Line spacing in meters
 */
export function computeLineSpacing(
  altitude: number,
  camera: CameraProfile,
  sidelap: number,
): number {
  const footprint = computeFootprint(altitude, camera);
  return footprint.width * (1 - sidelap);
}

/**
 * Compute camera trigger distance for a given frontlap percentage.
 * Trigger distance = footprint_height * (1 - frontlap)
 *
 * @param altitude Flight altitude in meters AGL
 * @param camera   Camera profile
 * @param frontlap Desired frontlap as a fraction (0 to 1), e.g. 0.7 for 70%
 * @returns Trigger distance in meters
 */
export function computeTriggerDistance(
  altitude: number,
  camera: CameraProfile,
  frontlap: number,
): number {
  const footprint = computeFootprint(altitude, camera);
  return footprint.height * (1 - frontlap);
}
