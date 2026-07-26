import { describe, it, expect } from 'vitest';
import { computeProfileDiff } from '../compute-diff';
import { getTemplate } from '../registry';
import type { VehicleProfile } from '../../../stores/settings-store';
import type { ParameterWithMeta } from '../../../../shared/parameter-types';

function mkParam(name: string, value: number): [string, ParameterWithMeta] {
  return [name, {
    id: name, value, type: 9, index: 0, isReadOnly: false, isModified: false,
  } as ParameterWithMeta];
}

describe('computeProfileDiff', () => {
  const tpl = getTemplate('copter-quad-x')!;
  const profile: VehicleProfile = {
    id: 'p', name: 'q', type: 'copter',
    weight: 600, batteryCells: 4, batteryCapacity: 3000,
    templateSlug: 'copter-quad-x',
  };

  it('reports a change when live value differs', () => {
    const cache = new Map<string, ParameterWithMeta>([
      mkParam('FRAME_CLASS', 2),  // current hex, target quad
      mkParam('FRAME_TYPE', 1),
      mkParam('BATT_CAPACITY', 3000),
      mkParam('BATT_LOW_VOLT', 14.0),
      mkParam('BATT_CRT_VOLT', 13.2),
      mkParam('BATT_MONITOR', 4),
      mkParam('ARMING_CHECK', 1),
    ]);
    const diff = computeProfileDiff(profile, tpl, {
      currentParams: cache,
      includeSim: false,
      isRebootRequired: (n) => n.startsWith('FRAME_'),
    });
    expect(diff.changes.find(c => c.name === 'FRAME_CLASS')).toBeDefined();
    expect(diff.changes.find(c => c.name === 'FRAME_CLASS')?.requiresReboot).toBe(true);
  });

  it('classifies unchanged params', () => {
    const cache = new Map<string, ParameterWithMeta>([
      mkParam('FRAME_CLASS', 1),  // already matches quad
      mkParam('FRAME_TYPE', 1),
      mkParam('BATT_CAPACITY', 3000),
      mkParam('BATT_LOW_VOLT', 14.0),
      mkParam('BATT_CRT_VOLT', 13.2),
      mkParam('BATT_MONITOR', 4),
      mkParam('ARMING_CHECK', 1),
    ]);
    const diff = computeProfileDiff(profile, tpl, {
      currentParams: cache,
      includeSim: false,
      isRebootRequired: () => false,
    });
    expect(diff.changes.length).toBe(0);
    expect(diff.unchangedParams.find(u => u.name === 'FRAME_CLASS')).toBeDefined();
  });

  it('lists unknown params (firmware doesn\'t expose them)', () => {
    const cache = new Map<string, ParameterWithMeta>([
      mkParam('FRAME_CLASS', 2),
      // BATT_* intentionally missing
    ]);
    const diff = computeProfileDiff(profile, tpl, {
      currentParams: cache,
      includeSim: false,
      isRebootRequired: () => false,
    });
    const unknownNames = diff.unknownParams.map(u => u.name);
    expect(unknownNames).toContain('BATT_CAPACITY');
  });

  it('includes SIM_* params when includeSim is true', () => {
    const cache = new Map<string, ParameterWithMeta>([
      mkParam('FRAME_CLASS', 1),
      mkParam('FRAME_TYPE', 1),
      mkParam('SIM_BATT_VOLTAGE', 0),
      mkParam('SIM_BATT_CAP_AH', 0),
    ]);
    const diff = computeProfileDiff(profile, tpl, {
      currentParams: cache,
      includeSim: true,
      isRebootRequired: () => false,
    });
    const names = new Set(diff.changes.map(c => c.name));
    expect(names.has('SIM_BATT_VOLTAGE')).toBe(true);
  });
});
