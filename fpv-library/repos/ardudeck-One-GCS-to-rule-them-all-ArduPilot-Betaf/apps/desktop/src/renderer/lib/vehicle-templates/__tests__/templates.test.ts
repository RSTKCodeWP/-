import { describe, it, expect } from 'vitest';
import { VEHICLE_TEMPLATES, getTemplate, defaultTemplateForType } from '../registry';
import type { VehicleProfile } from '../../../stores/settings-store';

function profile(overrides: Partial<VehicleProfile> = {}): VehicleProfile {
  return {
    id: 'p1',
    name: 'Test',
    type: 'copter',
    weight: 600,
    batteryCells: 4,
    batteryCapacity: 3000,
    ...overrides,
  } as VehicleProfile;
}

describe('vehicle-templates registry', () => {
  it('has 27 templates with unique slugs', () => {
    expect(VEHICLE_TEMPLATES.length).toBe(27);
    const slugs = new Set(VEHICLE_TEMPLATES.map(t => t.slug));
    expect(slugs.size).toBe(VEHICLE_TEMPLATES.length);
  });

  it('every template emits at least one core param', () => {
    for (const t of VEHICLE_TEMPLATES) {
      const p = profile({ ...t.defaults, id: 'p', name: t.name, type: t.vehicleType } as VehicleProfile);
      const specs = t.toParams(p);
      expect(specs.length).toBeGreaterThan(0);
    }
  });

  it('every template has a valid fallback for its vehicle type', () => {
    const types: Array<VehicleProfile['type']> = ['copter', 'plane', 'vtol', 'rover', 'boat', 'sub'];
    for (const type of types) {
      const fallback = defaultTemplateForType(type);
      expect(fallback.vehicleType).toBe(type);
    }
  });

  it('getTemplate returns undefined for unknown slug', () => {
    expect(getTemplate('not-a-real-slug')).toBeUndefined();
    expect(getTemplate(undefined)).toBeUndefined();
  });
});

describe('showcase: Tailsitter Delta Duo', () => {
  const tpl = getTemplate('vtol-tailsitter-delta-duo')!;

  it('emits tailsitter-specific params', () => {
    const p = profile({
      type: 'vtol',
      ...tpl.defaults,
      id: 'p',
      name: 'duo',
    } as VehicleProfile);
    const specs = tpl.toParams(p);
    const names = new Set(specs.map(s => s.name));
    expect(names.has('Q_ENABLE')).toBe(true);
    expect(names.has('Q_TAILSIT_ENABLE')).toBe(true);
    expect(names.has('Q_FRAME_CLASS')).toBe(true);
    expect(names.has('SERVO1_FUNCTION')).toBe(true);   // elevon L
    expect(names.has('SERVO2_FUNCTION')).toBe(true);   // elevon R
  });

  it('battery params derive from cells', () => {
    const p = profile({ type: 'vtol', ...tpl.defaults, id: 'p', name: 'd', batteryCells: 6 } as VehicleProfile);
    const specs = tpl.toParams(p);
    const low = specs.find(s => s.name === 'BATT_LOW_VOLT');
    expect(low?.value).toBeCloseTo(6 * 3.5, 2);
  });
});

describe('inferFrom', () => {
  it('picks Tailsitter Delta Duo from tailsitter params', () => {
    const m = new Map<string, number>([
      ['Q_TAILSIT_ENABLE', 1],
      ['Q_FRAME_CLASS', 10],
      ['SERVO1_FUNCTION', 77],
    ]);
    const duo = getTemplate('vtol-tailsitter-delta-duo')!;
    expect(duo.inferFrom(m)).toBe(1);
  });

  it('returns 0 for wildly mismatched params', () => {
    const m = new Map<string, number>([
      ['FRAME_CLASS', 99],
      ['SERVO1_FUNCTION', 0],
    ]);
    const duo = getTemplate('vtol-tailsitter-delta-duo')!;
    expect(duo.inferFrom(m)).toBe(0);
  });
});
