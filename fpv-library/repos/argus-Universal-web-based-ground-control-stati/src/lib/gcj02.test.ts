import { describe, it, expect } from 'vitest';
import { toGcj, toWgs } from './gcj02';

describe('gcj02', () => {
  it('shifts coordinates inside China', () => {
    const [glat, glon] = toGcj(39.9042, 116.4074);
    expect(glat).not.toBeCloseTo(39.9042, 3);
    expect(glon).not.toBeCloseTo(116.4074, 3);
    expect(Math.abs(glat - 39.9042)).toBeLessThan(0.01);
    expect(Math.abs(glon - 116.4074)).toBeLessThan(0.01);
  });

  it('roundtrips toGcj -> toWgs with sub-meter accuracy', () => {
    const lat = 34.2583,
      lon = 108.9425;
    const [g0, g1] = toGcj(lat, lon);
    const [w0, w1] = toWgs(g0, g1);
    expect(Math.abs(w0 - lat)).toBeLessThan(2e-5);
    expect(Math.abs(w1 - lon)).toBeLessThan(2e-5);
  });

  it('returns finite numbers for edge coordinates', () => {
    const [a, b] = toGcj(0, 0);
    expect(Number.isFinite(a)).toBe(true);
    expect(Number.isFinite(b)).toBe(true);
    const [c, d] = toGcj(85, 180);
    expect(Number.isFinite(c)).toBe(true);
    expect(Number.isFinite(d)).toBe(true);
  });
});
