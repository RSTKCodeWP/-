import { describe, it, expect } from 'vitest';
import { frameGeometry } from './frame-geometry.js';

describe('frame geometry', () => {
  it.each([
    [4, 0.4],
    [6, 0.65],
    [8, 1.325],
  ])('places %i motors on the arm-radius circle', (n, diag) => {
    const mounts = frameGeometry(n, diag);
    expect(mounts).toHaveLength(n);
    const r = diag / 2;
    for (const m of mounts) {
      const radius = Math.sqrt(m.position.x ** 2 + m.position.y ** 2);
      expect(radius).toBeCloseTo(r, 6);
      expect(m.position.z).toBe(0);
    }
  });

  it.each([[4], [6], [8]])('has balanced yaw factors (sum 0) for %i motors', (n) => {
    const mounts = frameGeometry(n, 1);
    const yawSum = mounts.reduce((a, m) => a + m.yawFactor, 0);
    expect(yawSum).toBe(0);
  });

  it.each([[4], [6], [8]])('is geometrically centered (positions sum ~0) for %i motors', (n) => {
    const mounts = frameGeometry(n, 1);
    const sx = mounts.reduce((a, m) => a + m.position.x, 0);
    const sy = mounts.reduce((a, m) => a + m.position.y, 0);
    expect(Math.abs(sx)).toBeLessThan(1e-9);
    expect(Math.abs(sy)).toBeLessThan(1e-9);
  });
});
