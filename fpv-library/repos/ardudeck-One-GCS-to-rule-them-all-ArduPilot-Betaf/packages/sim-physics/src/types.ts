/**
 * Core simulator types. Frames follow ArduPilot conventions:
 *  - World frame: NED (x=North, y=East, z=Down). Ground is at z=0; altitude is -z.
 *  - Body frame: FRD (x=Forward, y=Right, z=Down).
 *  - Quaternion rotates body -> world.
 */

import type { Vec3 } from './math/vec3.js';
import type { Quat } from './math/quat.js';

export interface VehicleState {
  /** Position in NED metres from the home origin. */
  position: Vec3;
  /** Velocity in NED m/s. */
  velocity: Vec3;
  /** Attitude, body -> world. */
  attitude: Quat;
  /** Angular velocity in body frame, rad/s (this is the gyro reading). */
  angularVelocity: Vec3;
  /** Specific force in body frame, m/s^2 (this is the accelerometer reading). */
  accelBody: Vec3;
  /** Seconds since the simulation started. */
  timestamp: number;
}

/**
 * Physical parameters for a multirotor, mapped from the desktop `SitlCustomFrame`
 * schema. Only the fields the dynamics needs are kept here so the package stays
 * decoupled from the app.
 */
export interface MultirotorParams {
  /** Total mass, kg. */
  mass: number;
  /** Motor-to-motor diagonal distance, m. Arm radius = diagonal_size / 2. */
  diagonalSize: number;
  /** Number of motors (4 quad, 6 hexa, 8 octa). */
  numMotors: number;
  /** Hover throttle output, 0-1. Used to calibrate per-motor max thrust. */
  hoverThrOut: number;
  /** Propeller curve exponent (thrust linearization), ~0.5-0.65. */
  propExpo: number;
  /** Motor PWM range, microseconds. */
  pwmMin: number;
  pwmMax: number;
  /** Normalized motor spin range, 0-1 (idle and max). */
  spinMin: number;
  spinMax: number;
  /** Linear translational drag coefficient (N per m/s). Phase 1 simple model. */
  dragCoef: number;
  /** Yaw reaction-torque coefficient (N*m per N of thrust). */
  yawTorqueCoef: number;
}

export interface Environment {
  /** Gravitational acceleration magnitude, m/s^2 (positive). */
  gravity: number;
  /** Air density, kg/m^3. */
  airDensity: number;
  /** Wind velocity in NED m/s (Phase 3 fills this; defaults to zero). */
  wind: Vec3;
}

export interface StepResult {
  state: VehicleState;
}

export const DEFAULT_ENVIRONMENT: Environment = {
  gravity: 9.80665,
  airDensity: 1.225,
  wind: { x: 0, y: 0, z: 0 },
};

/**
 * A motor's mounting position (body FRD, m) and yaw factor. `yawFactor` matches
 * ArduPilot's AP_MotorsMatrix convention: +1 for a CCW propeller, -1 for CW.
 * Body yaw torque contribution is `yawFactor * yawTorqueCoef * thrust`, so when
 * SITL commands +yaw it increases CCW motors and the craft yaws nose-right (+z).
 */
export interface MotorMount {
  position: Vec3;
  yawFactor: 1 | -1;
}
