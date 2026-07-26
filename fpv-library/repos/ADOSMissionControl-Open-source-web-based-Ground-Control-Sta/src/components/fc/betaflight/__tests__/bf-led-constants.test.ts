/**
 * @module fc/betaflight/bf-led-constants.test
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { packLed, unpackLed, toggleFlag, type BfLed } from "../bf-led-constants";

describe("packLed / unpackLed", () => {
  it("round-trips every field through the packed U32 layout", () => {
    const led: BfLed = { x: 13, y: 7, color: 9, fn: 5, directions: 0b101010, overlays: 0b1010101 };
    const packed = packLed(led);
    expect(packed).toBeGreaterThanOrEqual(0); // unsigned
    expect(unpackLed(packed)).toEqual(led);
  });

  it("places fields at the documented bit offsets", () => {
    expect(unpackLed(packLed({ x: 0, y: 0, color: 0, fn: 0, directions: 0, overlays: 0 }))).toEqual({ x: 0, y: 0, color: 0, fn: 0, directions: 0, overlays: 0 });
    // x is bits 4-7, y is bits 0-3
    expect(unpackLed(0x00000005)).toMatchObject({ x: 0, y: 5 });
    expect(unpackLed(0x00000050)).toMatchObject({ x: 5, y: 0 });
    // color at offset 22
    expect(unpackLed(0xf << 22).color).toBe(0xf);
    // direction at offset 26
    expect(unpackLed((0x3f << 26) >>> 0).directions).toBe(0x3f);
  });
});

describe("toggleFlag", () => {
  it("sets and clears a bit", () => {
    expect(toggleFlag(0, 3, true)).toBe(0b1000);
    expect(toggleFlag(0b1000, 3, false)).toBe(0);
  });
});
