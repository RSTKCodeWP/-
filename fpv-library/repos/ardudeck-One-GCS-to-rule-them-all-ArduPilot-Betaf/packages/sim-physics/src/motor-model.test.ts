import { describe, it, expect } from 'vitest';
import {
  maxThrustPerMotor,
  motorThrusts,
  normalizedThrottle,
  thrustFactor,
} from './motor-model.js';
import type { MultirotorParams } from './types.js';

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

const G = 9.80665;

describe('motor model', () => {
  it('clamps normalized throttle to [0,1]', () => {
    expect(normalizedThrottle(500, params)).toBe(0);
    expect(normalizedThrottle(2500, params)).toBe(1);
    expect(normalizedThrottle(1500, params)).toBeCloseTo(0.5, 6);
  });

  it('thrust factor passes through endpoints', () => {
    expect(thrustFactor(0, 0.5)).toBe(0);
    expect(thrustFactor(1, 0.5)).toBeCloseTo(1, 6);
  });

  it('calibrates so all motors at hover throttle sum to weight', () => {
    const hoverPwm = params.pwmMin + params.hoverThrOut * (params.pwmMax - params.pwmMin);
    const thrusts = motorThrusts([hoverPwm, hoverPwm, hoverPwm, hoverPwm], params, G);
    const total = thrusts.reduce((a, b) => a + b, 0);
    expect(total).toBeCloseTo(params.mass * G, 4);
  });

  it('per-motor max thrust gives better than 1:1 thrust-to-weight at full', () => {
    const tMax = maxThrustPerMotor(params, G);
    const fullTotal = tMax * params.numMotors;
    expect(fullTotal).toBeGreaterThan(params.mass * G);
  });

  it('missing PWM entries default to idle (zero thrust)', () => {
    const thrusts = motorThrusts([], params, G);
    expect(thrusts).toHaveLength(4);
    expect(thrusts.every((t) => t === 0)).toBe(true);
  });
});
