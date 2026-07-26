import { describe, it, expect } from "vitest";

import {
  hexToBytes,
  shannonBitsPerChar,
  validateHex,
} from "@/components/fc/security/ImportKeyModal";

describe("ImportKeyModal validateHex", () => {
  it("returns invalid with no reason on empty input", () => {
    const r = validateHex("");
    expect(r.valid).toBe(false);
    expect(r.reason).toBeUndefined();
  });

  it("rejects wrong length", () => {
    expect(validateHex("a".repeat(63)).reason).toMatch(/64 hex chars/);
    expect(validateHex("a".repeat(65)).reason).toMatch(/64 hex chars/);
  });

  it("rejects non-hex characters", () => {
    const r = validateHex("z".repeat(64));
    expect(r.valid).toBe(false);
    expect(r.reason).toMatch(/hex/i);
  });

  it("rejects all-zero keys as low-entropy", () => {
    const r = validateHex("0".repeat(64));
    expect(r.valid).toBe(false);
    expect(r.reason).toMatch(/entropy/i);
  });

  it("rejects repeated-pattern low-entropy keys", () => {
    // 64 chars of alternating "a0" has entropy 1 bit/char — well below 4.
    const r = validateHex("a0".repeat(32));
    expect(r.valid).toBe(false);
    expect(r.reason).toMatch(/entropy/i);
  });

  it("accepts a uniform-random 64-char hex string", () => {
    // Fixture: first 64 hex chars of a SHA-256 hash.
    const random = "3c5e2bdf8a40219157f0d1b6afe43a0c7e58cb4d2f9a1e306b8cafdfe87c52d9";
    const r = validateHex(random);
    expect(r.valid).toBe(true);
    expect(r.reason).toBeUndefined();
  });

  it("accepts mixed-case hex (downcase before entropy check)", () => {
    const r = validateHex("3C5E2BDF8A40219157F0D1B6AFE43A0C7E58CB4D2F9A1E306B8CAFDFE87C52D9");
    expect(r.valid).toBe(true);
  });
});

describe("shannonBitsPerChar", () => {
  it("returns 0 for empty string", () => {
    expect(shannonBitsPerChar("")).toBe(0);
  });

  it("returns 0 for a single-character string", () => {
    expect(shannonBitsPerChar("aaaaa")).toBe(0);
  });

  it("returns ~1 for a two-symbol alternating string", () => {
    const h = shannonBitsPerChar("abababab");
    expect(h).toBeCloseTo(1, 2);
  });

  it("returns ~4 for a uniform 16-symbol alphabet", () => {
    // Each hex digit appearing 4 times in 64 chars → H ≈ log2(16) = 4.
    const uniform = "0123456789abcdef".repeat(4);
    const h = shannonBitsPerChar(uniform);
    expect(h).toBeCloseTo(4, 2);
  });
});

describe("hexToBytes", () => {
  it("round-trips through lowercase", () => {
    const bytes = hexToBytes("deadbeef");
    expect(Array.from(bytes)).toEqual([0xde, 0xad, 0xbe, 0xef]);
  });

  it("handles uppercase", () => {
    const bytes = hexToBytes("DEADBEEF");
    expect(Array.from(bytes)).toEqual([0xde, 0xad, 0xbe, 0xef]);
  });

  it("returns 32-byte array for a 64-char hex", () => {
    const bytes = hexToBytes("3c5e2bdf8a40219157f0d1b6afe43a0c7e58cb4d2f9a1e306b8cafdfe87c52d9");
    expect(bytes.length).toBe(32);
  });
});
