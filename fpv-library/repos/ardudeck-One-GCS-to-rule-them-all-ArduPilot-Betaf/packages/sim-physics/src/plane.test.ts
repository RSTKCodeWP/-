import { describe, it, expect } from 'vitest';
import { initialPlaneState, stepPlane, type PlaneParams } from './plane.js';
import { DEFAULT_ENVIRONMENT } from './types.js';

const params: PlaneParams = {
  mass: 2.0, wingArea: 0.4, span: 1.5, chord: 0.27,
  cl0: 0.2, clAlpha: 5.0, cd0: 0.03, inducedK: 0.05, maxThrust: 12,
  elevatorEffect: 1.2, aileronEffect: 1.0, rudderEffect: 0.8,
  pitchDamp: 2.0, rollDamp: 1.5, yawDamp: 2.0,
};
const env = DEFAULT_ENVIRONMENT;
const NEUTRAL = [1500, 1500, 1000, 1500]; // ail, elev, thr=0, rud

describe('plane dynamics', () => {
  it('accelerates forward under throttle', () => {
    const s = stepPlane([1500, 1500, 2000, 1500], initialPlaneState(15), params, env, 0.02).state;
    expect(s.velocity.x).toBeGreaterThan(15);
  });

  it('generates upward lift force at positive angle of attack', () => {
    // Pitched up 8deg, flying forward: expect an upward (negative NED z) accel contribution.
    const pitched = { ...initialPlaneState(20), attitude: { w: Math.cos(0.07), x: 0, y: Math.sin(0.07), z: 0 } };
    const s = stepPlane(NEUTRAL, pitched, params, env, 0.001).state;
    // Specific force should have a strong upward (-z body) component from lift.
    expect(s.accelBody.z).toBeLessThan(0);
  });

  it('pitches with elevator deflection', () => {
    const up = stepPlane([1500, 2000, 1500, 1500], initialPlaneState(20), params, env, 0.01).state;
    const down = stepPlane([1500, 1000, 1500, 1500], initialPlaneState(20), params, env, 0.01).state;
    expect(Math.sign(up.angularVelocity.y)).not.toBe(Math.sign(down.angularVelocity.y));
  });

  it('rolls with aileron deflection', () => {
    const s = stepPlane([2000, 1500, 1500, 1500], initialPlaneState(20), params, env, 0.01).state;
    expect(Math.abs(s.angularVelocity.x)).toBeGreaterThan(0);
  });

  it('stays finite over a long run', () => {
    let s = initialPlaneState(18);
    for (let i = 0; i < 5000; i++) s = stepPlane([1500, 1500, 1600, 1500], s, params, env, 0.004).state;
    expect(Number.isFinite(s.position.x) && Number.isFinite(s.velocity.x)).toBe(true);
  });
});
