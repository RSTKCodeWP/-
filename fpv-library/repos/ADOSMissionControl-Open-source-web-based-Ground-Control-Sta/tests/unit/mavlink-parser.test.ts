import { describe, it, expect } from 'vitest';
import {
  MAVLinkParser,
  crc16,
  crc16Accumulate,
  CRC_EXTRA,
  PAYLOAD_LENGTHS,
} from '@/lib/protocol/mavlink-parser';

/** Build a valid MAVLink v2 frame from scratch. */
function buildFrame(
  msgId: number,
  payload: Uint8Array,
  systemId = 1,
  componentId = 1,
  sequence = 0,
): Uint8Array {
  const payloadLen = payload.length;
  const frameLen = 10 + payloadLen + 2; // header + payload + CRC
  const buf = new Uint8Array(frameLen);

  // STX
  buf[0] = 0xfd;
  // Payload length
  buf[1] = payloadLen;
  // Incompatibility flags
  buf[2] = 0;
  // Compatibility flags
  buf[3] = 0;
  // Sequence
  buf[4] = sequence;
  // System ID
  buf[5] = systemId;
  // Component ID
  buf[6] = componentId;
  // Message ID (3 bytes, little-endian)
  buf[7] = msgId & 0xff;
  buf[8] = (msgId >> 8) & 0xff;
  buf[9] = (msgId >> 16) & 0xff;
  // Payload
  buf.set(payload, 10);

  // CRC: covers bytes 1 through (10 + payloadLen - 1)
  let crc = crc16(buf, 1, 9 + payloadLen);
  const crcExtra = CRC_EXTRA.get(msgId)!;
  crc = crc16Accumulate(crcExtra, crc);
  buf[10 + payloadLen] = crc & 0xff;
  buf[10 + payloadLen + 1] = (crc >> 8) & 0xff;

  return buf;
}

/** Build a valid HEARTBEAT frame (msgId=0, 9-byte payload). */
function buildHeartbeat(systemId = 1, componentId = 1): Uint8Array {
  const payload = new Uint8Array(9);
  // custom_mode (4 bytes), type (1), autopilot (1), base_mode (1), system_status (1), mavlink_version (1)
  payload[4] = 2;  // type: quadrotor
  payload[5] = 3;  // autopilot: ardupilot
  payload[6] = 0x80; // base_mode: armed
  payload[7] = 4;  // system_status: active
  payload[8] = 3;  // mavlink_version
  return buildFrame(0, payload, systemId, componentId);
}

describe('crc16()', () => {
  it('returns 0xFFFF for empty data (zero length)', () => {
    const result = crc16(new Uint8Array(0), 0, 0);
    expect(result).toBe(0xffff);
  });
});

describe('crc16Accumulate()', () => {
  it('produces same result as full buffer CRC for single byte', () => {
    const buf = new Uint8Array([0x42]);
    const fullCrc = crc16(buf, 0, 1);

    let accumCrc = 0xffff;
    accumCrc = crc16Accumulate(0x42, accumCrc);

    expect(accumCrc).toBe(fullCrc);
  });

  it('produces same result as full buffer CRC for multiple bytes', () => {
    const buf = new Uint8Array([0x01, 0x02, 0x03, 0x04]);
    const fullCrc = crc16(buf, 0, 4);

    let accumCrc = 0xffff;
    for (const byte of buf) {
      accumCrc = crc16Accumulate(byte, accumCrc);
    }

    expect(accumCrc).toBe(fullCrc);
  });
});

