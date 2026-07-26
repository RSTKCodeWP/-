import { describe, it, expect } from 'vitest';
import { initialState, stepCopter } from './copter.js';
import { DEFAULT_ENVIRONMENT, type MultirotorParams, type VehicleState } from './types.js';

const params: MultirotorParams = {
  mass: 1.5,
  diagonalSize: 0.4,
  numMotors: 4,
  hoverThrOut: 0.39,
  propExpo: 0.65,
  pwmMin: 1000,
  pwmMax: 2000,
  spinMin: 0.15,
  spinMax: 0.95,
  dragCoef: 0.15,
  yawTorqueCoef: 0.02,
};

const G = DEFAULT_ENVIRONMENT.gravity;
const DT = 1 / 400;
const HOVER_PWM = params.pwmMin + params.hoverThrOut * (params.pwmMax - params.pwmMin); // 1390

function run(pwms: number[], start: VehicleState, steps: number): VehicleState {
  let s = start;
  for (let i = 0; i < steps; i++) s = stepCopter(pwms, s, params, DEFAULT_ENVIRONMENT, DT).state;
  return s;
}

describe('copter dynamics', () => {
  it('rests on the ground at idle and reads ~1g on the accelerometer', () => {
    const idle = [params.pwmMin, params.pwmMin, params.pwmMin, params.pwmMin];
    const s = run(idle, initialState(), 400);
    expect(s.position.z).toBeCloseTo(0, 3); // does not sink through ground
    expect(s.velocity.z).toBeCloseTo(0, 3);
    expect(s.accelBody.z).toBeCloseTo(-G, 2); // accelerometer reads gravity
  });

  it('holds altitude at the hover throttle (equilibrium)', () => {
    const airborne: VehicleState = { ...initialState(), position: { x: 0, y: 0, z: -10 } };
    const s = run([HOVER_PWM, HOVER_PWM, HOVER_PWM, HOVER_PWM], airborne, 2000);
    expect(s.position.z).toBeCloseTo(-10, 2); // altitude unchanged
    expect(s.velocity.z).toBeCloseTo(0, 3);
    expect(s.accelBody.z).toBeCloseTo(-G, 3); // hovering also reads 1g
  });

  it('climbs when throttle exceeds hover', () => {
    const s = run([1700, 1700, 1700, 1700], initialState(), 200);
    expect(s.position.z).toBeLessThan(-0.5); // altitude (= -z) increased
    expect(s.velocity.z).toBeLessThan(0);
  });

  it('yaws nose-right (+z) when CCW motors are increased', () => {
    // QuadX: idx0,idx1 = CCW; idx2,idx3 = CW. Raise CCW, lower CW.
    const s = stepCopter([1450, 1450, 1330, 1330], initialState(), params, DEFAULT_ENVIRONMENT, DT).state;
    expect(s.angularVelocity.z).toBeGreaterThan(0);
    // Pure yaw: negligible roll/pitch rate.
    expect(Math.abs(s.angularVelocity.x)).toBeLessThan(1e-6);
    expect(Math.abs(s.angularVelocity.y)).toBeLessThan(1e-6);
  });

  it('rolls right (+x) when the left-side motors are increased', () => {
    // Left motors (y<0) are idx1 (back-left) and idx2 (front-left).
    const s = stepCopter([1330, 1450, 1450, 1330], initialState(), params, DEFAULT_ENVIRONMENT, DT).state;
    expect(s.angularVelocity.x).toBeGreaterThan(0);
    expect(Math.abs(s.angularVelocity.y)).toBeLessThan(1e-6); // no pitch coupling
  });

  it('stays finite over a long hover run', () => {
    const s = run([HOVER_PWM, HOVER_PWM, HOVER_PWM, HOVER_PWM], { ...initialState(), position: { x: 0, y: 0, z: -50 } }, 5000);
    for (const v of [s.position, s.velocity, s.angularVelocity, s.accelBody]) {
      expect(Number.isFinite(v.x) && Number.isFinite(v.y) && Number.isFinite(v.z)).toBe(true);
    }
  });
});
