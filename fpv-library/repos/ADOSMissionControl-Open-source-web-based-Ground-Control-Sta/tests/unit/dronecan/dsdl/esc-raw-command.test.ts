/**
 * @license GPL-3.0-only
 */

import { describe, expect, it } from "vitest";
import {
  ESC_RAW_COMMAND_BITS,
  ESC_RAW_COMMAND_MAX,
  ESC_RAW_COMMAND_MAX_CHANNELS,
  ESC_RAW_COMMAND_MIN,
  decodeRawCommand,
  encodeRawCommand,
} from "@/lib/dronecan/dsdl/esc-raw-command";

describe("dsdl esc.RawCommand", () => {
  it("encodes a single channel into ceil(14/8) = 2 bytes", () => {
    const buf = encodeRawCommand({ cmd: [1234] });
    expect(buf.length).toBe(2);
    const round = decodeRawCommand(buf);
    expect(round.cmd).toEqual([1234]);
  });

  it("packs 5 channels into ceil(70/8) = 9 bytes", () => {
    const cmd = [100, 200, 300, -400, -500];
    const buf = encodeRawCommand({ cmd });
    expect(buf.length).toBe(Math.ceil((cmd.length * ESC_RAW_COMMAND_BITS) / 8));
    const round = decodeRawCommand(buf);
    expect(round.cmd).toEqual(cmd);
  });

  it("packs 20 channels (the DSDL max) into ceil(280/8) = 35 bytes", () => {
    const cmd = Array.from({ length: ESC_RAW_COMMAND_MAX_CHANNELS }, (_, i) =>
      i % 2 === 0 ? i * 100 : -(i * 100),
    );
    const buf = encodeRawCommand({ cmd });
    expect(buf.length).toBe(
      Math.ceil((ESC_RAW_COMMAND_MAX_CHANNELS * ESC_RAW_COMMAND_BITS) / 8),
    );
    const round = decodeRawCommand(buf);
    expect(round.cmd).toEqual(cmd);
  });

  it("clamps out-of-range commands to int14 bounds", () => {
    const buf = encodeRawCommand({ cmd: [99999, -99999] });
    const round = decodeRawCommand(buf);
    expect(round.cmd).toEqual([ESC_RAW_COMMAND_MAX, ESC_RAW_COMMAND_MIN]);
  });

  it("throws when more than 20 channels are supplied", () => {
    const cmd = new Array(ESC_RAW_COMMAND_MAX_CHANNELS + 1).fill(0);
    expect(() => encodeRawCommand({ cmd })).toThrow();
  });
});
