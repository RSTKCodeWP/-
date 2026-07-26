/**
 * @module cmdPairing
 * @description Convex functions for the ADOS drone pairing system.
 * Supports two flows:
 * 1. Agent-initiated: agent generates code → user enters code in GCS
 * 2. User-initiated: user pre-generates code → agent uses it during install
 * @license GPL-3.0-only
 */

import { v } from "convex/values";
import { mutation, query, internalMutation } from "./_generated/server";
import { internal } from "./_generated/api";
import { getAuthUserId } from "@convex-dev/auth/server";

const SAFE_CHARSET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789";
const CODE_LENGTH = 6;
const CODE_TTL_MS = 15 * 60 * 1000; // 15 minutes
const PAIRING_CODE_RE = new RegExp(
  `^[${SAFE_CHARSET}]{${CODE_LENGTH}}$`,
);
const MAX_DEVICE_ID_LENGTH = 96;
const MAX_LABEL_LENGTH = 128;
const MAX_API_KEY_LENGTH = 256;

function normalizePairingCode(code: string): string {
  const normalized = code.trim().toUpperCase();
  if (!PAIRING_CODE_RE.test(normalized)) {
    throw new Error("Pairing code must be six safe uppercase characters");
  }
  return normalized;
}

function generatePairingCode(): string {
  // The pairing code is a bearer credential — claiming it returns the
  // agent's API key — so it must be unpredictable. Draw from a CSPRNG and
  // rejection-sample to avoid modulo bias across the 31-character charset.
  const limit = Math.floor(256 / SAFE_CHARSET.length) * SAFE_CHARSET.length;
  let pairingCode = "";
  while (pairingCode.length < CODE_LENGTH) {
    const bytes = crypto.getRandomValues(new Uint8Array(CODE_LENGTH));
    for (let i = 0; i < bytes.length && pairingCode.length < CODE_LENGTH; i++) {
      if (bytes[i] < limit) {
        pairingCode += SAFE_CHARSET[bytes[i] % SAFE_CHARSET.length];
      }
    }
  }
  return pairingCode;
}

function requireBoundedString(value: string, name: string, max: number): string {
  const trimmed = value.trim();
  if (!trimmed) throw new Error(`${name} required`);
  if (trimmed.length > max) throw new Error(`${name} too long`);
  return trimmed;
}

function optionalBoundedString(
  value: string | undefined,
  name: string,
  max: number,
): string | undefined {
  if (value === undefined) return undefined;
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  if (trimmed.length > max) throw new Error(`${name} too long`);
  return trimmed;
}

/** Anonymous code-pair: browser identifies itself by a browserUserId
 *  (the per-browser UUID from browser-identity-store), no Convex
 *  account required. Returns the agent identity (hostname, apiKey,
 *  deviceId, name) the operator's browser then stores in
 *  local-nodes-store the same way the LAN-direct hostname pair does.
 *
 *  Trade-off vs the signed-in `claimPairingCode`: this path does NOT
 *  write a `cmd_drones` row. The drone is LAN-only for this browser
 *  until the operator signs in and migrates (out of scope today).
 *  In return, the "no account required" promise extends to the
 *  short-code path, not just the hostname path.
 */
