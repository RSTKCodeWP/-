import { describe, it, expect } from 'vitest';
import { inferProfileFromParams } from '../import';
import { exportParm } from '../export-parm';
import { getTemplate } from '../registry';
import type { VehicleProfile } from '../../../stores/settings-store';

describe('inferProfileFromParams', () => {
  it('finds the Tailsitter Delta Duo template from its signature params', () => {
    const map = new Map<string, number>([
      ['Q_TAILSIT_ENABLE', 1],
      ['Q_FRAME_CLASS', 10],
      ['SERVO1_FUNCTION', 77],
      ['BATT_LOW_VOLT', 14.0],
      ['BATT_CAPACITY', 3000],
    ]);
    const r = inferProfileFromParams(map);
    expect(r).not.toBeNull();
    expect(r!.template.slug).toBe('vtol-tailsitter-delta-duo');
    expect(r!.profile.batteryCells).toBe(4);              // 14.0 / 3.5
    expect(r!.profile.batteryCapacity).toBe(3000);
    expect(r!.autoFilled.has('batteryCells')).toBe(true);
  });

  it('returns null for totally unrelated params', () => {
    const map = new Map<string, number>([['UNKNOWN_PARAM', 42]]);
    expect(inferProfileFromParams(map)).toBeNull();
  });
});

describe('exportParm round-trip', () => {
  it('produces standard ArduPilot .parm format', () => {
    const profile: VehicleProfile = {
      id: 'p', name: 'Duo Test', type: 'vtol',
      weight: 800, batteryCells: 4, batteryCapacity: 3000,
      templateSlug: 'vtol-tailsitter-delta-duo',
    };
    const tpl = getTemplate('vtol-tailsitter-delta-duo')!;
    const text = exportParm(profile, tpl, { includeSim: false });
    expect(text.startsWith('#')).toBe(true);
    expect(text).toContain('Q_TAILSIT_ENABLE,1');
    expect(text).toContain('Q_FRAME_CLASS,10');
    expect(text).toContain('SERVO1_FUNCTION,77');
  });

  it('includes SIM_* only when includeSim is true', () => {
    const profile: VehicleProfile = {
      id: 'p', name: 'q', type: 'copter',
      weight: 600, batteryCells: 4, batteryCapacity: 3000,
      templateSlug: 'copter-quad-x',
    };
    const tpl = getTemplate('copter-quad-x')!;
    const coreOnly = exportParm(profile, tpl, { includeSim: false });
    const withSim  = exportParm(profile, tpl, { includeSim: true });
    expect(coreOnly).not.toContain('SIM_BATT_VOLTAGE');
    expect(withSim).toContain('SIM_BATT_VOLTAGE');
  });
});
