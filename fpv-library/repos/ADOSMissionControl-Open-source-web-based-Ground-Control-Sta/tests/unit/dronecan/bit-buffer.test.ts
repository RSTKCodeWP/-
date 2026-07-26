/**
 * @license GPL-3.0-only
 */

import { describe, expect, it } from "vitest";
import {
  BitReader,
  BitWriter,
  decodeFloat16,
  encodeFloat16,
} from "@/lib/dronecan/bit-buffer";

describe("BitWriter / BitReader integer round-trips", () => {
  it("round-trips int14 boundary values", () => {
    const cases = [-8192, -1, 0, 1, 8191];
    for (const v of cases) {
      const w = new BitWriter();
      w.write(v, 14);
      const r = new BitReader(w.toUint8Array());
      expect(r.read(14, true)).toBe(v);
    }
  });

  it("round-trips uint3 + uint8 + uint13 in exactly 3 bytes", () => {
    const w = new BitWriter();
    w.write(0b101, 3); // uint3
    w.write(0xa5, 8); // uint8
    w.write(0x1f5a & 0x1fff, 13); // uint13
    const buf = w.toUint8Array();
    expect(buf.length).toBe(3);
    expect(w.bitsWritten()).toBe(24);
    const r = new BitReader(buf);
    expect(r.read(3)).toBe(0b101);
    expect(r.read(8)).toBe(0xa5);
    expect(r.read(13)).toBe(0x1f5a & 0x1fff);
  });

  it("round-trips int27 straddling 4 bytes", () => {
    const cases = [-(1 << 26), -1, 0, 1, (1 << 26) - 1];
    for (const v of cases) {
      const w = new BitWriter();
      w.write(0, 1); // shift the int27 off byte alignment
      w.write(v, 27);
      const r = new BitReader(w.toUint8Array());
      r.skip(1);
      expect(r.read(27, true)).toBe(v);
    }
  });

  it("round-trips int37 BigInt boundary cases", () => {
    const cases: bigint[] = [
      -(BigInt(1) << BigInt(36)),
      BigInt(-1),
      BigInt(0),
      BigInt(1),
      (BigInt(1) << BigInt(36)) - BigInt(1),
    ];
    for (const v of cases) {
      const w = new BitWriter();
      w.writeBig(v, 37);
      const r = new BitReader(w.toUint8Array());
      expect(r.readBig(37, true)).toBe(v);
    }
  });

  it("packs LSB-first within each byte (canonical layout)", () => {
    const w = new BitWriter();
    // Write 0x07 in 3 bits, then 0x05 in 5 bits. Combined byte 0 = 0x07 | (0x05 << 3) = 0x2F.
    w.write(0x07, 3);
    w.write(0x05, 5);
    expect(w.toUint8Array()[0]).toBe(0x2f);
  });
});

describe("BitWriter / BitReader sequential mix", () => {
  it("preserves identical bytes across encode and decode", () => {
    const w = new BitWriter();
    w.write(1, 1);
    w.write(0xab, 8);
    w.write(0x123, 12);
    w.writeBig(BigInt("0x123456789ABCDEF"), 60);
    w.writeFloat16(1.5);
    w.write(-3, 6);
    const buf = w.toUint8Array();

    const r = new BitReader(buf);
    expect(r.read(1)).toBe(1);
    expect(r.read(8)).toBe(0xab);
    expect(r.read(12)).toBe(0x123);
    expect(r.readBig(60)).toBe(BigInt("0x123456789ABCDEF"));
    expect(r.readFloat16()).toBeCloseTo(1.5, 5);
    expect(r.read(6, true)).toBe(-3);
  });
});

describe("float16 special cases", () => {
  it("round-trips 0.0, -0.0, ±Inf, NaN, ±1.0, max normal, denormal", () => {
    const zero = decodeFloat16(encodeFloat16(0));
    expect(Object.is(zero, 0)).toBe(true);

    const negZero = decodeFloat16(encodeFloat16(-0));
    expect(Object.is(negZero, -0)).toBe(true);

    expect(decodeFloat16(encodeFloat16(Infinity))).toBe(Infinity);
    expect(decodeFloat16(encodeFloat16(-Infinity))).toBe(-Infinity);
    expect(Number.isNaN(decodeFloat16(encodeFloat16(NaN)))).toBe(true);

    expect(decodeFloat16(encodeFloat16(1))).toBe(1);
    expect(decodeFloat16(encodeFloat16(-1))).toBe(-1);
    expect(decodeFloat16(encodeFloat16(65504))).toBe(65504);

    // Smallest positive denormal: 2^-24.
    const denormal = Math.pow(2, -24);
    expect(decodeFloat16(encodeFloat16(denormal))).toBeCloseTo(denormal, 8);
  });

  it("encodes overflow to ±Inf", () => {
    expect(decodeFloat16(encodeFloat16(70000))).toBe(Infinity);
    expect(decodeFloat16(encodeFloat16(-70000))).toBe(-Infinity);
  });
});