export const claimPairingCodeAnon = mutation({
  args: { code: v.string(), browserUserId: v.string() },
  handler: async (ctx, { code, browserUserId }) => {
    const pairingCode = normalizePairingCode(code);
    const browserOwner = requireBoundedString(
      browserUserId,
      "browserUserId",
      MAX_LABEL_LENGTH,
    );

    const request = await ctx.db
      .query("cmd_pairingRequests")
      .withIndex("by_pairingCode", (q) => q.eq("pairingCode", pairingCode))
      .first();

    if (!request) return { error: "invalid_pairing_code" as const };
    if (request.expiresAt < Date.now()) {
      await ctx.db.delete(request._id);
      return { error: "pairing_code_expired" as const };
    }
    const browserMarker = `browser:${browserOwner}`;
    if (request.claimedBy && request.claimedBy !== browserMarker) {
      return { error: "code_already_claimed" as const };
    }

    // Anon-paired drones still need a cmd_drones row so the agent's
    // /agent/status heartbeat can validate its apiKey. Without this the
    // heartbeat handler 401s every 5 s and cloud relay never delivers
    // telemetry — fine for LAN-direct on HTTP origins but a dead end on
    // HTTPS (mixed-content blocks the LAN path). The browser:UUID
    // marker stays out of the way of real Convex auth user ids; the
    // listMyDrones query filters on getAuthUserId() which never returns
    // a "browser:" prefix, so signed-in users don't see anon drones.
    const deviceId = request.deviceId || `device-${pairingCode}`;
    const droneUserId = `browser:${browserOwner}`;
    const existingDrone = await ctx.db
      .query("cmd_drones")
      .withIndex("by_deviceId", (q) => q.eq("deviceId", deviceId))
      .first();

    // Single-owner guard: an anon claim may re-pair a device this same
    // browser already owns, but must not reassign one owned by another
    // account or a different browser. Checked before the claim patch so a
    // rejected attempt never consumes the code. A genuine owner who
    // changed browsers recovers by unpairing on the device and re-pairing.
    if (existingDrone && existingDrone.userId !== droneUserId) {
      return { error: "device_owned_by_other" as const };
    }

    await ctx.db.patch(request._id, {
      claimedBy: browserMarker,
      claimedAt: Date.now(),
    });

    if (existingDrone) {
      await ctx.db.patch(existingDrone._id, {
        userId: droneUserId,
        apiKey: request.apiKey || existingDrone.apiKey,
        agentVersion: request.agentVersion ?? existingDrone.agentVersion,
        board: request.board ?? existingDrone.board,
        tier: request.tier ?? existingDrone.tier,
        os: request.os ?? existingDrone.os,
        mdnsHost: request.mdnsHost ?? existingDrone.mdnsHost,
        lastIp: request.localIp ?? existingDrone.lastIp,
        lastSeen: Date.now(),
        pairedAt: Date.now(),
      });
    } else {
      await ctx.db.insert("cmd_drones", {
        userId: droneUserId,
        deviceId,
        name: request.agentName || `Drone ${pairingCode}`,
        apiKey: request.apiKey || "",
        agentVersion: request.agentVersion,
        board: request.board,
        tier: request.tier,
        os: request.os,
        mdnsHost: request.mdnsHost,
        lastIp: request.localIp,
        lastSeen: Date.now(),
        fcConnected: false,
        pairedAt: Date.now(),
      });
    }

    return {
      error: null,
      deviceId,
      name: request.agentName || `Drone ${pairingCode}`,
      apiKey: request.apiKey || "",
      mdnsHost: request.mdnsHost,
      localIp: request.localIp,
      board: request.board,
      agentVersion: request.agentVersion,
    };
  },
});

/** User claims a pairing code (enters code displayed on agent terminal). */
export const claimPairingCode = mutation({
  args: { code: v.string() },
  handler: async (ctx, { code }) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) throw new Error("Not authenticated");
    const pairingCode = normalizePairingCode(code);

    const request = await ctx.db
      .query("cmd_pairingRequests")
      .withIndex("by_pairingCode", (q) =>
        q.eq("pairingCode", pairingCode)
      )
      .first();

    if (!request) return { error: "invalid_pairing_code" as const };
    if (request.expiresAt < Date.now()) {
      await ctx.db.delete(request._id);
      return { error: "pairing_code_expired" as const };
    }
    if (request.claimedBy) return { error: "code_already_claimed" as const };

    // Single-owner guard: refuse to claim a device another account already
    // owns instead of silently creating a second owner row (with its own
    // API key) for the same hardware. The legitimate re-pair-to-a-new-
    // account path is for the current owner to release it first
    // (wipePairStateForOwnedDevice). Checked before the claim patch so a
    // rejected attempt never marks the code consumed.
    const deviceId = request.deviceId || `device-${pairingCode}`;
    const deviceRows = await ctx.db
      .query("cmd_drones")
      .withIndex("by_deviceId", (q) => q.eq("deviceId", deviceId))
      .collect();
    if (deviceRows.some((d) => d.userId !== userId)) {
      return { error: "device_owned_by_other" as const };
    }

    // Mark as claimed
    await ctx.db.patch(request._id, {
      claimedBy: userId,
      claimedAt: Date.now(),
    });

    // Upsert: update existing drone record if same user + device
    const existingDrone = await ctx.db
      .query("cmd_drones")
      .withIndex("by_userId", (q) => q.eq("userId", userId))
      .filter((q) => q.eq(q.field("deviceId"), deviceId))
      .first();

    let droneId;
    if (existingDrone) {
      await ctx.db.patch(existingDrone._id, {
        apiKey: request.apiKey || "",
        agentVersion: request.agentVersion,
        board: request.board,
        tier: request.tier,
        os: request.os,
        mdnsHost: request.mdnsHost,
        lastIp: request.localIp,
        lastSeen: Date.now(),
        pairedAt: Date.now(),
      });
      droneId = existingDrone._id;
    } else {
      droneId = await ctx.db.insert("cmd_drones", {
        userId,
        deviceId,
        name: request.agentName || `Drone ${pairingCode}`,
        apiKey: request.apiKey || "",
        agentVersion: request.agentVersion,
        board: request.board,
        tier: request.tier,
        os: request.os,
        mdnsHost: request.mdnsHost,
        lastIp: request.localIp,
        lastSeen: Date.now(),
        fcConnected: false,
        pairedAt: Date.now(),
      });
    }

    return {
      error: null,
      droneId,
      apiKey: request.apiKey || "",
      mdnsHost: request.mdnsHost,
      localIp: request.localIp,
      deviceId,
      name: existingDrone?.name || request.agentName,
    };
  },
});

