import { describe, it, expect } from 'vitest';
import { engineFailMask, SIM_PRESETS, SIM_DEFAULTS, type SimConditions } from './sim-test-conditions';

describe('engineFailMask', () => {
  it('is 0 for no failed motors (the old bug: 0 selects nothing)', () => {
    expect(engineFailMask([])).toBe(0);
  });

  it('sets bit0 for motor 1 (this is what the old panel failed to do)', () => {
    expect(engineFailMask([1])).toBe(1);
  });

  it('maps 1-indexed motors to their bit', () => {
    expect(engineFailMask([2])).toBe(0b10);
    expect(engineFailMask([3])).toBe(0b100);
    expect(engineFailMask([8])).toBe(0b1000_0000);
  });

  it('combines multiple motors into one mask', () => {
    expect(engineFailMask([1, 3])).toBe(0b101);
    expect(engineFailMask([1, 2, 3, 4])).toBe(0b1111);
  });

  it('ignores non-positive motor numbers', () => {
    expect(engineFailMask([0, -1, 2])).toBe(0b10);
  });

  it('is order-independent and idempotent on duplicates', () => {
    expect(engineFailMask([3, 1, 3])).toBe(engineFailMask([1, 3]));
  });
});

describe('SIM presets', () => {
  it('the motor-out preset actually engages a motor (mask != 0) and kills its thrust', () => {
    const p = SIM_PRESETS.find((x) => x.id === 'motor-out');
    expect(p).toBeDefined();
    expect(p!.patch.failedMotors && engineFailMask(p!.patch.failedMotors)).toBeGreaterThan(0);
    expect(p!.patch.engineMul).toBe(0);
  });

  it('every preset patch references only known SimConditions fields', () => {
    const keys = new Set(Object.keys(SIM_DEFAULTS) as (keyof SimConditions)[]);
    for (const preset of SIM_PRESETS) {
      for (const k of Object.keys(preset.patch)) {
        expect(keys.has(k as keyof SimConditions), `${preset.id} → ${k}`).toBe(true);
      }
    }
  });

  it('preset ids are unique', () => {
    const ids = SIM_PRESETS.map((p) => p.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
