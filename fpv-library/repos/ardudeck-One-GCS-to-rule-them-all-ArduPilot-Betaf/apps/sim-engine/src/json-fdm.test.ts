import { describe, it, expect } from 'vitest';
import { initialState } from '@ardudeck/sim-physics';
import {
  encodeServoPacket,
  parseServoPacket,
  serializeState,
  SERVO_PACKET_BYTES,
  SERVO_PACKET_MAGIC,
} from './json-fdm.js';

describe('JSON FDM protocol', () => {
  it('round-trips a servo packet', () => {
    const pwm = Array.from({ length: 16 }, (_, i) => 1000 + i * 10);
    const buf = encodeServoPacket({ frameRate: 1000, frameCount: 42, pwm });
    expect(buf.length).toBe(SERVO_PACKET_BYTES);
    const parsed = parseServoPacket(buf);
    expect(parsed).not.toBeNull();
    expect(parsed!.magic).toBe(SERVO_PACKET_MAGIC);
    expect(parsed!.frameRate).toBe(1000);
    expect(parsed!.frameCount).toBe(42);
    expect(parsed!.pwm).toEqual(pwm);
  });

  it('rejects a wrong-magic packet', () => {
    const buf = encodeServoPacket({ frameRate: 1000, frameCount: 1, pwm: [] });
    buf.writeUInt16LE(1234, 0);
    expect(parseServoPacket(buf)).toBeNull();
  });

  it('rejects a too-short buffer', () => {
    expect(parseServoPacket(Buffer.alloc(10))).toBeNull();
  });

  it('serializes state as parseable JSON with the required keys', () => {
    const line = serializeState({
      ...initialState(),
      position: { x: 1, y: 2, z: -3 },
      velocity: { x: 0.1, y: 0.2, z: -0.3 },
      angularVelocity: { x: 0.01, y: 0.02, z: 0.03 },
      accelBody: { x: 0, y: 0, z: -9.8 },
      timestamp: 1.5,
    });
    const parsed = JSON.parse(line.trim());
    expect(parsed.timestamp).toBe(1.5);
    expect(parsed.imu.gyro).toEqual([0.01, 0.02, 0.03]);
    expect(parsed.imu.accel_body).toEqual([0, 0, -9.8]);
    expect(parsed.position).toEqual([1, 2, -3]);
    expect(parsed.velocity).toEqual([0.1, 0.2, -0.3]);
    expect(parsed.quaternion).toEqual([1, 0, 0, 0]);
  });

  it('sanitizes non-finite numbers to 0', () => {
    const line = serializeState({ ...initialState(), timestamp: NaN, position: { x: Infinity, y: 0, z: 0 } });
    const parsed = JSON.parse(line.trim());
    expect(parsed.timestamp).toBe(0);
    expect(parsed.position[0]).toBe(0);
  });
});
