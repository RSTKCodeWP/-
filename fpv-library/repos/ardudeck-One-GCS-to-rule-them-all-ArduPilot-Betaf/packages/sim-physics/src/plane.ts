/**
 * Basic fixed-wing 6DOF model. Aerodynamic forces from a linear lift/drag
 * polar; control surfaces (aileron/elevator/rudder) produce body moments. Good
 * enough to fly trimmed cruise, climb/descend on elevator, and bank on aileron.
 * Not a high-fidelity aero model - coefficients are representative, not tuned to
 * a specific airframe.
 *
 * SITL plane servo order (RCMAP defaults): pwm[0]=aileron, [1]=elevator,
 * [2]=throttle, [3]=rudder.
 */

import { add, cross, scale, sub, vec3 } from './math/vec3.js';
import { integrateQuat, rotateBodyToWorld, rotateWorldToBody } from './math/quat.js';
import type { Environment, StepResult, VehicleState } from './types.js';

export interface PlaneParams {
  mass: number;
  /** Wing reference area (m^2). */
  wingArea: number;
  /** Wing span (m) and mean chord (m) for moment scaling. */
  span: number;
  chord: number;
  /** Lift curve: CL = cl0 + clAlpha * alpha (alpha in rad). */
  cl0: number;
  clAlpha: number;
  /** Drag polar: CD = cd0 + inducedK * CL^2. */
  cd0: number;
  inducedK: number;
  /** Max thrust at full throttle (N). */
  maxThrust: number;
  /** Control-surface moment effectiveness (per unit deflection [-1,1]). */
  elevatorEffect: number;
  aileronEffect: number;
  rudderEffect: number;
  /** Rotational damping (per rad/s). */
  pitchDamp: number;
  rollDamp: number;
  yawDamp: number;
}

function inertia(p: PlaneParams) {
  const b = p.span / 2;
  const c = p.chord;
  return {
    ixx: Math.max(1e-3, 0.25 * p.mass * b * b),
    iyy: Math.max(1e-3, 0.25 * p.mass * c * c * 4),
    izz: Math.max(1e-3, 0.4 * p.mass * b * b),
  };
}

/** PWM (1000-2000) -> [-1, 1] around 1500. */
function surface(pwm: number | undefined): number {
  const v = ((pwm ?? 1500) - 1500) / 500;
  return Math.max(-1, Math.min(1, v));
}
/** PWM (1000-2000) -> [0, 1]. */
function throttle(pwm: number | undefined): number {
  const v = ((pwm ?? 1000) - 1000) / 1000;
  return Math.max(0, Math.min(1, v));
}

export function initialPlaneState(airspeed = 0): VehicleState {
  return {
    position: vec3(0, 0, 0),
    velocity: vec3(airspeed, 0, 0),
    attitude: { w: 1, x: 0, y: 0, z: 0 },
    angularVelocity: vec3(0, 0, 0),
    accelBody: vec3(0, 0, 0),
    timestamp: 0,
  };
}

export function stepPlane(
  pwms: number[],
  state: VehicleState,
  params: PlaneParams,
  env: Environment,
  dt: number,
): StepResult {
  const aileron = surface(pwms[0]);
  const elevator = surface(pwms[1]);
  const thr = throttle(pwms[2]);
  const rudder = surface(pwms[3]);

  // Relative airflow in body frame.
  const airWorld = sub(state.velocity, env.wind);
  const ab = rotateWorldToBody(state.attitude, airWorld);
  const V = Math.max(0, Math.hypot(ab.x, ab.y, ab.z));
  const q = 0.5 * env.airDensity * V * V;

  const alpha = V > 0.5 ? Math.atan2(ab.z, ab.x) : 0; // angle of attack
  const beta = V > 0.5 ? Math.asin(Math.max(-1, Math.min(1, ab.y / Math.max(V, 1e-6)))) : 0;

  const CL = params.cl0 + params.clAlpha * alpha;
  const CD = params.cd0 + params.inducedK * CL * CL;
  const lift = q * params.wingArea * CL;
  const drag = q * params.wingArea * CD;

  // Lift acts perpendicular to airflow in the body x-z plane; drag opposes it.
  const ca = Math.cos(alpha);
  const sa = Math.sin(alpha);
  let forceBody = vec3(
    params.maxThrust * thr - drag * ca + lift * sa,
    -q * params.wingArea * 1.0 * beta, // side force opposing sideslip
    -drag * sa - lift * ca,
  );

  // Moments from control surfaces + aerodynamic damping.
  const w = state.angularVelocity;
  const momentBody = vec3(
    q * params.wingArea * params.span * (params.aileronEffect * aileron) - params.rollDamp * w.x,
    q * params.wingArea * params.chord * (params.elevatorEffect * elevator) - params.pitchDamp * w.y,
    q * params.wingArea * params.span * (params.rudderEffect * rudder - 0.5 * beta) - params.yawDamp * w.z,
  );

  // World forces: aero/thrust + gravity, with a simple ground plane.
  const nonGravWorld = rotateBodyToWorld(state.attitude, forceBody);
  const gravityWorld = vec3(0, 0, params.mass * env.gravity);
  let totalWorld = add(nonGravWorld, gravityWorld);
  let normalWorld = vec3(0, 0, 0);
  const onGround = state.position.z >= -1e-3;
  if (onGround && totalWorld.z > 0) {
    normalWorld = vec3(0, 0, -totalWorld.z);
    totalWorld = add(totalWorld, normalWorld);
  }

  const accelWorld = scale(totalWorld, 1 / params.mass);
  const accelBody = rotateWorldToBody(
    state.attitude,
    scale(add(nonGravWorld, normalWorld), 1 / params.mass),
  );

  let velocity = add(state.velocity, scale(accelWorld, dt));
  let position = add(state.position, scale(velocity, dt));

  const I = inertia(params);
  const Iw = vec3(I.ixx * w.x, I.iyy * w.y, I.izz * w.z);
  const gyroTerm = cross(w, Iw);
  const angAccel = vec3(
    (momentBody.x - gyroTerm.x) / I.ixx,
    (momentBody.y - gyroTerm.y) / I.iyy,
    (momentBody.z - gyroTerm.z) / I.izz,
  );
  const angularVelocity = add(w, scale(angAccel, dt));
  const attitude = integrateQuat(state.attitude, angularVelocity, dt);

  if (position.z > 0) {
    position = { ...position, z: 0 };
    if (velocity.z > 0) velocity = { ...velocity, z: 0 };
  }

  return {
    state: { position, velocity, attitude, angularVelocity, accelBody, timestamp: state.timestamp + dt },
  };
}