describe('MAVLinkParser', () => {
  it('emits frame for valid HEARTBEAT frame', () => {
    const parser = new MAVLinkParser();
    const frames: any[] = [];
    parser.onFrame((f) => frames.push(f));

    const heartbeat = buildHeartbeat();
    parser.feed(heartbeat);

    expect(frames.length).toBe(1);
    expect(frames[0].msgId).toBe(0);
  });

  it('emits correct msgId, systemId, componentId', () => {
    const parser = new MAVLinkParser();
    const frames: any[] = [];
    parser.onFrame((f) => frames.push(f));

    const heartbeat = buildHeartbeat(42, 7);
    parser.feed(heartbeat);

    expect(frames[0].msgId).toBe(0);
    expect(frames[0].systemId).toBe(42);
    expect(frames[0].componentId).toBe(7);
  });

  it('skips garbage bytes before valid frame', () => {
    const parser = new MAVLinkParser();
    const frames: any[] = [];
    parser.onFrame((f) => frames.push(f));

    const garbage = new Uint8Array([0xaa, 0xbb, 0xcc, 0xdd, 0xee]);
    const heartbeat = buildHeartbeat();
    const combined = new Uint8Array(garbage.length + heartbeat.length);
    combined.set(garbage, 0);
    combined.set(heartbeat, garbage.length);

    parser.feed(combined);
    expect(frames.length).toBe(1);
    expect(frames[0].msgId).toBe(0);
  });

  it('handles split frames (header in one call, payload+CRC in another)', () => {
    const parser = new MAVLinkParser();
    const frames: any[] = [];
    parser.onFrame((f) => frames.push(f));

    const heartbeat = buildHeartbeat();
    // Split at byte 6 (mid-header)
    const part1 = heartbeat.subarray(0, 6);
    const part2 = heartbeat.subarray(6);

    parser.feed(part1);
    expect(frames.length).toBe(0); // not yet complete

    parser.feed(part2);
    expect(frames.length).toBe(1);
    expect(frames[0].msgId).toBe(0);
  });

  it('handles zero-trimmed payloads (short payload restored to PAYLOAD_LENGTHS size)', () => {
    const parser = new MAVLinkParser();
    const frames: any[] = [];
    parser.onFrame((f) => frames.push(f));

    // Build a heartbeat with only 5 bytes of payload (zero-trimmed)
    // The last 4 bytes are zeros, so MAVLink v2 can trim them
    const shortPayload = new Uint8Array(5);
    shortPayload[4] = 2; // type: quadrotor
    const frame = buildFrame(0, shortPayload);

    parser.feed(frame);

    expect(frames.length).toBe(1);
    // Payload should be restored to canonical length (9 for HEARTBEAT)
    expect(frames[0].payload.byteLength).toBe(9);
  });

  it('does NOT emit frame for CRC mismatch', () => {
    const parser = new MAVLinkParser();
    const frames: any[] = [];
    parser.onFrame((f) => frames.push(f));

    const heartbeat = buildHeartbeat();
    // Corrupt the CRC
    heartbeat[heartbeat.length - 1] ^= 0xff;

    parser.feed(heartbeat);
    expect(frames.length).toBe(0);
  });

  it('does NOT emit frame for unknown msgId', () => {
    const parser = new MAVLinkParser();
    const frames: any[] = [];
    parser.onFrame((f) => frames.push(f));

    // Build a frame with msgId 9999 which is not in CRC_EXTRA
    const payload = new Uint8Array(4);
    const frameLen = 10 + 4 + 2;
    const buf = new Uint8Array(frameLen);
    buf[0] = 0xfd;
    buf[1] = 4;
    buf[5] = 1;
    buf[6] = 1;
    buf[7] = 9999 & 0xff;
    buf[8] = (9999 >> 8) & 0xff;
    buf[9] = (9999 >> 16) & 0xff;

    parser.feed(buf);
    expect(frames.length).toBe(0);
  });

  it('handles multiple frames in single feed() call', () => {
    const parser = new MAVLinkParser();
    const frames: any[] = [];
    parser.onFrame((f) => frames.push(f));

    const hb1 = buildHeartbeat(1, 1);
    const hb2 = buildHeartbeat(2, 1);
    const combined = new Uint8Array(hb1.length + hb2.length);
    combined.set(hb1, 0);
    combined.set(hb2, hb1.length);

    parser.feed(combined);
    expect(frames.length).toBe(2);
    expect(frames[0].systemId).toBe(1);
    expect(frames[1].systemId).toBe(2);
  });

  it('onFrame() returns working unsubscribe function', () => {
    const parser = new MAVLinkParser();
    const frames: any[] = [];
    const unsub = parser.onFrame((f) => frames.push(f));

    parser.feed(buildHeartbeat());
    expect(frames.length).toBe(1);

    unsub();
    parser.feed(buildHeartbeat());
    expect(frames.length).toBe(1); // no new frame added
  });

  it('reset() clears partial frame state', () => {
    const parser = new MAVLinkParser();
    const frames: any[] = [];
    parser.onFrame((f) => frames.push(f));

    // Feed partial frame
    const heartbeat = buildHeartbeat();
    parser.feed(heartbeat.subarray(0, 5));
    parser.reset();

    // Now feed a complete frame
    parser.feed(buildHeartbeat());
    expect(frames.length).toBe(1);
  });
});
