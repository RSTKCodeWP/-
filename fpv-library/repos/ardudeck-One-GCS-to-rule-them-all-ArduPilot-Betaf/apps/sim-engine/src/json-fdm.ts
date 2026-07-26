/**
 * ArduPilot SITL "JSON" FDM backend wire protocol.
 *
 * SITL is the UDP client: it sends a 40-byte `servo_packet` (little-endian) to
 * the external sim each physics frame, and expects a newline-terminated JSON
 * line of vehicle state in return.
 *
 * Reference: ArduPilot/libraries/SITL/SIM_JSON.cpp
 */

import type { VehicleState } from '@ardudeck/sim-physics';

/** Magic value at the head of every servo packet (SIM_JSON). */
export const SERVO_PACKET_MAGIC = 18458;
/** Default UDP port the external sim binds; SITL sends `--model JSON:<ip>` here. */
export const DEFAULT_FDM_PORT = 9002;
/** Number of PWM channels in a servo packet. */
export const NUM_CHANNELS = 16;
/** Bytes: magic(2) + frame_rate(2) + frame_count(4) + pwm[16](32). */
export const SERVO_PACKET_BYTES = 2 + 2 + 4 + NUM_CHANNELS * 2;

export interface ServoPacket {
  magic: number;
  frameRate: number;
  frameCount: number;
  pwm: number[];
}

/** Parse a servo packet. Returns null if the buffer is malformed. */
export function parseServoPacket(buf: Buffer): ServoPacket | null {
  if (buf.length < SERVO_PACKET_BYTES) return null;
  const magic = buf.readUInt16LE(0);
  if (magic !== SERVO_PACKET_MAGIC) return null;
  const frameRate = buf.readUInt16LE(2);
  const frameCount = buf.readUInt32LE(4);
  const pwm: number[] = [];
  for (let i = 0; i < NUM_CHANNELS; i++) {
    pwm.push(buf.readUInt16LE(8 + i * 2));
  }
  return { magic, frameRate, frameCount, pwm };
}

/** Build a servo packet buffer (used by tests and any local SITL stand-in). */
export function encodeServoPacket(p: { frameRate: number; frameCount: number; pwm: number[] }): Buffer {
  const buf = Buffer.alloc(SERVO_PACKET_BYTES);
  buf.writeUInt16LE(SERVO_PACKET_MAGIC, 0);
  buf.writeUInt16LE(p.frameRate & 0xffff, 2);
  buf.writeUInt32LE(p.frameCount >>> 0, 4);
  for (let i = 0; i < NUM_CHANNELS; i++) {
    buf.writeUInt16LE((p.pwm[i] ?? 0) & 0xffff, 8 + i * 2);
  }
  return buf;
}

/**
 * Serialize vehicle state into the JSON line SITL parses. Position/velocity are
 * NED metres relative to SITL's origin (-O home); gyro is body rad/s; accel_body
 * is body specific force m/s^2; quaternion is body->world [w,x,y,z].
 */
export function serializeState(state: VehicleState): string {
  const { position: p, velocity: v, attitude: q, angularVelocity: g, accelBody: a } = state;
  const f = (n: number) => (Number.isFinite(n) ? n : 0);
  const obj = {
    timestamp: f(state.timestamp),
    imu: {
      gyro: [f(g.x), f(g.y), f(g.z)],
      accel_body: [f(a.x), f(a.y), f(a.z)],
    },
    position: [f(p.x), f(p.y), f(p.z)],
    quaternion: [f(q.w), f(q.x), f(q.y), f(q.z)],
    velocity: [f(v.x), f(v.y), f(v.z)],
  };
  return `\n${JSON.stringify(obj)}\n`;
}