/** User pre-generates a pairing code (for zero-touch install). */
export const preGenerateCode = mutation({
  args: { code: v.optional(v.string()) },
  handler: async (ctx, { code }) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) throw new Error("Not authenticated");

    let pairingCode = code ? normalizePairingCode(code) : "";
    for (let attempt = 0; attempt < 8; attempt++) {
      if (!pairingCode) pairingCode = generatePairingCode();
      const existing = await ctx.db
        .query("cmd_pairingRequests")
        .withIndex("by_pairingCode", (q) => q.eq("pairingCode", pairingCode))
        .first();
      if (!existing) break;
      if (existing.expiresAt < Date.now() && !existing.claimedBy) {
        await ctx.db.delete(existing._id);
        break;
      }
      if (code) throw new Error("Pairing code already exists");
      pairingCode = "";
    }

    if (!pairingCode) {
      throw new Error("Could not allocate pairing code");
    }

    const requestId = await ctx.db.insert("cmd_pairingRequests", {
      pairingCode,
      expiresAt: Date.now() + CODE_TTL_MS,
      createdBy: userId,
    });

    return { requestId, code: pairingCode };
  },
});

/**
 * Agent polls to check if its code was claimed.
 * No auth required — uses deviceId lookup.
 */
export const getPairingStatus = query({
  args: { deviceId: v.string() },
  handler: async (ctx, { deviceId }) => {
    const request = await ctx.db
      .query("cmd_pairingRequests")
      .withIndex("by_deviceId", (q) => q.eq("deviceId", deviceId))
      .first();

    if (!request) return { registered: false };

    return {
      registered: true,
      claimed: !!request.claimedBy,
      claimedAt: request.claimedAt,
    };
  },
});

/** User sees their pre-generated (unclaimed) codes. */
export const getMyPendingCodes = query({
  args: {},
  handler: async (ctx) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) return [];
    return await ctx.db
      .query("cmd_pairingRequests")
      .withIndex("by_createdBy", (q) => q.eq("createdBy", userId))
      .filter((q) => q.eq(q.field("claimedBy"), undefined))
      .collect();
  },
});

/**
 * Called by HTTP handler when agent registers its pairing request.
 * No user auth — this is the agent-side of the pairing flow.
 * Handles upsert and auto-matching with pre-generated codes.
 */
