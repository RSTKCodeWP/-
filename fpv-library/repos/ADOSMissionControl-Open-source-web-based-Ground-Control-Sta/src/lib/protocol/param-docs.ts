/**
 * ArduPilot parameter documentation URL helpers.
 *
 * Builds deterministic links to official ArduPilot parameter pages. Does not
 * fetch network metadata (see param-metadata.ts for in-app descriptions/enums).
 *
 * @module protocol/param-docs
 * @license GPL-3.0-only
 */

import type { ArduPilotVehicle } from "./param-metadata";
import type { FirmwareType, VehicleClass } from "./types";
import { firmwareTypeToVehicle } from "./param-metadata";

export interface ParamDocContext {
  vehicle: ArduPilotVehicle;
  /** e.g. V4.5.7 when known; null → unversioned parameters.html */
  versionTag: string | null;
}

/**
 * Resolve docs context from vehicle info fields.
 * Falls back to vehicleClass when firmwareType is not yet classified as ardupilot-*
 * (e.g. brief window as unknown) but class is still copter/plane/rover/sub.
 */
export function resolveParamDocContext(
  firmwareType: FirmwareType | undefined | null,
  firmwareVersionString: string | undefined | null,
  vehicleClass?: VehicleClass | null,
): ParamDocContext | null {
  let vehicle = firmwareType ? firmwareTypeToVehicle(firmwareType) : null;
  if (!vehicle && vehicleClass) {
    switch (vehicleClass) {
      case "copter":
        vehicle = "ArduCopter";
        break;
      case "plane":
        vehicle = "ArduPlane";
        break;
      case "rover":
        vehicle = "Rover";
        break;
      case "sub":
        vehicle = "ArduSub";
        break;
      default:
        vehicle = null;
    }
    // Only use class fallback for ArduPilot-ish firmware strings / unknown AP path
    if (vehicle && firmwareType && firmwareType !== "unknown" && !firmwareType.startsWith("ardupilot-")) {
      return null;
    }
  }
  if (!vehicle) return null;
  return { vehicle, versionTag: parseFirmwareVersionTag(firmwareVersionString) };
}

/** Map vehicle enum to ardupilot.org path segment (copter, plane, …). */
export function vehicleToDocsSlug(vehicle: ArduPilotVehicle): string {
  switch (vehicle) {
    case "ArduCopter":
      return "copter";
    case "ArduPlane":
      return "plane";
    case "Rover":
      return "rover";
    case "ArduSub":
      return "sub";
  }
}

/** Title-case vehicle name segment used in parameters-*.html filenames. */
export function vehicleToDocsTitle(vehicle: ArduPilotVehicle): string {
  switch (vehicle) {
    case "ArduCopter":
      return "Copter";
    case "ArduPlane":
      return "Plane";
    case "Rover":
      return "Rover";
    case "ArduSub":
      return "Sub";
  }
}

/**
 * Extract a stable version tag (e.g. V4.6.3) from AUTOPILOT_VERSION / display strings.
 * Returns null when no semver-like version is present (caller uses the unversioned parameters.html).
 *
 * Note: ardupilot.org has no `parameters-*-stable-latest.html` page — only specific V*.*.* builds
 * or the live `parameters.html` index.
 */
export function parseFirmwareVersionTag(firmwareVersionString: string | undefined | null): string | null {
  if (!firmwareVersionString || !firmwareVersionString.trim()) return null;
  const s = firmwareVersionString.trim();

  // Prefer explicit V-prefixed semver (ArduCopter V4.6.3)
  const vPrefixed = s.match(/\bV(\d+\.\d+(?:\.\d+)?)\b/i);
  if (vPrefixed) return `V${vPrefixed[1]}`;

  // Plain semver often appears after vehicle name (APM:Copter 4.5.7, Copter 4.6.0)
  const plain = s.match(/(?:^|[\s:])(\d+\.\d+(?:\.\d+)?)(?:\b|$)/);
  if (plain) return `V${plain[1]}`;

  return null;
}

/**
 * Sphinx/RTD section id for a param on ardupilot.org parameter pages.
 * `AHRS_GPS_MINSATS` → `ahrs-gps-minsats` (underscores become hyphens; not snake_case fragments).
 */
export function paramNameToDocFragment(paramName: string): string {
  return paramName.trim().toLowerCase().replace(/_/g, "-");
}

/**
 * Official ArduPilot parameter docs URL for a single parameter.
 *
 * Versioned (when known): `…/parameters-Copter-stable-V4.5.7.html#ahrs-gps-minsats`
 * Fallback (dev / unknown version): `…/parameters.html#ahrs-gps-minsats`
 */
export function getParamDocUrl(
  paramName: string,
  vehicle: ArduPilotVehicle,
  versionTag: string | null = null,
): string {
  const slug = vehicleToDocsSlug(vehicle);
  const title = vehicleToDocsTitle(vehicle);
  const fragment = paramNameToDocFragment(paramName);
  const ver =
    versionTag && versionTag !== "latest"
      ? versionTag.startsWith("V")
        ? versionTag
        : `V${versionTag}`
      : null;

  if (ver) {
    return `https://ardupilot.org/${slug}/docs/parameters-${title}-stable-${ver}.html#${fragment}`;
  }
  return `https://ardupilot.org/${slug}/docs/parameters.html#${fragment}`;
}

/** Build doc URL when context is available; null for non-ArduPilot. */
export function getParamDocUrlFromContext(
  paramName: string,
  ctx: ParamDocContext | null | undefined,
): string | null {
  if (!ctx) return null;
  return getParamDocUrl(paramName, ctx.vehicle, ctx.versionTag);
}
