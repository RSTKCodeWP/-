/**
 * Betaflight LED mode-colour codec tests (MSP_LED_STRIP_MODECOLOR 127 / 221).
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { decodeMspLedStripModeColors } from "@/lib/protocol/msp/decoders/config/led";
import { encodeMspSetLedStripModeColor } from "@/lib/protocol/msp/encoders/osd-led";

function dv(bytes: number[]): DataView {
  return new DataView(new Uint8Array(bytes).buffer);
}

describe("Betaflight LED mode colours", () => {
  it("decodes the fixed 48-triplet MSP_LED_STRIP_MODECOLOR layout", () => {
    // 36 mode/direction + 11 special + 1 aux triplet = 48 * 3 bytes.
    const bytes: number[] = [];
    for (let mode = 0; mode < 6; mode++)
      for (let dir = 0; dir < 6; dir++) bytes.push(mode, dir, (mode + dir) % 16);
    for (let fun = 0; fun < 11; fun++) bytes.push(6, fun, fun % 16);
    bytes.push(7, 0, 5); // aux channel

    const decoded = decodeMspLedStripModeColors(dv(bytes));

    expect(decoded).toHaveLength(48);
    expect(decoded[0]).toEqual({ mode: 0, fun: 0, color: 0 });
    expect(decoded[7]).toEqual({ mode: 1, fun: 1, color: 2 });
    expect(decoded[36]).toEqual({ mode: 6, fun: 0, color: 0 }); // first special colour
    expect(decoded[47]).toEqual({ mode: 7, fun: 0, color: 5 }); // aux entry last
  });

  it("ignores a trailing partial triplet", () => {
    const decoded = decodeMspLedStripModeColors(dv([0, 1, 2, 3, 4])); // 1 full triplet + 2 stray bytes
    expect(decoded).toHaveLength(1);
    expect(decoded[0]).toEqual({ mode: 0, fun: 1, color: 2 });
  });

  it("encodes MSP_SET_LED_STRIP_MODECOLOR as 3 bytes [mode, fun, color]", () => {
    const buf = encodeMspSetLedStripModeColor(3, 4, 9);
    expect(Array.from(buf)).toEqual([3, 4, 9]);
  });
});
