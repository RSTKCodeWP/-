/**
 * Unit-quaternion math for attitude. Convention: a quaternion rotates a vector
 * from the BODY frame into the WORLD (NED) frame. Stored as `{w,x,y,z}`, matching
 * the ArduPilot JSON FDM `quaternion` field order [w,x,y,z].
 */

import type { Vec3 } from './vec3.js';

export interface Quat {
  w: number;
  x: number;
  y: number;
  z: number;
}

export function quat(w = 1, x = 0, y = 0, z = 0): Quat {
  return { w, x, y, z };
}

export const IDENTITY: Quat = { w: 1, x: 0, y: 0, z: 0 };

export function multiply(a: Quat, b: Quat): Quat {
  return {
    w: a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z,
    x: a.w * b.x + a.x * b.w + a.y * b.z - a.z * b.y,
    y: a.w * b.y - a.x * b.z + a.y * b.w + a.z * b.x,
    z: a.w * b.z + a.x * b.y - a.y * b.x + a.z * b.w,
  };
}

export function normalizeQuat(q: Quat): Quat {
  const n = Math.sqrt(q.w * q.w + q.x * q.x + q.y * q.y + q.z * q.z);
  if (n < 1e-12) return { ...IDENTITY };
  return { w: q.w / n, x: q.x / n, y: q.y / n, z: q.z / n };
}

/** Rotate a body-frame vector into the world (NED) frame: v_world = q * v * q^-1. */
export function rotateBodyToWorld(q: Quat, v: Vec3): Vec3 {
  // t = 2 * (q_vec x v); v' = v + q.w*t + q_vec x t
  const tx = 2 * (q.y * v.z - q.z * v.y);
  const ty = 2 * (q.z * v.x - q.x * v.z);
  const tz = 2 * (q.x * v.y - q.y * v.x);
  return {
    x: v.x + q.w * tx + (q.y * tz - q.z * ty),
    y: v.y + q.w * ty + (q.z * tx - q.x * tz),
    z: v.z + q.w * tz + (q.x * ty - q.y * tx),
  };
}

/** Rotate a world-frame vector into the body frame (inverse rotation). */
export function rotateWorldToBody(q: Quat, v: Vec3): Vec3 {
  return rotateBodyToWorld({ w: q.w, x: -q.x, y: -q.y, z: -q.z }, v);
}

/**
 * Integrate a quaternion by a body-frame angular velocity (rad/s) over dt.
 * qdot = 0.5 * q (x) [0, w]; then renormalize.
 */
export function integrateQuat(q: Quat, omegaBody: Vec3, dt: number): Quat {
  const wq: Quat = { w: 0, x: omegaBody.x, y: omegaBody.y, z: omegaBody.z };
  const qd = multiply(q, wq);
  const next: Quat = {
    w: q.w + 0.5 * qd.w * dt,
    x: q.x + 0.5 * qd.x * dt,
    y: q.y + 0.5 * qd.y * dt,
    z: q.z + 0.5 * qd.z * dt,
  };
  return normalizeQuat(next);
}

/** Yaw/pitch/roll (ZYX) from a body->world quaternion, radians. */
export function toEuler(q: Quat): { roll: number; pitch: number; yaw: number } {
  const sinr = 2 * (q.w * q.x + q.y * q.z);
  const cosr = 1 - 2 * (q.x * q.x + q.y * q.y);
  const roll = Math.atan2(sinr, cosr);

  const sinp = 2 * (q.w * q.y - q.z * q.x);
  const pitch = Math.abs(sinp) >= 1 ? Math.sign(sinp) * (Math.PI / 2) : Math.asin(sinp);

  const siny = 2 * (q.w * q.z + q.x * q.y);
  const cosy = 1 - 2 * (q.y * q.y + q.z * q.z);
  const yaw = Math.atan2(siny, cosy);

  return { roll, pitch, yaw };
}

/** Build a body->world quaternion from roll/pitch/yaw (ZYX), radians. */
export function fromEuler(roll: number, pitch: number, yaw: number): Quat {
  const cr = Math.cos(roll / 2);
  const sr = Math.sin(roll / 2);
  const cp = Math.cos(pitch / 2);
  const sp = Math.sin(pitch / 2);
  const cy = Math.cos(yaw / 2);
  const sy = Math.sin(yaw / 2);
  return normalizeQuat({
    w: cr * cp * cy + sr * sp * sy,
    x: sr * cp * cy - cr * sp * sy,
    y: cr * sp * cy + sr * cp * sy,
    z: cr * cp * sy - sr * sp * cy,
  });
}
