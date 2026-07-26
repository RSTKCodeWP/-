/**
 * Cloud pairing mutation tests.
 *
 * The pairing flow is the most security-sensitive cloud surface: claiming
 * a code returns the agent's API key, so the branches that gate a claim
 * (charset validation, TTL expiry, single-owner guards, double-claim
 * rejection, pre-generated-code collision and expiry reclaim) must hold.
 *
 * Convex mutations cannot be invoked without a runtime, and convex-test
 * is not a dependency here, so the test works two ways (the established
 * pattern in this folder):
 *
 *   1. Source-reading pins the public surface — both claim paths are
 *      exported as `mutation` (client-callable), the recovery sweep is an
 *      `internalMutation` (never client-callable), and each guard branch
 *      exists in the handler text.
 *   2. A faithful re-implementation of the two claim handlers and the
 *      pre-generate handler runs against a fake db, exercising the real
 *      branching against concrete rows.
 */
import { readFile } from "node:fs/promises";
import path from "node:path";
import { describe, expect, it } from "vitest";

const PAIRING_PATH = path.join(process.cwd(), "convex/cmdPairing.ts");

// ── Constants mirrored from the source under test ──────────

const SAFE_CHARSET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789";
const CODE_LENGTH = 6;
const CODE_TTL_MS = 15 * 60 * 1000;
const PAIRING_CODE_RE = new RegExp(`^[${SAFE_CHARSET}]{${CODE_LENGTH}}$`);

function normalizePairingCode(code: string): string {
  const normalized = code.trim().toUpperCase();
  if (!PAIRING_CODE_RE.test(normalized)) {
    throw new Error("Pairing code must be six safe uppercase characters");
  }
  return normalized;
}

// ── Source-surface assertions ──────────────────────────────

