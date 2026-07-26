// presets/resolve.ts — Resolve a build preset to sim_vehicle.py CLI args
// SPDX-License-Identifier: GPL-3.0-only

import { getPreset, listPresetIds } from './presets.js';
import type { BuildPreset } from './types.js';

export interface ResolvedPreset {
  /** The preset that was resolved. */
  preset: BuildPreset;
  /** Extra args to append to the sim_vehicle.py invocation. */
  extraArgs: string[];
  /** Vehicle type override (may differ from CLI default). */
  vehicle: string;
}

/**
 * Resolve a preset ID to sim_vehicle.py extra arguments.
 * Throws with a helpful message if the preset ID is invalid.
 */
export function resolvePreset(presetId: string): ResolvedPreset {
  const preset = getPreset(presetId);
  if (!preset) {
    const ids = listPresetIds();
    throw new Error(
      `Unknown preset "${presetId}". Available presets:\n` +
      ids.map((id) => `  - ${id}`).join('\n'),
    );
  }

  const extraArgs: string[] = [];

  // Frame type flag
  extraArgs.push('-f', preset.sitl.frame);

  // Parameter overrides as individual -P flags
  for (const [key, value] of Object.entries(preset.sitl.paramOverrides)) {
    extraArgs.push('-P', `${key}=${value}`);
  }

  return {
    preset,
    extraArgs,
    vehicle: preset.sitl.vehicle,
  };
}
