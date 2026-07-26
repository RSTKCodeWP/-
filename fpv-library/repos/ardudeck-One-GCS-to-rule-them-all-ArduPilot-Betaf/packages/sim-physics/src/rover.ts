/**
 * Ground vehicle (rover) model using a kinematic bicycle: throttle drives a
 * forward force against rolling/aero drag, steering sets a yaw rate that scales
 * with speed. Motion is constrained to the ground plane (z=0, level attitude).
 *
 * SITL rover servo order: pwm[0]=steering, pwm[2]=throttle.
 */

import { vec3 } from './math/vec3.js';
import { fromEuler, toEuler } from './math/quat.js';
import type { Environment, StepResult, VehicleState } from './types.js';

export interface RoverParams {
  mass: number;
  /** Max forward thrust at full throttle (N). */
  maxThrust: number;
  /** Linear drag (N per m/s). */
  dragCoef: number;
  /** Distance between axles (m). */
  wheelbase: number;
  /** Max steering angle at full deflection (rad). */
  maxSteer: number;
}

function cmd(pwm: number | undefined): number {
  const v = ((pwm ?? 1500) - 1500) / 500;
  return Math.max(-1, Math.min(1, v));
}

export function initialRoverState(): VehicleState {
  return {
    position: vec3(0, 0, 0),
    velocity: vec3(0, 0, 0),
    attitude: { w: 1, x: 0, y: 0, z: 0 },
    angularVelocity: vec3(0, 0, 0),
    accelBody: vec3(0, 0, 0),
    timestamp: 0,
  };
}

export function stepRover(
  pwms: number[],
  state: VehicleState,
  params: RoverParams,
  env: Environment,
  dt: number,
): StepResult {
  const steer = cmd(pwms[0]) * params.maxSteer;
  const throttle = cmd(pwms[2]);

  // Forward speed is the body-x component of NED velocity given current yaw.
  const { yaw } = toEuler(state.attitude);
  const speed = state.velocity.x * Math.cos(yaw) + state.velocity.y * Math.sin(yaw);

  const forwardForce = throttle * params.maxThrust - params.dragCoef * speed;
  const accelFwd = forwardForce / params.mass;
  const newSpeed = speed + accelFwd * dt;

  const yawRate = Math.abs(newSpeed) > 1e-3 ? (newSpeed / params.wheelbase) * Math.tan(steer) : 0;
  const newYaw = yaw + yawRate * dt;

  const velocity = vec3(newSpeed * Math.cos(newYaw), newSpeed * Math.sin(newYaw), 0);
  const position = vec3(
    state.position.x + velocity.x * dt,
    state.position.y + velocity.y * dt,
    0,
  );

  return {
    state: {
      position,
      velocity,
      attitude: fromEuler(0, 0, newYaw),
      angularVelocity: vec3(0, 0, yawRate),
      // Forward specific force in body x; gravity reaction on z (resting on ground).
      accelBody: vec3(accelFwd, 0, -env.gravity),
      timestamp: state.timestamp + dt,
    },
  };
}