export const registerAgent = mutation({
  args: {
    deviceId: v.string(),
    pairingCode: v.string(),
    apiKey: v.optional(v.string()),
    name: v.optional(v.string()),
    version: v.optional(v.string()),
    board: v.optional(v.string()),
    tier: v.optional(v.number()),
    os: v.optional(v.string()),
    mdnsHost: v.optional(v.string()),
    localIp: v.optional(v.string()),
    // Agent-authoritative pairing-code expiry (epoch seconds). Mirrors
    // the timer the agent's local wizard is showing the operator so
    // the cloud-side UI countdown matches the physical device.
    pairingCodeExpiresAt: v.optional(v.number()),
  },
  handler: async (ctx, args) => {
    const now = Date.now();
    const deviceId = requireBoundedString(
      args.deviceId,
      "deviceId",
      MAX_DEVICE_ID_LENGTH,
    );
    const pairingCode = normalizePairingCode(args.pairingCode);
    const name = optionalBoundedString(args.name, "name", MAX_LABEL_LENGTH);
    const version = optionalBoundedString(
      args.version,
      "version",
      MAX_LABEL_LENGTH,
    );
    const board = optionalBoundedString(args.board, "board", MAX_LABEL_LENGTH);
    const os = optionalBoundedString(args.os, "os", MAX_LABEL_LENGTH);
    const apiKey = optionalBoundedString(args.apiKey, "apiKey", MAX_API_KEY_LENGTH);
    const mdnsHost = optionalBoundedString(
      args.mdnsHost,
      "mdnsHost",
      MAX_LABEL_LENGTH,
    );
    const localIp = optionalBoundedString(args.localIp, "localIp", MAX_LABEL_LENGTH);
    if (
      args.tier !== undefined &&
      (!Number.isInteger(args.tier) || args.tier < 0 || args.tier > 10)
    ) {
      throw new Error("tier out of range");
    }
    // Validate the agent-side expiry. Reject negatives or absurd values
    // so a malformed beacon can never poison the row. Epoch seconds
    // beyond year 2100 are obvious noise.
    let pairingCodeExpiresAt: number | undefined = args.pairingCodeExpiresAt;
    if (pairingCodeExpiresAt !== undefined) {
      if (
        !Number.isFinite(pairingCodeExpiresAt) ||
        pairingCodeExpiresAt < 0 ||
        pairingCodeExpiresAt > 4_102_444_800
      ) {
        pairingCodeExpiresAt = undefined;
      }
    }

    // Re-register the same device/code without letting a mismatched public
    // request delete an active pending pairing window.
    const existing = await ctx.db
      .query("cmd_pairingRequests")
      .withIndex("by_deviceId", (q) => q.eq("deviceId", deviceId))
      .first();
    if (existing) {
      if (existing.claimedBy) {
        // Surface the owner so the agent's beacon-claim handler can
        // record the real claimant (signed-in user id, or "browser:UUID"
        // for anon claims) instead of defaulting to the literal "cloud".
        return { alreadyClaimed: true, userId: existing.claimedBy };
      }
      if (existing.expiresAt < now) {
        await ctx.db.delete(existing._id);
      } else if (existing.pairingCode !== pairingCode) {
        return { error: "device_pending_with_different_code" };
      } else {
        await ctx.db.patch(existing._id, {
          agentName: name,
          agentVersion: version,
          board,
          tier: args.tier,
          os,
          apiKey,
          mdnsHost,
          localIp,
          expiresAt: now + CODE_TTL_MS,
          ...(pairingCodeExpiresAt !== undefined ? { pairingCodeExpiresAt } : {}),
        });
        return { registered: true };
      }
    }

    // Check if a pre-generated code matches (zero-touch flow)
    const preGenerated = await ctx.db
      .query("cmd_pairingRequests")
      .withIndex("by_pairingCode", (q) =>
        q.eq("pairingCode", pairingCode)
      )
      .first();
    if (preGenerated && preGenerated.createdBy && !preGenerated.claimedBy) {
      if (preGenerated.expiresAt < now) {
        await ctx.db.delete(preGenerated._id);
        return { error: "pairing_code_expired" };
      }
      // Auto-match: pre-generated code found, auto-claim it
      await ctx.db.patch(preGenerated._id, {
        deviceId,
        agentName: name,
        agentVersion: version,
        board,
        tier: args.tier,
        os,
        apiKey,
        mdnsHost,
        localIp,
        claimedBy: preGenerated.createdBy!,
        claimedAt: now,
      });
      // Upsert drone record
      const ownerId = preGenerated.createdBy!;
      const existingDrone = await ctx.db
        .query("cmd_drones")
        .withIndex("by_userId", (q) => q.eq("userId", ownerId))
        .filter((q) => q.eq(q.field("deviceId"), deviceId))
        .first();

      if (existingDrone) {
        await ctx.db.patch(existingDrone._id, {
          apiKey: apiKey || "",
          agentVersion: version,
          board,
          tier: args.tier,
          os,
          mdnsHost,
          lastIp: localIp,
          lastSeen: now,
          pairedAt: now,
        });
      } else {
        await ctx.db.insert("cmd_drones", {
          userId: ownerId,
          deviceId,
          name: name || `Drone ${pairingCode}`,
          apiKey: apiKey || "",
          agentVersion: version,
          board,
          tier: args.tier,
          os,
          mdnsHost,
          lastIp: localIp,
          lastSeen: now,
          fcConnected: false,
          pairedAt: now,
        });
      }
      return { autoMatched: true, userId: ownerId };
    }

    // Insert new pairing request
    await ctx.db.insert("cmd_pairingRequests", {
      deviceId,
      pairingCode,
      agentName: name,
      agentVersion: version,
      board,
      tier: args.tier,
      os,
      apiKey,
      mdnsHost,
      localIp,
      expiresAt: now + CODE_TTL_MS,
      ...(pairingCodeExpiresAt !== undefined ? { pairingCodeExpiresAt } : {}),
    });

    return { registered: true };
  },
});

