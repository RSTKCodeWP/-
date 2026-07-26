/**
 * @license GPL-3.0-only
 */

import { describe, expect, it } from "vitest";
import {
  HEALTH_OK,
  HEALTH_WARNING,
  MODE_MAINTENANCE,
  MODE_OPERATIONAL,
  MODE_SOFTWARE_UPDATE,
  decodeNodeStatus,
  encodeNodeStatus,
} from "@/lib/dronecan/dsdl/node-status";

describe("dsdl NodeStatus", () => {
  it("round-trips a typical OPERATIONAL OK status", () => {
    const original = {
      uptime_sec: 12345,
      health: HEALTH_OK,
      mode: MODE_OPERATIONAL,
      vendor_specific_status_code: 0x1234,
    } as const;
    const buf = encodeNodeStatus(original);
    expect(buf.length).toBe(7);
    const decoded = decodeNodeStatus(buf);
    expect(decoded).toEqual(original);
  });

  it("encodes the packed health+mode byte correctly", () => {
    const buf = encodeNodeStatus({
      uptime_sec: 0,
      health: HEALTH_WARNING,
      mode: MODE_MAINTENANCE,
      vendor_specific_status_code: 0,
    });
    // byte 4: health bits 0..1, mode bits 2..4
    // WARNING=1, MAINTENANCE=2 → 0b0000_1001 = 0x09
    expect(buf[4]).toBe(0x09);
  });

  it("handles SOFTWARE_UPDATE mode and a large uptime", () => {
    const buf = encodeNodeStatus({
      uptime_sec: 0x7fffffff,
      health: HEALTH_OK,
      mode: MODE_SOFTWARE_UPDATE,
      vendor_specific_status_code: 0xabcd,
    });
    const decoded = decodeNodeStatus(buf);
    expect(decoded.uptime_sec).toBe(0x7fffffff);
    expect(decoded.mode).toBe(MODE_SOFTWARE_UPDATE);
    expect(decoded.vendor_specific_status_code).toBe(0xabcd);
  });

  it("matches the documented wire bytes for a hand-crafted example", () => {
    // uptime_sec = 1 → 01 00 00 00
    // health = OK (0), mode = OPERATIONAL (0) → byte 4 = 0x00
    // vendor = 0 → 00 00
    const buf = encodeNodeStatus({
      uptime_sec: 1,
      health: HEALTH_OK,
      mode: MODE_OPERATIONAL,
      vendor_specific_status_code: 0,
    });
    expect(Array.from(buf)).toEqual([0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]);
  });

  it("rejects a buffer shorter than 7 bytes", () => {
    expect(() => decodeNodeStatus(new Uint8Array(6))).toThrow();
  });
});
