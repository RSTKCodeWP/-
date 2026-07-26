/**
 * MSP2 serial-config codec tests (MSP2_COMMON_SERIAL_CONFIG 0x1009 / 0x100A).
 * The 32-bit function mask carries bits above 15 that the legacy U16 drops.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { decodeMspSerialConfig2 } from "@/lib/protocol/msp/decoders/config/serial";
import { encodeMspSetSerialConfig2 } from "@/lib/protocol/msp/encoders/config";

const PORTS = [
  { identifier: 20, functions: 1, mspBaudRate: 0, gpsBaudRate: 0, telemetryBaudRate: 0, blackboxBaudRate: 0 },
  // FrSky OSD (bit 16) + MSP (bit 0) — the >15 bit is the point of MSP2.
  { identifier: 51, functions: (1 << 16) | 1, mspBaudRate: 5, gpsBaudRate: 2, telemetryBaudRate: 3, blackboxBaudRate: 4 },
];

describe("MSP2 serial config", () => {
  it("round-trips a 32-bit function mask (bit 16 preserved)", () => {
    const buf = encodeMspSetSerialConfig2(PORTS);
    // 1 count byte + 2 * 10-byte records
    expect(buf.length).toBe(1 + 2 * 10);
    expect(buf[0]).toBe(2); // leading port count

    const decoded = decodeMspSerialConfig2(new DataView(buf.buffer)).ports;
    expect(decoded).toEqual(PORTS);
    // the extended function bit survived (legacy U16 would have dropped it)
    expect(decoded[1].functions & (1 << 16)).not.toBe(0);
  });

  it("tolerates a wider per-port stride from newer firmware", () => {
    // 1 record with 2 trailing extension bytes appended (stride derived from count).
    const bytes = [
      1, // count
      51, 0x01, 0x00, 0x01, 0x00, 5, 2, 3, 4, // identifier + U32 mask (bit0+bit16) + 4 baud
      0xff, 0xff, // trailing extension bytes
    ];
    const decoded = decodeMspSerialConfig2(new DataView(new Uint8Array(bytes).buffer)).ports;
    expect(decoded).toHaveLength(1);
    expect(decoded[0].identifier).toBe(51);
    expect(decoded[0].functions).toBe((1 << 16) | 1);
    expect(decoded[0].blackboxBaudRate).toBe(4);
  });
});
