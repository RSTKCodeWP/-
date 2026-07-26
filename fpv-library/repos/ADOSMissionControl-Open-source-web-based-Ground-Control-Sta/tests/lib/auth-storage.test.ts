import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

/**
 * Regression net for auth credential storage.
 *
 * The agent's X-ADOS-Key (and the per-paired-drone apiKey it derives
 * from) must live in-memory only. Persisting them to localStorage would
 * make them readable by every script on the page and recoverable from
 * a shared computer or a public-WiFi cache. Today the apiKey-bearing
 * stores have no `persist` middleware, and the only auth-adjacent
 * localStorage value is the deterministic browser fingerprint (which
 * is not a credential — see link-id-allocator.ts SECURITY NOTE).
 *
 * These tests fail if anyone wires Zustand `persist` onto the auth
 * stores, or if the apiKey field starts being written to localStorage
 * directly.
 */
function read(p: string): string {
  return readFileSync(resolve(__dirname, p), "utf-8");
}

describe("auth credential storage discipline", () => {
  const pairingStore = read("../../src/stores/pairing-store.ts");
  const connStore = read("../../src/stores/agent-connection-store.ts");

  it("pairing-store does not import zustand persist middleware", () => {
    expect(pairingStore).not.toMatch(/from "zustand\/middleware"/);
    expect(pairingStore).not.toContain("persist(");
  });

  it("pairing-store does not write apiKey to localStorage", () => {
    // The store may setItem for unrelated UI keys, but the apiKey field
    // must never appear in a localStorage write context.
    const writes = pairingStore.match(/localStorage\.setItem\([^)]*\)/g) ?? [];
    for (const w of writes) {
      expect(w).not.toContain("apiKey");
    }
  });

  it("agent-connection-store does not import zustand persist middleware", () => {
    expect(connStore).not.toMatch(/from "zustand\/middleware"/);
    expect(connStore).not.toContain("persist(");
  });

  it("agent-connection-store does not write apiKey to localStorage", () => {
    const writes = connStore.match(/localStorage\.setItem\([^)]*\)/g) ?? [];
    for (const w of writes) {
      expect(w).not.toContain("apiKey");
    }
  });

  it("agent-connection-store does not call localStorage at all", () => {
    // Defensive: it currently doesn't, and there's no reason for it to.
    expect(connStore).not.toContain("localStorage");
  });

  it("link-id-allocator carries the SECURITY NOTE explaining why its localStorage use is safe", () => {
    const src = read("../../src/lib/protocol/link-id-allocator.ts");
    expect(src).toContain("SECURITY NOTE");
    expect(src).toContain("NOT an authentication credential");
  });
});
