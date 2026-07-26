import { describe, it, expect } from "vitest";

import {
  encodeCanForward,
  encodeCanFrame,
  encodeCanFdFrame,
  encodeCanFilterModify,
  MAV_CMD_CAN_FORWARD,
} from "@/lib/protocol/encoders/can-forward";
import type { CanFrame } from "@/lib/protocol/transport/can-transport";

// MAVLink v2 frame layout used by buildFrame():
//   [0] 0xfd
//   [1] payload length
//   [2] incompat flags
//   [3] compat flags
//   [4] sequence
//   [5] sysid
//   [6] compid
//   [7..9] msg id
//   [10..10+len-1] payload
//   [..+2] CRC16

const HEADER_LEN = 10;
const CRC_LEN = 2;

function msgIdOf(frame: Uint8Array): number {
  return frame[7] | (frame[8] << 8) | (frame[9] << 16);
}

describe("encodeCanForward", () => {
  it("exposes the canonical MAV_CMD identifier", () => {
    expect(MAV_CMD_CAN_FORWARD).toBe(32000);
  });

  it("builds a COMMAND_LONG frame (msg 76, 33-byte payload)", () => {
    const frame = encodeCanForward(1, 1, 1);
    expect(frame[0]).toBe(0xfd);
    expect(frame[1]).toBe(33);
    expect(msgIdOf(frame)).toBe(76);
    expect(frame.byteLength).toBe(HEADER_LEN + 33 + CRC_LEN);
  });

  it("places the bus index in param1 (float32 at offset 10)", () => {
    const frame = encodeCanForward(1, 1, 2);
    const dv = new DataView(
      frame.buffer,
      frame.byteOffset + HEADER_LEN,
      frame.byteLength - HEADER_LEN - CRC_LEN,
    );
    expect(dv.getFloat32(0, true)).toBe(2);
  });

  it("encodes the MAV_CMD identifier at payload offset 28 (uint16)", () => {
    const frame = encodeCanForward(1, 1, 0);
    const dv = new DataView(
      frame.buffer,
      frame.byteOffset + HEADER_LEN,
      frame.byteLength - HEADER_LEN - CRC_LEN,
    );
    expect(dv.getUint16(28, true)).toBe(MAV_CMD_CAN_FORWARD);
  });

  it("targets the requested system and component", () => {
    const frame = encodeCanForward(7, 42, 1);
    const dv = new DataView(
      frame.buffer,
      frame.byteOffset + HEADER_LEN,
      frame.byteLength - HEADER_LEN - CRC_LEN,
    );
    expect(dv.getUint8(30)).toBe(7);
    expect(dv.getUint8(31)).toBe(42);
  });
});

describe("encodeCanFrame", () => {
  const baseFrame: CanFrame = {
    id: 0x1234abcd,
    extended: true,
    dlc: 8,
    data: new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8]),
  };

  it("builds a CAN_FRAME (msg 386, 16-byte payload)", () => {
    const frame = encodeCanFrame(1, 1, 1, baseFrame);
    expect(frame[0]).toBe(0xfd);
    expect(frame[1]).toBe(16);
    expect(msgIdOf(frame)).toBe(386);
    expect(frame.byteLength).toBe(HEADER_LEN + 16 + CRC_LEN);
  });

  it("packs the id, target, bus, len, and data in spec order", () => {
    const frame = encodeCanFrame(7, 42, 2, baseFrame);
    const dv = new DataView(
      frame.buffer,
      frame.byteOffset + HEADER_LEN,
      frame.byteLength - HEADER_LEN - CRC_LEN,
    );
    expect(dv.getUint32(0, true)).toBe(0x1234abcd);
    expect(dv.getUint8(4)).toBe(7);
    expect(dv.getUint8(5)).toBe(42);
    expect(dv.getUint8(6)).toBe(2);
    expect(dv.getUint8(7)).toBe(8);
    for (let i = 0; i < 8; i++) {
      expect(dv.getUint8(8 + i)).toBe(baseFrame.data[i]);
    }
  });

  it("zero-pads short payloads to 8 bytes", () => {
    const shortFrame: CanFrame = {
      id: 0x12,
      extended: false,
      dlc: 3,
      data: new Uint8Array([0xaa, 0xbb, 0xcc]),
    };
    const frame = encodeCanFrame(1, 1, 1, shortFrame);
    const dv = new DataView(
      frame.buffer,
      frame.byteOffset + HEADER_LEN,
      frame.byteLength - HEADER_LEN - CRC_LEN,
    );
    expect(dv.getUint8(7)).toBe(3);
    expect(dv.getUint8(8)).toBe(0xaa);
    expect(dv.getUint8(9)).toBe(0xbb);
    expect(dv.getUint8(10)).toBe(0xcc);
    for (let i = 11; i < 16; i++) {
      expect(dv.getUint8(i)).toBe(0);
    }
  });

  it("clamps oversized data to 8 bytes", () => {
    const big: CanFrame = {
      id: 0x1,
      extended: false,
      dlc: 8,
      data: new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
    };
    const frame = encodeCanFrame(1, 1, 1, big);
    expect(frame[1]).toBe(16);
  });
});

describe("encodeCanFdFrame", () => {
  it("builds a CANFD_FRAME (msg 387, 72-byte payload)", () => {
    const data = new Uint8Array(64);
    for (let i = 0; i < 64; i++) data[i] = i;
    const fdFrame: CanFrame = { id: 0xabc, extended: false, dlc: 64, data };
    const frame = encodeCanFdFrame(1, 1, 1, fdFrame);
    expect(frame[0]).toBe(0xfd);
    expect(frame[1]).toBe(72);
    expect(msgIdOf(frame)).toBe(387);
    expect(frame.byteLength).toBe(HEADER_LEN + 72 + CRC_LEN);
  });

  it("preserves all 64 data bytes in order", () => {
    const data = new Uint8Array(64);
    for (let i = 0; i < 64; i++) data[i] = (i * 7) & 0xff;
    const fdFrame: CanFrame = { id: 0xff, extended: false, dlc: 64, data };
    const frame = encodeCanFdFrame(2, 8, 2, fdFrame);
    const dv = new DataView(
      frame.buffer,
      frame.byteOffset + HEADER_LEN,
      frame.byteLength - HEADER_LEN - CRC_LEN,
    );
    expect(dv.getUint8(4)).toBe(2);
    expect(dv.getUint8(5)).toBe(8);
    expect(dv.getUint8(6)).toBe(2);
    expect(dv.getUint8(7)).toBe(64);
    for (let i = 0; i < 64; i++) {
      expect(dv.getUint8(8 + i)).toBe(data[i]);
    }
  });
});

describe("encodeCanFilterModify", () => {
  it("builds a CAN_FILTER_MODIFY frame (msg 388, 37-byte payload)", () => {
    const frame = encodeCanFilterModify(1, 1, 1, 0, [0x100, 0x200]);
    expect(frame[1]).toBe(37);
    expect(msgIdOf(frame)).toBe(388);
    const dv = new DataView(
      frame.buffer,
      frame.byteOffset + HEADER_LEN,
      frame.byteLength - HEADER_LEN - CRC_LEN,
    );
    expect(dv.getUint16(0, true)).toBe(0x100);
    expect(dv.getUint16(2, true)).toBe(0x200);
    expect(dv.getUint8(32)).toBe(1);
    expect(dv.getUint8(33)).toBe(1);
    expect(dv.getUint8(34)).toBe(1);
    expect(dv.getUint8(35)).toBe(0);
    expect(dv.getUint8(36)).toBe(2);
  });
});
