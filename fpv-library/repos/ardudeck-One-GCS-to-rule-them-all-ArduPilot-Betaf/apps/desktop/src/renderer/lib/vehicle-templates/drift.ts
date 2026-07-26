import type { VehicleProfile } from '../../stores/settings-store.js';
import { getTemplate, defaultTemplateForType } from './registry.js';

export interface DriftEntry {
  name: string;
  currentValue: number;
  expectedValue: number;
  reason: string;
}

function coerceValueForParam(value: number, type: number | undefined): number {
  if (type !== undefined && type >= 1 && type <= 8) return Math.round(value);
  return value;
}

export interface DriftReport {
  /** True when the profile was never applied — drift is undefined. */
  notApplied: boolean;
  diverged: DriftEntry[];
}

/**
 * Compare the currently-loaded param cache against what the profile's template
 * would produce. Used to light up the "Drifted — N params" badge.
 *
 * `includeSim` mirrors what's actually written to the target (SIM_* only for
 * SITL). This way drift detection stays honest about what the user applied.
 */
export function computeDrift(args: {
  profile: VehicleProfile;
  /** Cache can carry param type so drift coerces target the same way apply does. */
  currentParams: Map<string, { value: number; type?: number }>;
  includeSim: boolean;
  epsilon?: number;
}): DriftReport {
  const eps = args.epsilon ?? 1e-4;

  if (!args.profile.lastAppliedAt) {
    return { notApplied: true, diverged: [] };
  }
  const template = getTemplate(args.profile.templateSlug) ?? defaultTemplateForType(args.profile.type);
  const specs = [
    ...template.toParams(args.profile),
    ...(args.includeSim ? template.toSimParams(args.profile) : []),
  ];

  const diverged: DriftEntry[] = [];
  for (const spec of specs) {
    const current = args.currentParams.get(spec.name);
    if (!current) continue;                  // param not on firmware — not drift
    const expected = coerceValueForParam(spec.value, current.type);
    if (Math.abs(current.value - expected) < eps) continue;
    diverged.push({
      name: spec.name,
      currentValue: current.value,
      expectedValue: expected,
      reason: spec.reason,
    });
  }
  return { notApplied: false, diverged };
}
