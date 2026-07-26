import { describe, it, expect } from 'vitest';
import { computeDrift } from '../drift';
import type { VehicleProfile } from '../../../stores/settings-store';

describe('computeDrift', () => {
  const applied: VehicleProfile = {
    id: 'p', name: 'q', type: 'copter',
    weight: 600, batteryCells: 4, batteryCapacity: 3000,
    templateSlug: 'copter-quad-x',
    lastAppliedAt: new Date().toISOString(),
  };

  it('reports "notApplied" when lastAppliedAt is missing', () => {
    const never: VehicleProfile = { ...applied, lastAppliedAt: undefined };
    const r = computeDrift({
      profile: never,
      currentParams: new Map(),
      includeSim: false,
    });
    expect(r.notApplied).toBe(true);
    expect(r.diverged).toEqual([]);
  });

  it('detects diverged params', () => {
    const r = computeDrift({
      profile: applied,
      currentParams: new Map([
        ['FRAME_CLASS', { value: 2 }],   // diverged: template wants 1
        ['FRAME_TYPE', { value: 1 }],    // matches
      ]),
      includeSim: false,
    });
    expect(r.diverged.find(d => d.name === 'FRAME_CLASS')).toBeDefined();
    expect(r.diverged.find(d => d.name === 'FRAME_TYPE')).toBeUndefined();
  });

  it('skips params absent from cache', () => {
    const r = computeDrift({
      profile: applied,
      currentParams: new Map(),
      includeSim: false,
    });
    expect(r.diverged).toEqual([]);
  });
});
