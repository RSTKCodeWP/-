import { describe, it, expect, beforeEach, vi } from "vitest";

import {
  MavlinkSigner,
  importNonExtractableKey,
} from "@/lib/protocol/mavlink-signer";

/**
 * These tests cover the Web Locks serialization in `MavlinkSigner`.
 *
 * Jsdom does not implement navigator.locks. We install a mock LockManager
 * that serializes exclusive requests FIFO against a shared counter so we
 * can assert that parallel sign() calls on the same (droneId, linkId) do
 * not interleave.
 */
describe("MavlinkSigner Web Locks", () => {
  let active = 0;
  let maxConcurrent = 0;
  // Per-lock-name chain of pending releases so sibling calls queue behind
  // each other. This mirrors how navigator.locks serializes exclusive
  // requests.
  const chains: Map<string, Promise<void>> = new Map();

  const mockLocks = {
    request: vi.fn(async (
      name: string,
      _opts: unknown,
      fn: () => Promise<unknown>,
    ) => {
      const previous = chains.get(name) ?? Promise.resolve();
      let release!: () => void;
      const thisRelease = new Promise<void>((r) => (release = r));
      chains.set(name, thisRelease);

      await previous;
      active += 1;
      if (active > maxConcurrent) maxConcurrent = active;
      try {
        return await fn();
      } finally {
        active -= 1;
        release();
      }
    }),
  };

  beforeEach(() => {
    active = 0;
    maxConcurrent = 0;
    chains.clear();
    mockLocks.request.mockClear();
    // Inject the mock LockManager onto globalThis.navigator so the signer
    // discovers it via feature detection.
    Object.defineProperty(globalThis, "navigator", {
      value: { ...globalThis.navigator, locks: mockLocks },
      writable: true,
      configurable: true,
    });
  });

  it("acquires the signing lock before computing the signature", async () => {
    const keyBytes = new Uint8Array(32);
    keyBytes[0] = 1;
    const key = await importNonExtractableKey(keyBytes);
    const signer = new MavlinkSigner("drone-a", 7, "keyid001", key);

    mockLocks.request.mockClear();
    await signer.sign(new Uint8Array(16));

    expect(mockLocks.request).toHaveBeenCalledTimes(1);
    expect(mockLocks.request.mock.calls[0][0]).toBe("ados-signing:drone-a:7");
    expect(mockLocks.request.mock.calls[0][1]).toMatchObject({ mode: "exclusive" });
  });

  it("serializes concurrent sign calls on the same drone+link", async () => {
    const keyBytes = new Uint8Array(32);
    const key = await importNonExtractableKey(keyBytes);
    const signer = new MavlinkSigner("drone-b", 3, "keyid002", key);

    const runs = Array.from({ length: 20 }, () => signer.sign(new Uint8Array(16)));
    await Promise.all(runs);

    expect(maxConcurrent).toBe(1);
  });

  it("assigns strictly increasing timestamps across serialized calls", async () => {
    const keyBytes = new Uint8Array(32);
    const key = await importNonExtractableKey(keyBytes);
    const signer = new MavlinkSigner("drone-c", 0, "keyid003", key);

    const tails = await Promise.all(
      Array.from({ length: 10 }, () => signer.sign(new Uint8Array(16))),
    );

    const timestamps = tails.map(readTimestamp);
    for (let i = 1; i < timestamps.length; i++) {
      expect(timestamps[i] > timestamps[i - 1]).toBe(true);
    }
  });
});

function readTimestamp(tail: Uint8Array): bigint {
  let v = BigInt(0);
  for (let i = 5; i >= 0; i--) {
    v = (v << BigInt(8)) | BigInt(tail[1 + i]);
  }
  return v;
}
