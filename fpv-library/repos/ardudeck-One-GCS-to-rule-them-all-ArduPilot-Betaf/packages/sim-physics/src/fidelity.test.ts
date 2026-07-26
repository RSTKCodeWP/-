import { describe, it, expect } from 'vitest';
import { makeRng } from './math/rng.js';
import { initBattery, updateBattery, type BatteryConfig } from './battery.js';
import { initWind, updateWind, type WindConfig } from './environment/wind.js';
import { applySensorNoise, NO_SENSOR_NOISE } from './sensors.js';
import { initialState, stepCopter } from './copter.js';
import { DEFAULT_ENVIRONMENT, type MultirotorParams } from './types.js';

describe('rng', () => {
  it('is deterministic for a given seed', () => {
    const a = makeRng(42);
    const b = makeRng(42);
    for (let i = 0; i < 100; i++) expect(a.next()).toBe(b.next());
  });

  it('gaussian has ~zero mean over many samples', () => {
    const r = makeRng(7);
    let sum = 0;
    const n = 20000;
    for (let i = 0; i < n; i++) sum += r.gaussian();
    expect(Math.abs(sum / n)).toBeLessThan(0.05);
  });
});

describe('battery', () => {
  const cfg: BatteryConfig = {
    maxVoltage: 50.4, refVoltage: 46.9, capacityAh: 44,
    internalResistance: 0.024, hoverCurrent: 65, hoverThrust: 32.5 * 9.80665,
  };

  it('sags under load below open-circuit voltage', () => {
    const s = initBattery(cfg);
    const r = updateBattery(cfg, s, cfg.hoverThrust, 0.01);
    expect(r.voltage).toBeLessThan(cfg.maxVoltage);
    expect(r.voltage).toBeGreaterThan(40);
  });

  it('drains state of charge over time under load', () => {
    let s = initBattery(cfg);
    for (let i = 0; i < 1000; i++) s = updateBattery(cfg, s, cfg.hoverThrust, 0.1).state;
    expect(s.remainingAh).toBeLessThan(cfg.capacityAh);
  });

  it('an infinite pack never drains', () => {
    const inf = { ...cfg, capacityAh: 0 };
    let s = initBattery(inf);
    for (let i = 0; i < 100; i++) s = updateBattery(inf, s, inf.hoverThrust, 1).state;
    expect(s.voltage).toBeCloseTo(inf.maxVoltage - inf.hoverCurrent * inf.internalResistance, 3);
  });
});

describe('wind', () => {
  it('returns exactly the steady wind when turbulence is off', () => {
    const cfg: WindConfig = { steady: { x: 5, y: -2, z: 0 }, intensity: 0, timeConstant: 1 };
    const r = updateWind(cfg, initWind(), 0.01, makeRng(1));
    expect(r.wind).toEqual({ x: 5, y: -2, z: 0 });
  });

  it('gust is zero-mean with stddev near the configured intensity', () => {
    const cfg: WindConfig = { steady: { x: 0, y: 0, z: 0 }, intensity: 2, timeConstant: 0.5 };
    let st = initWind();
    const rng = makeRng(123);
    const xs: number[] = [];
    for (let i = 0; i < 50000; i++) {
      const r = updateWind(cfg, st, 0.02, rng);
      st = r.state;
      xs.push(r.wind.x);
    }
    const mean = xs.reduce((a, b) => a + b, 0) / xs.length;
    const variance = xs.reduce((a, b) => a + (b - mean) ** 2, 0) / xs.length;
    expect(Math.abs(mean)).toBeLessThan(0.1);
    expect(Math.sqrt(variance)).toBeGreaterThan(1.5);
    expect(Math.sqrt(variance)).toBeLessThan(2.5);
  });
});

describe('sensor noise', () => {
  it('leaves readings untouched with no noise', () => {
    const s = { ...initialState(), angularVelocity: { x: 1, y: 2, z: 3 }, accelBody: { x: 0, y: 0, z: -9.8 } };
    const out = applySensorNoise(s, NO_SENSOR_NOISE, makeRng(1));
    expect(out.angularVelocity).toEqual(s.angularVelocity);
    expect(out.accelBody).toEqual(s.accelBody);
  });

  it('applies a constant bias exactly when noise is zero', () => {
    const s = { ...initialState(), angularVelocity: { x: 0, y: 0, z: 0 } };
    const out = applySensorNoise(s, { gyroNoise: 0, accelNoise: 0, gyroBias: { x: 0.1, y: 0, z: 0 } }, makeRng(1));
    expect(out.angularVelocity.x).toBeCloseTo(0.1, 9);
  });
});

describe('ground effect', () => {
  const params: MultirotorParams = {
    mass: 1.5, diagonalSize: 0.4, numMotors: 4, hoverThrOut: 0.39, propExpo: 0.65,
    pwmMin: 1000, pwmMax: 2000, spinMin: 0.15, spinMax: 0.95, dragCoef: 0.15, yawTorqueCoef: 0.02,
  };
  const hover = params.pwmMin + params.hoverThrOut * (params.pwmMax - params.pwmMin);

  it('adds lift near the ground at the same throttle', () => {
    const low = { ...initialState(), position: { x: 0, y: 0, z: -0.1 } };
    const pwm = [hover, hover, hover, hover];
    const withGE = stepCopter(pwm, low, params, DEFAULT_ENVIRONMENT, 0.01, { groundEffect: true }).state;
    const without = stepCopter(pwm, low, params, DEFAULT_ENVIRONMENT, 0.01, { groundEffect: false }).state;
    // More lift => more upward (more negative NED z) velocity.
    expect(withGE.velocity.z).toBeLessThan(without.velocity.z);
  });
});
