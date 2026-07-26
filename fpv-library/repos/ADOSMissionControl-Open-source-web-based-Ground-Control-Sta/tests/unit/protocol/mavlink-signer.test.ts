/**
 * Tests for the browser-side MAVLink signer.
 *
 * Covers: fingerprint determinism, non-extractable key import, sign/verify
 * round-trip, monotonic timestamp with forward-only clamp (audit M4),
 * signature tail layout, hex helpers.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

import {
  MavlinkSigner,
  generateRandomKey,
  importNonExtractableKey,
  keyBytesToHex,
  keyFingerprint,
  zeroize,
} from "@/lib/protocol/mavlink-signer";

describe("mavlink-signer", () => {
  describe("generateRandomKey", () => {
    it("returns 32 bytes", () => {
      const key = generateRandomKey();
      expect(key.length).toBe(32);
    });

    it("returns different bytes on each call", () => {
      const a = generateRandomKey();
      const b = generateRandomKey();
      expect(a).not.toEqual(b);
    });
  });

  describe("keyBytesToHex", () => {
    it("encodes 32 bytes as 64 lowercase hex chars", () => {
      const bytes = new Uint8Array(32);
      for (let i = 0; i < 32; i++) bytes[i] = i;
      const hex = keyBytesToHex(bytes);
      expect(hex.length).toBe(64);
      expect(hex).toBe("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f");
    });
  });

  describe("keyFingerprint", () => {
    it("returns 8 hex chars", async () => {
      const key = new Uint8Array(32);
      const fp = await keyFingerprint(key);
      expect(fp.length).toBe(8);
      expect(/^[0-9a-f]{8}$/.test(fp)).toBe(true);
    });

    it("is deterministic", async () => {
      const key = new Uint8Array(32);
      key[0] = 42;
      const a = await keyFingerprint(key);
      const b = await keyFingerprint(key);
      expect(a).toBe(b);
    });

    it("changes with key contents", async () => {
      const a = new Uint8Array(32);
      const b = new Uint8Array(32);
      b[0] = 1;
      expect(await keyFingerprint(a)).not.toBe(await keyFingerprint(b));
    });
  });

  describe("zeroize", () => {
    it("overwrites the buffer in place", () => {
      const buf = new Uint8Array([1, 2, 3, 4]);
      zeroize(buf);
      expect(Array.from(buf)).toEqual([0, 0, 0, 0]);
    });
  });

  describe("importNonExtractableKey", () => {
    it("rejects wrong-length input", async () => {
      await expect(importNonExtractableKey(new Uint8Array(16))).rejects.toThrow(/32 bytes/);
    });

    it("returns a CryptoKey that cannot be exported as raw", async () => {
      const key = new Uint8Array(32);
      key[0] = 7;
      const ck = await importNonExtractableKey(key);
      await expect(crypto.subtle.exportKey("raw", ck)).rejects.toThrow();
    });
  });

  describe("MavlinkSigner.sign", () => {
    let signer: MavlinkSigner;
    beforeEach(async () => {
      const keyBytes = new Uint8Array(32);
      for (let i = 0; i < 32; i++) keyBytes[i] = i;
      const ck = await importNonExtractableKey(keyBytes);
      signer = new MavlinkSigner("test-drone", 0, "deadbeef", ck);
    });

    it("returns 13 bytes: link_id + 6-byte timestamp + 6-byte signature", async () => {
      const frame = new Uint8Array(20);
      const tail = await signer.sign(frame);
      expect(tail.length).toBe(13);
    });

    it("verify round-trips a frame it signed", async () => {
      const frame = new Uint8Array(24);
      for (let i = 0; i < 24; i++) frame[i] = i;
      const tail = await signer.sign(frame);
      const ok = await signer.verify(frame, tail);
      expect(ok).toBe(true);
    });

    it("verify rejects a mutated frame", async () => {
      const frame = new Uint8Array(24);
      const tail = await signer.sign(frame);
      frame[0] ^= 0xff;
      const ok = await signer.verify(frame, tail);
      expect(ok).toBe(false);
    });

    it("verify rejects a mutated signature", async () => {
      const frame = new Uint8Array(24);
      const tail = await signer.sign(frame);
      tail[12] ^= 0xff;
      const ok = await signer.verify(frame, tail);
      expect(ok).toBe(false);
    });

    it("link_id at byte 0 matches the signer's link_id", async () => {
      const keyBytes = new Uint8Array(32);
      const ck = await importNonExtractableKey(keyBytes);
      const signer7 = new MavlinkSigner("d", 7, "keyid007", ck);
      const tail = await signer7.sign(new Uint8Array(12));
      expect(tail[0]).toBe(7);
    });
  });

  describe("MavlinkSigner monotonic timestamp (audit M4)", () => {
    let signer: MavlinkSigner;
    beforeEach(async () => {
      const keyBytes = new Uint8Array(32);
      const ck = await importNonExtractableKey(keyBytes);
      signer = new MavlinkSigner("test-drone", 0, "deadbeef", ck);
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it("strictly advances across consecutive signs", async () => {
      const t1 = readTimestamp(await signer.sign(new Uint8Array(12)));
      const t2 = readTimestamp(await signer.sign(new Uint8Array(12)));
      expect(t2 > t1).toBe(true);
    });

    it("does not regress when the system clock jumps backward", async () => {
      // First sign at a fixed mock time.
      vi.useFakeTimers();
      vi.setSystemTime(new Date("2026-04-17T12:00:00Z"));
      const t1 = readTimestamp(await signer.sign(new Uint8Array(12)));

      // Simulate clock regression by 5 minutes.
      vi.setSystemTime(new Date("2026-04-17T11:55:00Z"));
      const t2 = readTimestamp(await signer.sign(new Uint8Array(12)));

      // Despite the clock going backwards, the timestamp must not regress.
      expect(t2 > t1).toBe(true);
    });

    it("seedTimestamp raises but never lowers the counter", async () => {
      const one = BigInt(1_000_000);
      signer.seedTimestamp(one);
      expect(signer.currentTimestamp()).toBe(one);
      signer.seedTimestamp(BigInt(0));
      expect(signer.currentTimestamp()).toBe(one);
    });
  });

  describe("MavlinkSigner link_id validation", () => {
    it("rejects link_id outside the byte range", async () => {
      const keyBytes = new Uint8Array(32);
      const ck = await importNonExtractableKey(keyBytes);
      expect(() => new MavlinkSigner("d", -1, "k", ck)).toThrow();
      expect(() => new MavlinkSigner("d", 256, "k", ck)).toThrow();
    });
  });
});

/** Read the 6-byte little-endian timestamp out of a signature tail. */
function readTimestamp(tail: Uint8Array): bigint {
  let v = BigInt(0);
  for (let i = 5; i >= 0; i--) {
    v = (v << BigInt(8)) | BigInt(tail[1 + i]);
  }
  return v;
}
