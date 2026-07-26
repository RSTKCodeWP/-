/**
 * Maps SITL motor PWM outputs to per-motor thrust.
 *
 * SITL sends the firmware's actual servo outputs (microseconds), already scaled
 * through the firmware mixer's spin range, so we map PWM linearly to a 0-1
 * throttle and run it through a propeller curve. Per-motor max thrust is
 * calibrated so that all motors at `hoverThrOut` produce exactly weight (m*g) -
 * this makes hover an exact equilibrium regardless of frame.
 */

import type { MultirotorParams } from './types.js';

/** PWM microseconds -> normalized throttle in [0,1]. */
export function normalizedThrottle(pwm: number, params: MultirotorParams): number {
  const span = params.pwmMax - params.pwmMin;
  if (span <= 0) return 0;
  const t = (pwm - params.pwmMin) / span;
  return Math.max(0, Math.min(1, t));
}

/** Propeller thrust curve: blend of linear and quadratic by propExpo. f(0)=0, f(1)=1. */
export function thrustFactor(throttle: number, propExpo: number): number {
  const t = Math.max(0, Math.min(1, throttle));
  const e = Math.max(0, Math.min(1, propExpo));
  return (1 - e) * t + e * t * t;
}

/**
 * Per-motor maximum thrust (N), calibrated so N motors at `hoverThrOut` sum to
 * exactly m*g. Falls back gracefully if hoverThrOut is degenerate.
 */
export function maxThrustPerMotor(params: MultirotorParams, gravity: number): number {
  const weight = params.mass * gravity;
  const hf = thrustFactor(params.hoverThrOut, params.propExpo);
  const denom = params.numMotors * hf;
  if (denom <= 1e-9) {
    // Degenerate hover throttle; assume a 2:1 thrust-to-weight at full throttle.
    return (2 * weight) / Math.max(1, params.numMotors);
  }
  return weight / denom;
}

/**
 * Thrust (N) for each motor given the SITL PWM array. `voltageScale` lets later
 * phases fold in battery sag (thrust ~ V^2); Phase 1 passes 1.
 */
export function motorThrusts(
  pwms: number[],
  params: MultirotorParams,
  gravity: number,
  voltageScale = 1,
): number[] {
  const tMax = maxThrustPerMotor(params, gravity);
  const out: number[] = [];
  for (let i = 0; i < params.numMotors; i++) {
    const pwm = pwms[i] ?? params.pwmMin;
    const throttle = normalizedThrottle(pwm, params);
    out.push(tMax * thrustFactor(throttle, params.propExpo) * voltageScale);
  }
  return out;
}