// Upper bound on rows deleted per sweep so one cron tick stays within
// transaction limits even if a large backlog accrued. A 15-minute cron drains
// the rest on the next ticks.
const CLEAN_EXPIRED_BATCH = 256;

/**
 * Cron job: clean expired pairing requests.
 *
 * Internal (cron-only): a public no-auth mutation let any client trigger the
 * scan on demand. The query walks the `by_expiresAt` index range below `now`
 * instead of a full-table `.filter().collect()`, and the batch is bounded so
 * a backlog cannot blow the per-call limits.
 */
export const cleanExpiredRequests = internalMutation({
  args: {},
  handler: async (ctx) => {
    const now = Date.now();
    const expired = await ctx.db
      .query("cmd_pairingRequests")
      .withIndex("by_expiresAt", (q) => q.lt("expiresAt", now))
      .take(CLEAN_EXPIRED_BATCH);
    for (const req of expired) {
      await ctx.db.delete(req._id);
    }
    return { deleted: expired.length };
  },
});

/**
 * Operator-driven recovery: wipe pair state for a single device the
 * signed-in user owns (or no owner at all, see below). Delegates the
 * actual delete sweep to the internal mutation so the wipe surface
 * stays one code path.
 *
 * Ownership rules: if a cmd_drones row exists for this deviceId, the
 * caller must be its owner. If no row exists (the device was paired
 * to a different account, the row never existed, or the pairing
 * request is stale and orphan), the wipe is ALSO allowed. This lets
 * the operator clean up local-only broken state where the cloud row
 * was already gone but the pairing request lingered, or where the
 * device was previously claimed by another browser the operator no
 * longer controls.
 */
export const wipePairStateForOwnedDevice = mutation({
  args: { deviceId: v.string() },
  // Explicit handler return type breaks the self-referential typing
  // loop introduced by the `internal.cmdPairing.wipeByDeviceIds` call
  // below — Convex's generated `internal` API depends on the type of
  // every export in this file, including ours.
  handler: async (
    ctx,
    { deviceId },
  ): Promise<{
    removedRequests: number;
    removedDrones: number;
    removedStatus: number;
  }> => {
    const userId = await getAuthUserId(ctx);
    if (!userId) throw new Error("Not authenticated");

    const existingDrone = await ctx.db
      .query("cmd_drones")
      .withIndex("by_deviceId", (q) => q.eq("deviceId", deviceId))
      .first();
    if (existingDrone && existingDrone.userId !== userId) {
      throw new Error("Device is owned by a different account");
    }

    return await ctx.runMutation(internal.cmdPairing.wipeByDeviceIds, {
      deviceIds: [deviceId],
    });
  },
});

/** Admin recovery: wipe pair state for specific device IDs across all relevant tables. */
export const wipeByDeviceIds = internalMutation({
  args: { deviceIds: v.array(v.string()) },
  handler: async (ctx, { deviceIds }) => {
    let removedRequests = 0;
    let removedDrones = 0;
    let removedStatus = 0;
    for (const deviceId of deviceIds) {
      const reqs = await ctx.db
        .query("cmd_pairingRequests")
        .withIndex("by_deviceId", (q) => q.eq("deviceId", deviceId))
        .collect();
      for (const r of reqs) {
        await ctx.db.delete(r._id);
        removedRequests++;
      }
      const drones = await ctx.db
        .query("cmd_drones")
        .withIndex("by_deviceId", (q) => q.eq("deviceId", deviceId))
        .collect();
      for (const d of drones) {
        await ctx.db.delete(d._id);
        removedDrones++;
      }
      const statuses = await ctx.db
        .query("cmd_droneStatus")
        .withIndex("by_deviceId", (q) => q.eq("deviceId", deviceId))
        .collect();
      for (const s of statuses) {
        await ctx.db.delete(s._id);
        removedStatus++;
      }
    }
    return { removedRequests, removedDrones, removedStatus };
  },
});