describe("cmdPairing exported surface", () => {
  it("exposes both claim paths as client-callable mutations", async () => {
    const text = await readFile(PAIRING_PATH, "utf8");
    expect(text).toContain("export const claimPairingCode = mutation({");
    expect(text).toContain("export const claimPairingCodeAnon = mutation({");
    expect(text).toContain("export const preGenerateCode = mutation({");
  });

  it("keeps the recovery sweeps internal (never client-callable)", async () => {
    const text = await readFile(PAIRING_PATH, "utf8");
    expect(text).toContain("export const wipeByDeviceIds = internalMutation({");
    expect(text).toContain("export const cleanExpiredRequests = internalMutation({");
    // The wider device wipe must not leak as a public mutation.
    expect(text).not.toContain("export const wipeByDeviceIds = mutation({");
  });

  it("enforces a six-char safe charset on the pairing code", async () => {
    const text = await readFile(PAIRING_PATH, "utf8");
    expect(text).toContain('const SAFE_CHARSET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789";');
    expect(text).toContain("const CODE_LENGTH = 6;");
    expect(text).toContain("if (!PAIRING_CODE_RE.test(normalized)) {");
  });

  it("checks expiresAt before honoring either claim path", async () => {
    const text = await readFile(PAIRING_PATH, "utf8");
    // Both handlers reject an expired request and delete the stale row.
    const matches = text.match(/if \(request\.expiresAt < Date\.now\(\)\) \{/g) ?? [];
    expect(matches.length).toBeGreaterThanOrEqual(2);
    expect(text).toContain('return { error: "pairing_code_expired" as const };');
  });

  it("guards a device already owned by a different account/browser before the claim patch", async () => {
    const text = await readFile(PAIRING_PATH, "utf8");
    expect(text).toContain('return { error: "device_owned_by_other" as const };');
    // Signed-in path rejects when any device row belongs to another user.
    expect(text).toContain("deviceRows.some((d) => d.userId !== userId)");
    // Anon path rejects when the existing drone is owned by another marker.
    expect(text).toContain("existingDrone && existingDrone.userId !== droneUserId");
  });

  it("rejects an already-claimed code on the signed-in path", async () => {
    const text = await readFile(PAIRING_PATH, "utf8");
    expect(text).toContain(
      'if (request.claimedBy) return { error: "code_already_claimed" as const };',
    );
  });
});

// ── Fake db + handler re-implementations ───────────────────

interface PairingRequestRow {
  _id: string;
  pairingCode: string;
  expiresAt: number;
  deviceId?: string;
  apiKey?: string;
  agentName?: string;
  createdBy?: string;
  claimedBy?: string;
  claimedAt?: number;
}

interface DroneRow {
  _id: string;
  userId: string;
  deviceId: string;
  apiKey: string;
}

/**
 * Minimal in-memory store standing in for the Convex db. It supports the
 * exact two query shapes the claim handlers use: lookup of a pairing
 * request by pairingCode, and lookup of drone rows by deviceId.
 */
class FakeStore {
  requests: PairingRequestRow[] = [];
  drones: DroneRow[] = [];
  private seq = 0;

  insertRequest(row: Omit<PairingRequestRow, "_id">): PairingRequestRow {
    const full = { _id: `req-${this.seq++}`, ...row };
    this.requests.push(full);
    return full;
  }

  insertDrone(row: Omit<DroneRow, "_id">): DroneRow {
    const full = { _id: `drone-${this.seq++}`, ...row };
    this.drones.push(full);
    return full;
  }

  requestByCode(code: string): PairingRequestRow | undefined {
    return this.requests.find((r) => r.pairingCode === code);
  }

  dronesByDeviceId(deviceId: string): DroneRow[] {
    return this.drones.filter((d) => d.deviceId === deviceId);
  }

  patchRequest(id: string, patch: Partial<PairingRequestRow>): void {
    const row = this.requests.find((r) => r._id === id);
    if (row) Object.assign(row, patch);
  }

  patchDrone(id: string, patch: Partial<DroneRow>): void {
    const row = this.drones.find((d) => d._id === id);
    if (row) Object.assign(row, patch);
  }

  deleteRequest(id: string): void {
    this.requests = this.requests.filter((r) => r._id !== id);
  }
}

type ClaimResult =
  | { error: "invalid_pairing_code" }
  | { error: "pairing_code_expired" }
  | { error: "code_already_claimed" }
  | { error: "device_owned_by_other" }
  | { error: null; deviceId: string; apiKey: string };

/**
 * Re-implements the signed-in `claimPairingCode` handler against the fake
 * store, preserving the exact guard ordering: invalid → expired →
 * already-claimed → owned-by-other → patch (claim) → upsert.
 */
function claimPairingCode(
  store: FakeStore,
  userId: string,
  code: string,
  now: number,
): ClaimResult {
  const pairingCode = normalizePairingCode(code);
  const request = store.requestByCode(pairingCode);
  if (!request) return { error: "invalid_pairing_code" };
  if (request.expiresAt < now) {
    store.deleteRequest(request._id);
    return { error: "pairing_code_expired" };
  }
  if (request.claimedBy) return { error: "code_already_claimed" };

  const deviceId = request.deviceId || `device-${pairingCode}`;
  const deviceRows = store.dronesByDeviceId(deviceId);
  if (deviceRows.some((d) => d.userId !== userId)) {
    return { error: "device_owned_by_other" };
  }

  store.patchRequest(request._id, { claimedBy: userId, claimedAt: now });

  const existing = store.drones.find(
    (d) => d.userId === userId && d.deviceId === deviceId,
  );
  if (existing) {
    store.patchDrone(existing._id, { apiKey: request.apiKey || "" });
  } else {
    store.insertDrone({ userId, deviceId, apiKey: request.apiKey || "" });
  }
  return { error: null, deviceId, apiKey: request.apiKey || "" };
}

/**
 * Re-implements `claimPairingCodeAnon`: same guard ladder but the owner
 * marker is `browser:<id>` and re-claim by the SAME browser is allowed.
 */
function claimPairingCodeAnon(
  store: FakeStore,
  browserUserId: string,
  code: string,
  now: number,
): ClaimResult {
  const pairingCode = normalizePairingCode(code);
  const request = store.requestByCode(pairingCode);
  if (!request) return { error: "invalid_pairing_code" };
  if (request.expiresAt < now) {
    store.deleteRequest(request._id);
    return { error: "pairing_code_expired" };
  }
  const browserMarker = `browser:${browserUserId}`;
  if (request.claimedBy && request.claimedBy !== browserMarker) {
    return { error: "code_already_claimed" };
  }

  const deviceId = request.deviceId || `device-${pairingCode}`;
  const droneUserId = `browser:${browserUserId}`;
  const existingDrone = store.dronesByDeviceId(deviceId)[0];
  if (existingDrone && existingDrone.userId !== droneUserId) {
    return { error: "device_owned_by_other" };
  }

  store.patchRequest(request._id, { claimedBy: browserMarker, claimedAt: now });
  if (existingDrone) {
    store.patchDrone(existingDrone._id, { apiKey: request.apiKey || existingDrone.apiKey });
  } else {
    store.insertDrone({ userId: droneUserId, deviceId, apiKey: request.apiKey || "" });
  }
  return { error: null, deviceId, apiKey: request.apiKey || "" };
}

/**
 * Re-implements `preGenerateCode` for the explicit-code path: a live row
 * with the same code collides, an expired+unclaimed row is reclaimed.
 */
function preGenerateExplicitCode(
  store: FakeStore,
  userId: string,
  code: string,
  now: number,
): { code: string } {
  const pairingCode = normalizePairingCode(code);
  let finalCode = pairingCode;
  for (let attempt = 0; attempt < 8; attempt++) {
    const existing = store.requestByCode(finalCode);
    if (!existing) break;
    if (existing.expiresAt < now && !existing.claimedBy) {
      store.deleteRequest(existing._id);
      break;
    }
    // Explicit-code path: a live collision is fatal.
    throw new Error("Pairing code already exists");
  }
  store.insertRequest({
    pairingCode: finalCode,
    expiresAt: now + CODE_TTL_MS,
    createdBy: userId,
  });
  return { code: finalCode };
}

// ── Behavioral tests ───────────────────────────────────────

describe("normalizePairingCode", () => {
  it("uppercases and accepts a valid six-char safe code", () => {
    expect(normalizePairingCode("  abc234 ")).toBe("ABC234");
  });

  it("rejects codes containing ambiguous excluded characters (0, 1, I, O)", () => {
    for (const bad of ["ABC2I4", "ABC2O4", "ABC201", "ABCDE1"]) {
      expect(() => normalizePairingCode(bad)).toThrow();
    }
  });

  it("rejects wrong-length codes", () => {
    expect(() => normalizePairingCode("ABC23")).toThrow();
    expect(() => normalizePairingCode("ABC2345")).toThrow();
  });
});

describe("claimPairingCode (signed-in)", () => {
  const NOW = 1_700_000_000_000;

  it("claims a fresh code, marks it claimed, and creates the drone row", () => {
    const store = new FakeStore();
    store.insertRequest({
      pairingCode: "ABC234",
      expiresAt: NOW + CODE_TTL_MS,
      deviceId: "dev-1",
      apiKey: "key-1",
    });

    const result = claimPairingCode(store, "user-1", "abc234", NOW);
    expect(result).toEqual({ error: null, deviceId: "dev-1", apiKey: "key-1" });
    expect(store.requestByCode("ABC234")?.claimedBy).toBe("user-1");
    expect(store.dronesByDeviceId("dev-1")).toHaveLength(1);
  });

  it("returns invalid_pairing_code for an unknown code", () => {
    const store = new FakeStore();
    const result = claimPairingCode(store, "user-1", "ZZZ999", NOW);
    expect(result).toEqual({ error: "invalid_pairing_code" });
  });

  it("returns pairing_code_expired and deletes the stale row when past TTL", () => {
    const store = new FakeStore();
    store.insertRequest({
      pairingCode: "ABC234",
      expiresAt: NOW - 1,
      deviceId: "dev-1",
      apiKey: "key-1",
    });
    const result = claimPairingCode(store, "user-1", "ABC234", NOW);
    expect(result).toEqual({ error: "pairing_code_expired" });
    expect(store.requestByCode("ABC234")).toBeUndefined();
  });

  it("rejects a second claim of the same code (double-claim)", () => {
    const store = new FakeStore();
    store.insertRequest({
      pairingCode: "ABC234",
      expiresAt: NOW + CODE_TTL_MS,
      deviceId: "dev-1",
      apiKey: "key-1",
    });
    const first = claimPairingCode(store, "user-1", "ABC234", NOW);
    expect(first.error).toBeNull();
    const second = claimPairingCode(store, "user-2", "ABC234", NOW);
    expect(second).toEqual({ error: "code_already_claimed" });
  });

  it("blocks claiming a device a different account already owns", () => {
    const store = new FakeStore();
    store.insertRequest({
      pairingCode: "ABC234",
      expiresAt: NOW + CODE_TTL_MS,
      deviceId: "dev-shared",
      apiKey: "key-1",
    });
    store.insertDrone({ userId: "owner-A", deviceId: "dev-shared", apiKey: "old-key" });

    const result = claimPairingCode(store, "user-B", "ABC234", NOW);
    expect(result).toEqual({ error: "device_owned_by_other" });
    // The rejected attempt must not consume the code.
    expect(store.requestByCode("ABC234")?.claimedBy).toBeUndefined();
  });

  it("lets the same owner re-pair their own device (upsert, no new row)", () => {
    const store = new FakeStore();
    store.insertRequest({
      pairingCode: "ABC234",
      expiresAt: NOW + CODE_TTL_MS,
      deviceId: "dev-1",
      apiKey: "rotated-key",
    });
    store.insertDrone({ userId: "user-1", deviceId: "dev-1", apiKey: "old-key" });

    const result = claimPairingCode(store, "user-1", "ABC234", NOW);
    expect(result.error).toBeNull();
    expect(store.dronesByDeviceId("dev-1")).toHaveLength(1);
    expect(store.dronesByDeviceId("dev-1")[0].apiKey).toBe("rotated-key");
  });
});

describe("claimPairingCodeAnon", () => {
  const NOW = 1_700_000_000_000;

  it("claims a fresh code under a browser marker", () => {
    const store = new FakeStore();
    store.insertRequest({
      pairingCode: "ABC234",
      expiresAt: NOW + CODE_TTL_MS,
      deviceId: "dev-1",
      apiKey: "key-1",
    });
    const result = claimPairingCodeAnon(store, "browser-uuid-1", "ABC234", NOW);
    expect(result.error).toBeNull();
    expect(store.requestByCode("ABC234")?.claimedBy).toBe("browser:browser-uuid-1");
    expect(store.dronesByDeviceId("dev-1")[0].userId).toBe("browser:browser-uuid-1");
  });

  it("expires past-TTL codes", () => {
    const store = new FakeStore();
    store.insertRequest({ pairingCode: "ABC234", expiresAt: NOW - 1 });
    const result = claimPairingCodeAnon(store, "browser-uuid-1", "ABC234", NOW);
    expect(result).toEqual({ error: "pairing_code_expired" });
  });

  it("rejects a code already claimed by a DIFFERENT browser", () => {
    const store = new FakeStore();
    store.insertRequest({
      pairingCode: "ABC234",
      expiresAt: NOW + CODE_TTL_MS,
      deviceId: "dev-1",
      claimedBy: "browser:other-browser",
    });
    const result = claimPairingCodeAnon(store, "browser-uuid-1", "ABC234", NOW);
    expect(result).toEqual({ error: "code_already_claimed" });
  });

  it("allows the SAME browser to re-claim its own code", () => {
    const store = new FakeStore();
    store.insertRequest({
      pairingCode: "ABC234",
      expiresAt: NOW + CODE_TTL_MS,
      deviceId: "dev-1",
      apiKey: "key-1",
      claimedBy: "browser:browser-uuid-1",
    });
    const result = claimPairingCodeAnon(store, "browser-uuid-1", "ABC234", NOW);
    expect(result.error).toBeNull();
  });

  it("blocks a device already owned by another account/browser", () => {
    const store = new FakeStore();
    store.insertRequest({
      pairingCode: "ABC234",
      expiresAt: NOW + CODE_TTL_MS,
      deviceId: "dev-shared",
      apiKey: "key-1",
    });
    store.insertDrone({ userId: "real-account-id", deviceId: "dev-shared", apiKey: "old" });
    const result = claimPairingCodeAnon(store, "browser-uuid-1", "ABC234", NOW);
    expect(result).toEqual({ error: "device_owned_by_other" });
    expect(store.requestByCode("ABC234")?.claimedBy).toBeUndefined();
  });
});

describe("preGenerateCode (explicit code)", () => {
  const NOW = 1_700_000_000_000;

  it("inserts a request with a fresh TTL when the code is free", () => {
    const store = new FakeStore();
    const result = preGenerateExplicitCode(store, "user-1", "ABC234", NOW);
    expect(result.code).toBe("ABC234");
    const row = store.requestByCode("ABC234");
    expect(row?.createdBy).toBe("user-1");
    expect(row?.expiresAt).toBe(NOW + CODE_TTL_MS);
  });

  it("reclaims an expired, unclaimed code with the same value", () => {
    const store = new FakeStore();
    store.insertRequest({ pairingCode: "ABC234", expiresAt: NOW - 1 });
    const result = preGenerateExplicitCode(store, "user-1", "ABC234", NOW);
    expect(result.code).toBe("ABC234");
    // The stale row is replaced; exactly one live request remains.
    const live = store.requests.filter((r) => r.pairingCode === "ABC234");
    expect(live).toHaveLength(1);
    expect(live[0].createdBy).toBe("user-1");
  });

  it("rejects an explicit code that collides with a live request", () => {
    const store = new FakeStore();
    store.insertRequest({
      pairingCode: "ABC234",
      expiresAt: NOW + CODE_TTL_MS,
      createdBy: "user-9",
    });
    expect(() => preGenerateExplicitCode(store, "user-1", "ABC234", NOW)).toThrow(
      "Pairing code already exists",
    );
  });

  it("rejects an explicit code that collides with a claimed-but-unexpired request", () => {
    const store = new FakeStore();
    store.insertRequest({
      pairingCode: "ABC234",
      expiresAt: NOW + CODE_TTL_MS,
      createdBy: "user-9",
      claimedBy: "user-9",
    });
    expect(() => preGenerateExplicitCode(store, "user-1", "ABC234", NOW)).toThrow(
      "Pairing code already exists",
    );
  });
});
