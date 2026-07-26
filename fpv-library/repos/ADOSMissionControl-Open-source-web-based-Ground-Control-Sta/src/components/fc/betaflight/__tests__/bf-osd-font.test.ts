/**
 * @module fc/betaflight/bf-osd-font.test
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { parseMcmFont, OSD_GLYPH_BYTES } from "../bf-osd-font";
import { encodeMspOsdCharWrite } from "@/lib/protocol/msp/encoders/osd-led";

/** Build a valid .mcm with `n` glyphs, each byte b = its line index mod 256. */
function makeMcm(n: number): string {
  const lines = ["MAX7456"];
  for (let g = 0; g < n; g++) {
    for (let b = 0; b < 64; b++) lines.push((b % 2 === 0 ? "10101010" : "01010101"));
  }
  return lines.join("\r\n") + "\r\n";
}

describe("parseMcmFont", () => {
  it("parses each 64-line block into a 64-byte glyph", () => {
    const { glyphs } = parseMcmFont(makeMcm(3));
    expect(glyphs).toHaveLength(3);
    expect(glyphs[0]).toHaveLength(OSD_GLYPH_BYTES);
    expect(glyphs[0][0]).toBe(0b10101010);
    expect(glyphs[0][1]).toBe(0b01010101);
  });

  it("rejects a file without the MAX7456 header", () => {
    expect(() => parseMcmFont("00000000\n".repeat(64))).toThrow(/MAX7456/);
  });

  it("rejects a data length that is not a multiple of 64 lines", () => {
    expect(() => parseMcmFont("MAX7456\n" + "00000000\n".repeat(63))).toThrow(/multiple/);
  });

  it("rejects a non-binary glyph line", () => {
    expect(() => parseMcmFont("MAX7456\n" + "0000000x\n".repeat(64))).toThrow(/glyph line/);
  });
});

describe("encodeMspOsdCharWrite", () => {
  it("prefixes a little-endian U16 address before the glyph bytes", () => {
    const glyph = new Uint8Array(64).fill(0xab);
    const buf = encodeMspOsdCharWrite(300, glyph);
    expect(buf).toHaveLength(66);
    expect(buf[0]).toBe(300 & 0xff); // LE low byte
    expect(buf[1]).toBe(300 >> 8); // LE high byte
    expect(buf[2]).toBe(0xab);
    expect(buf[65]).toBe(0xab);
  });
});
