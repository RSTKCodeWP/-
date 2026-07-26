/**
 * MAVLink control encoders: ManualControl, PositionTarget, AttitudeTarget, RC override.
 * @module protocol/encoders/control
 */

import { buildFrame } from "./frame";

// ── MANUAL_CONTROL (ID 69) ──────────────────────────────────

/**
 * Encode a MANUAL_CONTROL message.
 *
 * Sent at up to 50 Hz for real-time joystick/gamepad control.
 * Axes are int16 (-1000 to 1000), buttons is uint16 bitmask.
 */
export function encodeManualControl(
  targetSys: number,
  x: number,
  y: number,
  z: number,
  r: number,
  buttons: number,
  sysId = 255,
  compId = 190,
): Uint8Array {
  const payload = new Uint8Array(11);
  const dv = new DataView(payload.buffer);
  dv.setInt16(0, x, true);        // pitch (forward/back)
  dv.setInt16(2, y, true);        // roll (left/right)
  dv.setInt16(4, z, true);        // throttle (up/down)
  dv.setInt16(6, r, true);        // yaw (rotation)
  dv.setUint16(8, buttons, true); // button bitmask
  payload[10] = targetSys;        // target system
  return buildFrame(69, payload, sysId, compId);
}

// ── SET_POSITION_TARGET_GLOBAL_INT (ID 86) ───────────────────

/**
 * Encode SET_POSITION_TARGET_GLOBAL_INT.
 *
 * Used for guided position commands (GUIDED mode goto).
 * lat/lon as int32 * 1e7, alt in meters.
 */
export function encodeSetPositionTargetGlobalInt(
  targetSys: number,
  targetComp: number,
  latInt: number,
  lonInt: number,
  alt: number,
  vx: number,
  vy: number,
  vz: number,
  typeMask: number,
  coordFrame: number,
  sysId = 255,
  compId = 190,
): Uint8Array {
  const payload = new Uint8Array(53);
  const dv = new DataView(payload.buffer);
  dv.setUint32(0, 0, true);           // timeBootMs (0 = let FC use its own)
  dv.setInt32(4, latInt, true);        // lat * 1e7
  dv.setInt32(8, lonInt, true);        // lon * 1e7
  dv.setFloat32(12, alt, true);        // alt
  dv.setFloat32(16, vx, true);         // vx
  dv.setFloat32(20, vy, true);         // vy
  dv.setFloat32(24, vz, true);         // vz
  dv.setFloat32(28, 0, true);          // afx
  dv.setFloat32(32, 0, true);          // afy
  dv.setFloat32(36, 0, true);          // afz
  dv.setFloat32(40, 0, true);          // yaw
  dv.setFloat32(44, 0, true);          // yawRate
  dv.setUint16(48, typeMask, true);    // typeMask
  payload[50] = targetSys;
  payload[51] = targetComp;
  payload[52] = coordFrame;
  return buildFrame(86, payload, sysId, compId);
}

// ── SET_ATTITUDE_TARGET (ID 82) ──────────────────────────────

/**
 * Encode SET_ATTITUDE_TARGET.
 *
 * Used for attitude-level guided flight commands.
 * Quaternion is constructed from Euler angles (simplified roll/pitch/yaw).
 */
export function encodeSetAttitudeTarget(
  targetSys: number,
  targetComp: number,
  roll: number,
  pitch: number,
  yaw: number,
  thrust: number,
  typeMask: number,
  sysId = 255,
  compId = 190,
): Uint8Array {
  const payload = new Uint8Array(39);
  const dv = new DataView(payload.buffer);
  dv.setUint32(0, 0, true);             // timeBootMs
  // Simplified quaternion from Euler: identity with small-angle approx
  const cr = Math.cos(roll / 2), sr = Math.sin(roll / 2);
  const cp = Math.cos(pitch / 2), sp = Math.sin(pitch / 2);
  const cy = Math.cos(yaw / 2), sy = Math.sin(yaw / 2);
  dv.setFloat32(4, cr * cp * cy + sr * sp * sy, true);   // q[0] w
  dv.setFloat32(8, sr * cp * cy - cr * sp * sy, true);   // q[1] x
  dv.setFloat32(12, cr * sp * cy + sr * cp * sy, true);  // q[2] y
  dv.setFloat32(16, cr * cp * sy - sr * sp * cy, true);  // q[3] z
  dv.setFloat32(20, 0, true);           // bodyRollRate
  dv.setFloat32(24, 0, true);           // bodyPitchRate
  dv.setFloat32(28, 0, true);           // bodyYawRate
  dv.setFloat32(32, thrust, true);       // thrust (0-1)
  payload[36] = targetSys;
  payload[37] = targetComp;
  payload[38] = typeMask;
  return buildFrame(82, payload, sysId, compId);
}

// ── RC_CHANNELS_OVERRIDE (ID 70) ────────────────────────────

/**
 * Encode RC_CHANNELS_OVERRIDE.
 *
 * Overrides RC input channels. Channel value of 0 means "release" (stop override).
 * @param channels - Up to 8 channel values (1000-2000 us, 0 = release)
 */
export function encodeRcChannelsOverride(
  targetSys: number,
  targetComp: number,
  channels: number[],
  sysId = 255,
  compId = 190,
): Uint8Array {
  const payload = new Uint8Array(18);
  const dv = new DataView(payload.buffer);
  // Wire order: 8 x uint16 channels, then uint8 targetSys, uint8 targetComp
  for (let i = 0; i < 8; i++) {
    dv.setUint16(i * 2, channels[i] ?? 0, true);
  }
  payload[16] = targetSys;
  payload[17] = targetComp;
  return buildFrame(70, payload, sysId, compId);
}
