/**
 * Sensor noise injection. The dynamics integrator stays deterministic and clean;
 * realistic IMU imperfections (white noise + constant bias) are layered on the
 * gyro and accelerometer readings here, just before they are sent to SITL.
 */

import { add, vec3, type Vec3 } from './math/vec3.js';
import type { Rng } from './math/rng.js';
import type { VehicleState } from './types.js';

export interface SensorNoiseConfig {
  /** Gyro white-noise stddev (rad/s). */
  gyroNoise: number;
  /** Accelerometer white-noise stddev (m/s^2). */
  accelNoise: number;
  /** Constant gyro bias (rad/s). */
  gyroBias?: Vec3;
  /** Constant accel bias (m/s^2). */
  accelBias?: Vec3;
}

export const NO_SENSOR_NOISE: SensorNoiseConfig = { gyroNoise: 0, accelNoise: 0 };

function noisy(v: Vec3, stddev: number, bias: Vec3 | undefined, rng: Rng): Vec3 {
  const b = bias ?? vec3(0, 0, 0);
  return add(
    { x: v.x + b.x, y: v.y + b.y, z: v.z + b.z },
    stddev > 0
      ? vec3(stddev * rng.gaussian(), stddev * rng.gaussian(), stddev * rng.gaussian())
      : vec3(0, 0, 0),
  );
}

/** Return a copy of `state` with noise/bias applied to the gyro and accelerometer. */
export function applySensorNoise(state: VehicleState, cfg: SensorNoiseConfig, rng: Rng): VehicleState {
  return {
    ...state,
    angularVelocity: noisy(state.angularVelocity, cfg.gyroNoise, cfg.gyroBias, rng),
    accelBody: noisy(state.accelBody, cfg.accelNoise, cfg.accelBias, rng),
  };
}
