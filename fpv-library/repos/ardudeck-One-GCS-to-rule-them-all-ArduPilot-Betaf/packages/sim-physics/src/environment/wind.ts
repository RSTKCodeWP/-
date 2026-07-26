/**
 * Wind model: a steady mean wind plus a stationary turbulence gust driven by a
 * first-order Gauss-Markov process (a discrete Dryden-style approximation). The
 * gust has zero mean and standard deviation ~ `intensity`, correlated over
 * `timeConstant` seconds.
 */

import { add, scale, vec3, type Vec3 } from '../math/vec3.js';
import type { Rng } from '../math/rng.js';

export interface WindConfig {
  /** Steady wind in NED m/s. */
  steady: Vec3;
  /** Turbulence standard deviation (m/s). 0 disables gusts. */
  intensity: number;
  /** Correlation time of the gust (s). */
  timeConstant: number;
}

export interface WindState {
  gust: Vec3;
}

export function initWind(): WindState {
  return { gust: vec3(0, 0, 0) };
}

export const CALM_WIND: WindConfig = { steady: { x: 0, y: 0, z: 0 }, intensity: 0, timeConstant: 1 };

/** Advance the gust and return the total wind vector (steady + gust) in NED. */
export function updateWind(
  cfg: WindConfig,
  state: WindState,
  dt: number,
  rng: Rng,
): { state: WindState; wind: Vec3 } {
  if (cfg.intensity <= 0) {
    return { state: { gust: vec3(0, 0, 0) }, wind: { ...cfg.steady } };
  }
  const tau = Math.max(1e-3, cfg.timeConstant);
  const alpha = Math.exp(-dt / tau);
  const beta = Math.sqrt(1 - alpha * alpha) * cfg.intensity;
  const gust = vec3(
    alpha * state.gust.x + beta * rng.gaussian(),
    alpha * state.gust.y + beta * rng.gaussian(),
    alpha * state.gust.z + beta * rng.gaussian(),
  );
  return { state: { gust }, wind: add(cfg.steady, gust) };
}

export { scale };
