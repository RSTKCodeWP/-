/**
 * @module cmdSigningEvents
 * @description Append-only audit log for MAVLink signing events.
 *
 * Every user-triggered signing action emits an event here. Compliance
 * exports, operator history, and "what changed last" diagnostics read
 * this table. Rows are scoped to the authenticated user; another user
 * on the same drone cannot read or write them.
 *
 * **Log discipline:** keyHex is NEVER stored in this table. Only the
 * 8-char keyId fingerprint. Any attempt to pass keyHex through `append`
 * is rejected at the mutation boundary.
 *
 * **Rate limiting:** not implemented in v1. Every call is driven by an
 * operator action (no GCS loops), and Convex sits behind HMAC-authed
 * user identity so an abusive client already has bigger leverage
 * elsewhere. v1.1 may add a sliding-window limiter keyed by userId.
 *
 * @license GPL-3.0-only
 */

import { v } from "convex/values";
import { mutation, query } from "./_generated/server";
import { getAuthUserId } from "@convex-dev/auth/server";

const EVENT_TYPES = [
  "enrollment",
  "rotation",
  "import",
  "export",
  "disable",
  "cloud_sync_on",
  "cloud_sync_off",
  "clear_fc",
  "key_mismatch_detected",
  "user_purge_on_signout",
  "fc_rejected_enrollment",
  "require_on",
  "require_off",
] as const;

type EventType = (typeof EVENT_TYPES)[number];

// ──────────────────────────────────────────────────────────────
// Queries
// ──────────────────────────────────────────────────────────────

/**
 * Return the most recent events for a single drone, ordered newest
 * first. Capped at 50 rows. UI renders this in the History disclosure
 * inside the Signing panel.
 */
export const listForDrone = query({
  args: { droneId: v.string(), limit: v.optional(v.number()) },
  handler: async (ctx, { droneId, limit }) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) return [];
    const cap = Math.min(limit ?? 50, 200);
    const rows = await ctx.db
      .query("cmd_signingEvents")
      .withIndex("by_user_drone", (q) =>
        q.eq("userId", userId).eq("droneId", droneId),
      )
      .order("desc")
      .take(cap);
    return rows;
  },
});

/**
 * Return every signing event for the authenticated user across all
 * drones, newest first. Feeds future fleet-wide audit views; the Signing
 * panel uses listForDrone instead.
 */
export const listMine = query({
  args: { limit: v.optional(v.number()) },
  handler: async (ctx, { limit }) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) return [];
    const cap = Math.min(limit ?? 200, 500);
    return await ctx.db
      .query("cmd_signingEvents")
      .withIndex("by_user_created", (q) => q.eq("userId", userId))
      .order("desc")
      .take(cap);
  },
});

// ──────────────────────────────────────────────────────────────
// Mutations
// ──────────────────────────────────────────────────────────────

/**
 * Append a single event. Called by the GCS after every user-triggered
 * signing action. Defensive validation:
 *   - eventType must be in the enum.
 *   - keyIdOld and keyIdNew, when present, must be 8 hex chars.
 *   - deviceFingerprint must be a short opaque hash, never a userId
 *     or any PII.
 */
export const append = mutation({
  args: {
    droneId: v.string(),
    eventType: v.string(),
    keyIdOld: v.optional(v.string()),
    keyIdNew: v.optional(v.string()),
    deviceFingerprint: v.string(),
  },
  handler: async (ctx, args) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) throw new Error("unauthenticated");

    if (!EVENT_TYPES.includes(args.eventType as EventType)) {
      throw new Error(`unknown eventType: ${args.eventType}`);
    }
    const hex8 = /^[0-9a-fA-F]{8}$/;
    if (args.keyIdOld && !hex8.test(args.keyIdOld)) {
      throw new Error("keyIdOld must be 8 hex chars");
    }
    if (args.keyIdNew && !hex8.test(args.keyIdNew)) {
      throw new Error("keyIdNew must be 8 hex chars");
    }
    if (args.deviceFingerprint.length < 4 || args.deviceFingerprint.length > 64) {
      throw new Error("deviceFingerprint must be 4-64 chars");
    }

    const id = await ctx.db.insert("cmd_signingEvents", {
      userId,
      droneId: args.droneId,
      eventType: args.eventType as EventType,
      keyIdOld: args.keyIdOld,
      keyIdNew: args.keyIdNew,
      deviceFingerprint: args.deviceFingerprint,
      createdAt: Date.now(),
    });
    return { _id: id };
  },
});
