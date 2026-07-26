/**
 * PID parameter safety validation.
 *
 * Defines safe ranges for copter and plane PID parameters, filter
 * parameters, and maximum allowed deltas per suggestion.
 *
 * @license GPL-3.0-only
 */

import type { ParamSafetyRange } from "@/lib/analysis/types";
import type { VehicleType } from "@/components/fc/pid/pid-constants";

// ---------------------------------------------------------------------------
// Safety range definitions
// ---------------------------------------------------------------------------

/** Copter PID safe ranges. */
const COPTER_RANGES: Record<string, ParamSafetyRange> = {
  // Roll rate PID
  ATC_RAT_RLL_P: { min: 0.01, max: 0.5, maxDelta: 0.05 },
  ATC_RAT_RLL_I: { min: 0.01, max: 1.0, maxDelta: 0.05 },
  ATC_RAT_RLL_D: { min: 0.0, max: 0.05, maxDelta: 0.005 },
  ATC_RAT_RLL_FF: { min: 0.0, max: 1.0, maxDelta: 0.05 },
  ATC_RAT_RLL_FLTT: { min: 0, max: 100, maxDelta: 10 },
  ATC_RAT_RLL_FLTD: { min: 0, max: 100, maxDelta: 10 },
  // Pitch rate PID
  ATC_RAT_PIT_P: { min: 0.01, max: 0.5, maxDelta: 0.05 },
  ATC_RAT_PIT_I: { min: 0.01, max: 1.0, maxDelta: 0.05 },
  ATC_RAT_PIT_D: { min: 0.0, max: 0.05, maxDelta: 0.005 },
  ATC_RAT_PIT_FF: { min: 0.0, max: 1.0, maxDelta: 0.05 },
  ATC_RAT_PIT_FLTT: { min: 0, max: 100, maxDelta: 10 },
  ATC_RAT_PIT_FLTD: { min: 0, max: 100, maxDelta: 10 },
  // Yaw rate PID
  ATC_RAT_YAW_P: { min: 0.01, max: 0.5, maxDelta: 0.05 },
  ATC_RAT_YAW_I: { min: 0.01, max: 1.0, maxDelta: 0.05 },
  ATC_RAT_YAW_D: { min: 0.0, max: 0.05, maxDelta: 0.005 },
  ATC_RAT_YAW_FF: { min: 0.0, max: 1.0, maxDelta: 0.05 },
  ATC_RAT_YAW_FLTT: { min: 0, max: 100, maxDelta: 10 },
  ATC_RAT_YAW_FLTD: { min: 0, max: 100, maxDelta: 10 },
};

/** Plane PID safe ranges. */
const PLANE_RANGES: Record<string, ParamSafetyRange> = {
  // Roll
  RLL2SRV_P: { min: 0.01, max: 5.0, maxDelta: 0.5 },
  RLL2SRV_I: { min: 0.01, max: 5.0, maxDelta: 0.5 },
  RLL2SRV_D: { min: 0.0, max: 5.0, maxDelta: 0.5 },
  RLL2SRV_IMAX: { min: 0, max: 4500, maxDelta: 500 },
  RLL2SRV_FF: { min: 0.0, max: 5.0, maxDelta: 0.5 },
  // Pitch
  PTCH2SRV_P: { min: 0.01, max: 5.0, maxDelta: 0.5 },
  PTCH2SRV_I: { min: 0.01, max: 5.0, maxDelta: 0.5 },
  PTCH2SRV_D: { min: 0.0, max: 5.0, maxDelta: 0.5 },
  PTCH2SRV_IMAX: { min: 0, max: 4500, maxDelta: 500 },
  PTCH2SRV_FF: { min: 0.0, max: 5.0, maxDelta: 0.5 },
  // Yaw
  YAW2SRV_RLL: { min: 0.01, max: 5.0, maxDelta: 0.5 },
  YAW2SRV_INT: { min: 0.01, max: 5.0, maxDelta: 0.5 },
  YAW2SRV_DAMP: { min: 0.0, max: 5.0, maxDelta: 0.5 },
  YAW2SRV_IMAX: { min: 0, max: 4500, maxDelta: 500 },
};

/** Filter parameter safe ranges (shared across vehicle types). */
const FILTER_RANGES: Record<string, ParamSafetyRange> = {
  INS_GYRO_FILTER: { min: 10, max: 256, maxDelta: 20 },
  INS_ACCEL_FILTER: { min: 10, max: 256, maxDelta: 20 },
  INS_HNTCH_FREQ: { min: 10, max: 400, maxDelta: 50 },
  INS_HNTCH_BW: { min: 5, max: 200, maxDelta: 25 },
  INS_HNTC2_FREQ: { min: 10, max: 400, maxDelta: 50 },
  INS_HNTC2_BW: { min: 5, max: 200, maxDelta: 25 },
};

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Get the safety range for a PID or filter parameter.
 *
 * @param param       Parameter name (e.g., "ATC_RAT_RLL_P")
 * @param vehicleType "copter" or "plane"
 * @returns Safety range, or a permissive default if the param is unknown
 */
export function getSafetyRange(
  param: string,
  vehicleType: VehicleType,
): ParamSafetyRange {
  // Check filter ranges first (vehicle-agnostic)
  const filterRange = FILTER_RANGES[param];
  if (filterRange) return filterRange;

  // Check vehicle-specific ranges
  const vehicleRanges = vehicleType === "copter" ? COPTER_RANGES : PLANE_RANGES;
  const range = vehicleRanges[param];
  if (range) return range;

  // Default: permissive range for unknown params
  return { min: 0, max: 10000, maxDelta: 1000 };
}

/**
 * Validate a parameter suggestion against safety constraints.
 *
 * Checks:
 *   1. Suggested value is within safe range
 *   2. Delta from current value doesn't exceed max delta
 *
 * @returns Object with validation result, clamped value, and optional warning
 */
export function validateSuggestion(
  param: string,
  currentValue: number,
  suggestedValue: number,
  vehicleType: VehicleType,
): { valid: boolean; clampedValue: number; warning?: string } {
  const range = getSafetyRange(param, vehicleType);

  let clamped = suggestedValue;
  let warning: string | undefined;
  let valid = true;

  // Clamp to safe range
  if (clamped < range.min) {
    warning = `${param}: ${suggestedValue} below minimum ${range.min}, clamped`;
    clamped = range.min;
    valid = false;
  } else if (clamped > range.max) {
    warning = `${param}: ${suggestedValue} above maximum ${range.max}, clamped`;
    clamped = range.max;
    valid = false;
  }

  // Check delta constraint
  const delta = Math.abs(clamped - currentValue);
  if (delta > range.maxDelta) {
    const direction = clamped > currentValue ? 1 : -1;
    clamped = currentValue + direction * range.maxDelta;

    // Re-clamp to range after delta adjustment
    clamped = Math.max(range.min, Math.min(range.max, clamped));

    const deltaWarning = `${param}: change of ${delta.toFixed(4)} exceeds max delta ${range.maxDelta}, limited`;
    warning = warning ? `${warning}; ${deltaWarning}` : deltaWarning;
    valid = false;
  }

  return { valid, clampedValue: clamped, warning };
}
