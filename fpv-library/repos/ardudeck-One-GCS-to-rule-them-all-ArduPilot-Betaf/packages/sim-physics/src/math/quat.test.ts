import { describe, it, expect } from 'vitest';
import {
  fromEuler,
  integrateQuat,
  normalizeQuat,
  rotateBodyToWorld,
  toEuler,
} from './quat.js';

const close = (a: number, b: number, eps = 1e-6) => Math.abs(a - b) < eps;

describe('quaternion', () => {
  it('identity rotation leaves a vector unchanged', () => {
    const v = rotateBodyToWorld({ w: 1, x: 0, y: 0, z: 0 }, { x: 1, y: 2, z: 3 });
    expect(close(v.x, 1)).toBe(true);
    expect(close(v.y, 2)).toBe(true);
    expect(close(v.z, 3)).toBe(true);
  });

  it('90deg yaw maps body-forward (+x) to world-east (+y)', () => {
    const q = fromEuler(0, 0, Math.PI / 2); // yaw +90
    const v = rotateBodyToWorld(q, { x: 1, y: 0, z: 0 });
    expect(close(v.x, 0, 1e-6)).toBe(true);
    expect(close(v.y, 1, 1e-6)).toBe(true);
    expect(close(v.z, 0, 1e-6)).toBe(true);
  });

  it('euler round-trips through quaternion', () => {
    const e = toEuler(fromEuler(0.3, -0.2, 1.1));
    expect(close(e.roll, 0.3, 1e-6)).toBe(true);
    expect(close(e.pitch, -0.2, 1e-6)).toBe(true);
    expect(close(e.yaw, 1.1, 1e-6)).toBe(true);
  });

  it('integration keeps the quaternion unit-normalized', () => {
    let q = { w: 1, x: 0, y: 0, z: 0 };
    for (let i = 0; i < 1000; i++) {
      q = integrateQuat(q, { x: 0.5, y: -0.3, z: 0.8 }, 0.0025);
    }
    const n = Math.sqrt(q.w * q.w + q.x * q.x + q.y * q.y + q.z * q.z);
    expect(close(n, 1, 1e-9)).toBe(true);
  });

  it('normalizeQuat falls back to identity for a zero quaternion', () => {
    const q = normalizeQuat({ w: 0, x: 0, y: 0, z: 0 });
    expect(q).toEqual({ w: 1, x: 0, y: 0, z: 0 });
  });
});
