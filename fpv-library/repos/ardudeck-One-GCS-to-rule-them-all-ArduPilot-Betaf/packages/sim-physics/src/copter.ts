/**
 * 6DOF multirotor flight dynamics. One fixed step maps SITL motor PWM to the
 * next vehicle state and the sensor readings (gyro + accelerometer) SITL reads
 * back through the JSON FDM backend.
 *
 * Frames: world = NED (z down, ground at z=0), body = FRD, attitude = body->world.
 */

import { add, cross, scale, sub, vec3, type Vec3 } from './math/vec3.js';
import {
  integrateQuat,
  rotateBodyToWorld,
  rotateWorldToBody,
} from './math/quat.js';
import { frameGeometry } from './frame-geometry.js';
import { motorThrusts } from './motor-model.js';
import type { Environment, MultirotorParams, StepResult, VehicleState } from './types.js';

/** Diagonal inertia tensor (kg*m^2) estimated from mass and arm radius. */
function inertia(params: MultirotorParams): { ixx: number; iyy: number; izz: number } {
  const r = params.diagonalSize / 2;
  const base = params.mass * r * r;
  return {
    ixx: Math.max(1e-4, 0.25 * base),
    iyy: Math.max(1e-4, 0.25 * base),
    izz: Math.max(1e-4, 0.5 * base),
  };
}

/** Horizontal ground friction coefficient (fraction of weight) when in contact. */
const GROUND_FRICTION = 0.6;
/** At/below this NED z (metres) the vehicle is touching the ground. */
const GROUND_CONTACT_EPS = 1e-3;
/** Peak thrust boost from ground effect at the surface (fraction). */
const GROUND_EFFECT_GAIN = 0.15;

export interface StepOptions {
  /** Thrust scale from the battery (loaded V / refV). Default 1. */
  voltageScale?: number;
  /** Apply ground-effect thrust augmentation near the surface. Default false. */
  groundEffect?: boolean;
}

/** Thrust multiplier from ground effect: strongest at the surface, gone by ~1 rotor span up. */
function groundEffectFactor(altitude: number, rotorRadius: number): number {
  if (altitude <= 0) return 1 + GROUND_EFFECT_GAIN;
  const span = Math.max(0.1, 2 * rotorRadius);
  return 1 + GROUND_EFFECT_GAIN * Math.exp(-altitude / span);
}

export function stepCopter(
  pwms: number[],
  state: VehicleState,
  params: MultirotorParams,
  env: Environment,
  dt: number,
  opts: StepOptions = {},
): StepResult {
  const voltageScale = opts.voltageScale ?? 1;
  let thrusts = motorThrusts(pwms, params, env.gravity, voltageScale);
  if (opts.groundEffect) {
    const altitude = -state.position.z;
    const ge = groundEffectFactor(altitude, params.diagonalSize / 2);
    thrusts = thrusts.map((t) => t * ge);
  }
  const mounts = frameGeometry(params.numMotors, params.diagonalSize);

  // --- Motor forces & moments in body frame ---
  let forceBody = vec3(0, 0, 0);
  let momentBody = vec3(0, 0, 0);
  for (let i = 0; i < params.numMotors; i++) {
    const thrust = thrusts[i] ?? 0;
    const mount = mounts[i];
    if (!mount) continue;
    const f = vec3(0, 0, -thrust); // thrust acts "up" = -z in FRD
    forceBody = add(forceBody, f);
    // roll/pitch from thrust offset, plus prop reaction torque about z (yaw)
    momentBody = add(momentBody, cross(mount.position, f));
    momentBody = add(momentBody, vec3(0, 0, mount.yawFactor * params.yawTorqueCoef * thrust));
  }

  // --- Aerodynamic drag (linear), opposing airspeed in body frame ---
  const airVelWorld = sub(state.velocity, env.wind);
  const airVelBody = rotateWorldToBody(state.attitude, airVelWorld);
  const dragBody = scale(airVelBody, -params.dragCoef);
  forceBody = add(forceBody, dragBody);

  // --- Resolve to world, add gravity, handle ground contact ---
  const nonGravWorld = rotateBodyToWorld(state.attitude, forceBody);
  const gravityWorld = vec3(0, 0, params.mass * env.gravity); // down = +z
  const provisional = add(nonGravWorld, gravityWorld);

  const onGround = state.position.z >= -GROUND_CONTACT_EPS;
  let normalAndFrictionWorld = vec3(0, 0, 0);
  if (onGround) {
    // Normal force cancels any net downward force so the craft rests (and the
    // accelerometer reads ~1g) instead of sinking through the ground.
    if (provisional.z > 0) {
      normalAndFrictionWorld = vec3(0, 0, -provisional.z);
    }
    // Horizontal kinetic friction opposing ground-relative motion.
    const weight = params.mass * env.gravity;
    const fx = -Math.sign(state.velocity.x) * Math.min(Math.abs(state.velocity.x) * params.mass, GROUND_FRICTION * weight);
    const fy = -Math.sign(state.velocity.y) * Math.min(Math.abs(state.velocity.y) * params.mass, GROUND_FRICTION * weight);
    normalAndFrictionWorld = add(normalAndFrictionWorld, vec3(fx, fy, 0));
  }

  const totalWorld = add(provisional, normalAndFrictionWorld);
  const accelWorld = scale(totalWorld, 1 / params.mass);

  // Accelerometer = specific force (all non-gravitational forces) in body frame.
  const nonGravTotalWorld = add(nonGravWorld, normalAndFrictionWorld);
  const accelBody = rotateWorldToBody(state.attitude, scale(nonGravTotalWorld, 1 / params.mass));

  // --- Integrate translation (semi-implicit Euler) ---
  let velocity = add(state.velocity, scale(accelWorld, dt));
  let position = add(state.position, scale(velocity, dt));

  // --- Rotational dynamics ---
  const I = inertia(params);
  const w = state.angularVelocity;
  const Iw = vec3(I.ixx * w.x, I.iyy * w.y, I.izz * w.z);
  const gyroTerm = cross(w, Iw);
  const angAccel = vec3(
    (momentBody.x - gyroTerm.x) / I.ixx,
    (momentBody.y - gyroTerm.y) / I.iyy,
    (momentBody.z - gyroTerm.z) / I.izz,
  );
  const angularVelocity = add(w, scale(angAccel, dt));
  const attitude = integrateQuat(state.attitude, angularVelocity, dt);

  // --- Ground clamp on the integrated position/velocity ---
  if (position.z > 0) {
    position = { ...position, z: 0 };
    if (velocity.z > 0) velocity = { ...velocity, z: 0 };
  }

  const next: VehicleState = {
    position,
    velocity,
    attitude,
    angularVelocity,
    accelBody,
    timestamp: state.timestamp + dt,
  };
  return { state: next };
}

/** A vehicle at rest on the ground, level, at the NED origin. */
export function initialState(): VehicleState {
  return {
    position: vec3(0, 0, 0),
    velocity: vec3(0, 0, 0),
    attitude: { w: 1, x: 0, y: 0, z: 0 },
    angularVelocity: vec3(0, 0, 0),
    accelBody: vec3(0, 0, 0),
    timestamp: 0,
  };
}

export type { Vec3 };
