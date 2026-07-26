import type { VehicleProfile } from '../../stores/settings-store.js';
import type { VehicleTemplate, ProfileDiffResult } from './types.js';
import type { ParameterWithMeta } from '../../../shared/parameter-types.js';

export interface ComputeDiffOptions {
  /** Live param cache from parameter-store. */
  currentParams: Map<string, ParameterWithMeta>;
  /** When true, include SIM_* params from the template. */
  includeSim: boolean;
  /** Optional tolerance when comparing float values. Defaults to 1e-4. */
  epsilon?: number;
  /** Function that tells us whether a param triggers reboot (from parameter-store). */
  isRebootRequired: (paramId: string) => boolean;
}

/**
 * MAV_PARAM_TYPE 1..8 are the integer variants (UINT8/INT8/UINT16/INT16/
 * UINT32/INT32/UINT64/INT64). 9 = REAL32 (float), 10 = REAL64 (double).
 * ArduPilot truncates on PARAM_SET when the param is integer-typed, so we
 * have to coerce the template's target value to the param's live type —
 * otherwise a template emitting 10.4 for an INT32 param would be written
 * as 10 and then instantly flagged as "drifted 0.4".
 */
function coerceValueForParam(value: number, type: number): number {
  if (type >= 1 && type <= 8) return Math.round(value);
  return value;
}

/**
 * Compute the delta between a vehicle profile (+its template) and the live
 * param cache. Returns exactly what the compare modal needs plus diagnostic
 * lists for params we skipped (unknown to firmware) or didn't need to touch.
 */
export function computeProfileDiff(
  profile: VehicleProfile,
  template: VehicleTemplate,
  opts: ComputeDiffOptions,
): ProfileDiffResult {
  const eps = opts.epsilon ?? 1e-4;
  const specs = [
    ...template.toParams(profile),
    ...(opts.includeSim ? template.toSimParams(profile) : []),
  ];

  const changes: ProfileDiffResult['changes'] = [];
  const unknownParams: ProfileDiffResult['unknownParams'] = [];
  const unchangedParams: ProfileDiffResult['unchangedParams'] = [];

  for (const spec of specs) {
    const existing = opts.currentParams.get(spec.name);
    if (!existing) {
      unknownParams.push({ name: spec.name, targetValue: spec.value, reason: spec.reason });
      continue;
    }
    // Coerce the target to match the live param's type. This prevents
    // phantom drift on integer-typed params where the template emits a float.
    const targetValue = coerceValueForParam(spec.value, existing.type);
    if (Math.abs(existing.value - targetValue) < eps) {
      unchangedParams.push({ name: spec.name, value: existing.value });
      continue;
    }
    changes.push({
      name: spec.name,
      currentValue: existing.value,
      targetValue,
      type: existing.type,
      reason: spec.reason,
      requiresReboot: spec.requiresReboot ?? opts.isRebootRequired(spec.name),
    });
  }

  return { changes, unknownParams, unchangedParams };
}
