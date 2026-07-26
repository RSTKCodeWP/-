/**
 * @module camera-library
 * @description Extended library of real drone and survey camera profiles for GSD
 * and footprint calculations. Complements the small built-in set in
 * {@link module:gsd-calculator} with popular mapping payloads. Pure data + lookup
 * and validation helpers — no React, store, or map dependencies.
 * @license GPL-3.0-only
 */

import type { CameraProfile } from "@/lib/patterns/gsd-calculator";

/**
 * Popular drone / survey camera profiles.
 *
 * Sensor dimensions are physical active-area sizes in millimetres, focal length
 * is the true (not 35mm-equivalent) lens focal length in millimetres, and image
 * dimensions are the full-resolution still capture in pixels. Values reflect the
 * manufacturers' published specifications for the mapping/still mode. Names are
 * chosen to not collide with the built-in {@link CAMERA_PROFILES}.
 */
export const EXTRA_CAMERA_PROFILES: CameraProfile[] = [
  // Full-frame 45MP mapping flagship (35mm lens option).
  { name: "DJI Zenmuse P1", sensorWidth: 35.9, sensorHeight: 24.0, focalLength: 35, imageWidth: 8192, imageHeight: 5460 },
  // 1" 20MP RTK mapping drone.
  { name: "DJI Phantom 4 RTK", sensorWidth: 13.2, sensorHeight: 8.8, focalLength: 8.8, imageWidth: 5472, imageHeight: 3648 },
  // 4/3 20MP enterprise mapping (mechanical shutter wide camera).
  { name: "DJI Mavic 3 Enterprise", sensorWidth: 17.3, sensorHeight: 13.0, focalLength: 12.29, imageWidth: 5280, imageHeight: 3956 },
  // 1" 20MP compact.
  { name: "DJI Air 2S", sensorWidth: 13.2, sensorHeight: 8.8, focalLength: 8.4, imageWidth: 5472, imageHeight: 3648 },
  // 1" 20MP Hasselblad.
  { name: "DJI Mavic 2 Pro", sensorWidth: 13.2, sensorHeight: 8.8, focalLength: 10.26, imageWidth: 5472, imageHeight: 3648 },
  // Full-frame 24MP with a 35mm survey lens.
  { name: "Sony A7 III", sensorWidth: 35.6, sensorHeight: 23.8, focalLength: 35, imageWidth: 6000, imageHeight: 4000 },
  // APS-C 24MP with a 16mm wide survey lens.
  { name: "Sony A6400", sensorWidth: 23.5, sensorHeight: 15.6, focalLength: 16, imageWidth: 6000, imageHeight: 4000 },
  // 1" 20MP.
  { name: "Autel EVO II Pro", sensorWidth: 13.2, sensorHeight: 8.8, focalLength: 10, imageWidth: 5472, imageHeight: 3648 },
  // Medium-format 100MP metric survey camera (80mm lens).
  { name: "Phase One iXM-100", sensorWidth: 43.9, sensorHeight: 32.9, focalLength: 80, imageWidth: 11664, imageHeight: 8750 },
  // Multispectral survey / agriculture (single band optics).
  { name: "MicaSense RedEdge-MX", sensorWidth: 4.8, sensorHeight: 3.6, focalLength: 5.4, imageWidth: 1280, imageHeight: 960 },
];

/**
 * Find a camera profile by exact name (case-insensitive, whitespace-trimmed).
 *
 * @param name     Camera name to look up.
 * @param profiles List to search. Defaults to {@link EXTRA_CAMERA_PROFILES}.
 *                 Pass a merged list (built-ins + extras + custom) to search all.
 * @returns The matching profile, or `undefined` when none matches.
 */
export function findCameraByName(
  name: string,
  profiles: CameraProfile[] = EXTRA_CAMERA_PROFILES,
): CameraProfile | undefined {
  if (typeof name !== "string") return undefined;
  const target = name.trim().toLowerCase();
  if (target.length === 0) return undefined;
  return profiles.find((c) => c.name.trim().toLowerCase() === target);
}

/** Outcome of {@link validateCameraProfile}. */
export interface CameraValidationResult {
  valid: boolean;
  errors: string[];
}

// Sanity bounds. A sensor larger than this or a lens/resolution outside these
// ranges is almost certainly a data-entry error rather than a real payload.
const MAX_SENSOR_MM = 100; // medium format tops out well under this
const MAX_FOCAL_MM = 2000; // super-telephoto ceiling
const MAX_IMAGE_PX = 100000; // far above any current sensor

function isPositiveFinite(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value > 0;
}

function isPositiveInteger(value: unknown): value is number {
  return isPositiveFinite(value) && Number.isInteger(value);
}

/**
 * Validate a candidate camera profile (e.g. a user-entered or imported payload).
 *
 * Accepts an arbitrary value and checks it structurally so custom cameras can be
 * vetted before they feed a GSD calculation (which silently returns 0 on bad
 * input). Checks: non-empty name, positive finite sensor dimensions and focal
 * length within sane bounds, and positive integer pixel dimensions.
 *
 * @param profile Candidate value of unknown shape.
 * @returns `valid` plus a list of human-readable error messages (empty when valid).
 */
export function validateCameraProfile(profile: unknown): CameraValidationResult {
  const errors: string[] = [];

  if (profile === null || typeof profile !== "object") {
    return { valid: false, errors: ["Camera profile must be an object."] };
  }

  const p = profile as Record<string, unknown>;

  if (typeof p.name !== "string" || p.name.trim().length === 0) {
    errors.push("Camera name is required.");
  }

  if (!isPositiveFinite(p.sensorWidth)) {
    errors.push("sensorWidth must be a positive number (mm).");
  } else if (p.sensorWidth > MAX_SENSOR_MM) {
    errors.push(`sensorWidth ${p.sensorWidth}mm exceeds the ${MAX_SENSOR_MM}mm limit.`);
  }

  if (!isPositiveFinite(p.sensorHeight)) {
    errors.push("sensorHeight must be a positive number (mm).");
  } else if (p.sensorHeight > MAX_SENSOR_MM) {
    errors.push(`sensorHeight ${p.sensorHeight}mm exceeds the ${MAX_SENSOR_MM}mm limit.`);
  }

  if (!isPositiveFinite(p.focalLength)) {
    errors.push("focalLength must be a positive number (mm).");
  } else if (p.focalLength > MAX_FOCAL_MM) {
    errors.push(`focalLength ${p.focalLength}mm exceeds the ${MAX_FOCAL_MM}mm limit.`);
  }

  if (!isPositiveInteger(p.imageWidth)) {
    errors.push("imageWidth must be a positive integer (pixels).");
  } else if (p.imageWidth > MAX_IMAGE_PX) {
    errors.push(`imageWidth ${p.imageWidth}px exceeds the ${MAX_IMAGE_PX}px limit.`);
  }

  if (!isPositiveInteger(p.imageHeight)) {
    errors.push("imageHeight must be a positive integer (pixels).");
  } else if (p.imageHeight > MAX_IMAGE_PX) {
    errors.push(`imageHeight ${p.imageHeight}px exceeds the ${MAX_IMAGE_PX}px limit.`);
  }

  return { valid: errors.length === 0, errors };
}
