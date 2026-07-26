import { describe, it, expect } from 'vitest';
import { modelKeyForClass, CLASS_MODEL, FALLBACK_MODEL } from './sim-models';

describe('modelKeyForClass', () => {
  it('maps plane to the plane model', () => {
    expect(modelKeyForClass('plane')).toBe('plane');
  });

  it('maps rover to the rover model', () => {
    expect(modelKeyForClass('rover')).toBe('rover');
  });

  it('falls back to the quad for classes without a dedicated model', () => {
    expect(modelKeyForClass('copter')).toBe(FALLBACK_MODEL);
    expect(modelKeyForClass('vtol')).toBe(FALLBACK_MODEL);
    expect(modelKeyForClass('sub')).toBe(FALLBACK_MODEL);
    expect(FALLBACK_MODEL).toBe('quad');
  });

  it('falls back to the quad for undefined / unknown class', () => {
    expect(modelKeyForClass(undefined)).toBe('quad');
    expect(modelKeyForClass('spaceship')).toBe('quad');
  });

  it('every mapped model key is a real ModelKey the scene can load', () => {
    const known = new Set(['quad', 'plane', 'hexa', 'rover']);
    for (const key of Object.values(CLASS_MODEL)) expect(key && known.has(key)).toBeTruthy();
  });
});
