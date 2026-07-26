import { describe, it, expect } from 'vitest';

import { encodeSetEkfSourceSet, MAV_CMD_SET_EKF_SOURCE_SET } from '@/lib/protocol/encoders/ekf-source';

// MAVLink v2 frame layout used by buildFrame():
//   [0] 0xfd
//   [1] payload length
//   [2] incompat flags
//   [3] compat flags
//   [4] sequence
//   [5] sysid (sender)
//   [6] compid (sender)
//   [7..9] msg id (24-bit, little-endian)
//   [10..10+payloadLen-1] payload
//   [..+2] CRC16
//
// COMMAND_LONG (msg id 76) has a 33-byte payload with the following little-endian layout:
//   [0..3]   float32 param1
//   [4..7]   float32 param2
//   [8..11]  float32 param3
//   [12..15] float32 param4
//   [16..19] float32 param5
//   [20..23] float32 param6
//   [24..27] float32 param7
//   [28..29] uint16  command
//   [30]     target system
//   [31]     target component
//   [32]     confirmation
//
// CRC_EXTRA for COMMAND_LONG is 152 — folded into the trailing CRC16. The
// encoder must produce a valid CRC, otherwise the receiver drops the frame.

describe('encodeSetEkfSourceSet', () => {
  it('exposes the expected MAV_CMD identifier', () => {
    expect(MAV_CMD_SET_EKF_SOURCE_SET).toBe(42007);
  });

  it('builds a 45-byte v2 COMMAND_LONG frame (10 header + 33 payload + 2 CRC)', () => {
    const frame = encodeSetEkfSourceSet(1, 255, 190, 1, 1);
    expect(frame.byteLength).toBe(10 + 33 + 2);
    expect(frame[0]).toBe(0xfd);
    expect(frame[1]).toBe(33); // payload length
  });

  it('places sysid at byte 5 and compid at byte 6', () => {
    const frame = encodeSetEkfSourceSet(2, 42, 17, 1, 1);
    expect(frame[5]).toBe(42); // sender sysid
    expect(frame[6]).toBe(17); // sender compid
  });

  it('encodes msg id 76 (COMMAND_LONG) in bytes 7-9', () => {
    const frame = encodeSetEkfSourceSet(3, 255, 190, 1, 1);
    expect(frame[7]).toBe(76);
    expect(frame[8]).toBe(0);
    expect(frame[9]).toBe(0);
  });

  it('encodes the source-set index in param1 and 42007 in the command field', () => {
    const frame = encodeSetEkfSourceSet(2, 255, 190, 1, 1);
    const dv = new DataView(frame.buffer, frame.byteOffset, frame.byteLength);
    expect(dv.getFloat32(10 + 0, true)).toBe(2);   // param1 = sourceSet
    expect(dv.getFloat32(10 + 4, true)).toBe(0);   // param2
    expect(dv.getFloat32(10 + 24, true)).toBe(0);  // param7
    expect(dv.getUint16(10 + 28, true)).toBe(42007); // command
  });

  it('targets the correct system and component, with confirmation=0', () => {
    const frame = encodeSetEkfSourceSet(1, 255, 190, 5, 7);
    expect(frame[10 + 30]).toBe(5); // target system
    expect(frame[10 + 31]).toBe(7); // target component
    expect(frame[10 + 32]).toBe(0); // confirmation
  });

  it('produces a CRC computed with CRC_EXTRA=152 (COMMAND_LONG)', async () => {
    // Round-trip through the parser to prove the CRC is valid for COMMAND_LONG.
    const { MAVLinkParser } = await import('@/lib/protocol/mavlink-parser');
    const parser = new MAVLinkParser();
    const frame = encodeSetEkfSourceSet(3, 255, 190, 1, 1);
    let decodedMsgId: number | null = null;
    parser.onFrame((f) => { decodedMsgId = f.msgId; });
    parser.feed(frame);
    expect(decodedMsgId).toBe(76);
  });
});
