/**
 * @module operatorHmacSecrets
 * @description Per-operator HMAC secret used by the cloud issuer
 * to sign short-lived capability tokens for the GCS to agent plugin
 * RPC bridge.
 *
 * Secrets rotate every 30 days. The previous secret is retained in
 * `previousSecretBase64` so tokens minted just before a rotation
 * stay valid until they expire (TTL bounded by the capability-token
 * action; see `cmdPluginCapabilityTokens.mintToken`).
 *
 * The secret is exposed to the operator's GCS via `getMyCurrent`
 * so the GCS can verify tokens locally when running in offline /
 * LAN-direct mode. Plugin code never reads either current or
 * previous secrets directly — only the cloud issuer signs, and
 * only the agent verifies.
 *
 * Crypto: uses Web Crypto (`crypto.getRandomValues`), no "use node"
 * directive needed.
 *
 * @license GPL-3.0-only
 */

import { v } from "convex/values";
import {
  internalAction,
  internalMutation,
  internalQuery,
  query,
} from "./_generated/server";
import { getAuthUserId } from "@convex-dev/auth/server";
import { internal } from "./_generated/api";
import type { Doc } from "./_generated/dataModel";

/** 30 days; matches the rotation cadence in the spec. */
const ROTATION_PERIOD_MS = 30 * 24 * 60 * 60 * 1000;
/** 32 random bytes = 256-bit HMAC-SHA256 key. */
const SECRET_BYTE_LENGTH = 32;

// ──────────────────────────────────────────────────────────────
// Helpers
// ──────────────────────────────────────────────────────────────

function generateSecretBase64(): string {
  const bytes = new Uint8Array(SECRET_BYTE_LENGTH);
  crypto.getRandomValues(bytes);
  // btoa handles binary strings; build one byte at a time.
  let bin = "";
  for (let i = 0; i < bytes.length; i += 1) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
}

// ──────────────────────────────────────────────────────────────
// Actions
// ──────────────────────────────────────────────────────────────

/**
 * Return the current HMAC secret for `userId`, minting a fresh one
 * on first use and rotating after `ROTATION_PERIOD_MS` has elapsed
 * since the last rotation. Always returns the secret as a
 * base64-encoded string.
 *
 * This is the only entry point the capability-token issuer uses; it
 * is an action because rotation writes to the table and needs to run
 * outside the read-only query path.
 */
export const getOrCreateCurrent = internalAction({
  args: { userId: v.string() },
  handler: async (ctx, { userId }): Promise<string> => {
    const existing = await ctx.runQuery(
      internal.operatorHmacSecrets.getCurrentInternal,
      { userId },
    );
    if (existing && Date.now() - existing.rotatedAt < ROTATION_PERIOD_MS) {
      return existing.secretBase64;
    }
    const newSecret = generateSecretBase64();
    await ctx.runMutation(internal.operatorHmacSecrets.rotate, {
      userId,
      newSecretBase64: newSecret,
      previousSecretBase64: existing?.secretBase64,
    });
    return newSecret;
  },
});

// ──────────────────────────────────────────────────────────────
// Internal queries / mutations
// ──────────────────────────────────────────────────────────────

/** Read the current row for `userId`. Internal because the secret
 * material is never exposed to public queries beyond
 * `getMyCurrent`, which gates on auth. */
export const getCurrentInternal = internalQuery({
  args: { userId: v.string() },
  handler: async (
    ctx,
    { userId },
  ): Promise<Doc<"operator_hmac_secrets"> | null> => {
    return await ctx.db
      .query("operator_hmac_secrets")
      .withIndex("by_user", (q) => q.eq("userId", userId))
      .first();
  },
});

/** Insert or rotate the secret row for `userId`. */
export const rotate = internalMutation({
  args: {
    userId: v.string(),
    newSecretBase64: v.string(),
    previousSecretBase64: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("operator_hmac_secrets")
      .withIndex("by_user", (q) => q.eq("userId", args.userId))
      .first();
    const patch = {
      userId: args.userId,
      secretBase64: args.newSecretBase64,
      rotatedAt: Date.now(),
      previousSecretBase64: args.previousSecretBase64,
    };
    if (existing) {
      await ctx.db.patch(existing._id, patch);
      return existing._id;
    }
    return await ctx.db.insert("operator_hmac_secrets", patch);
  },
});

// ──────────────────────────────────────────────────────────────
// Public queries
// ──────────────────────────────────────────────────────────────

/**
 * Return the current HMAC secret for the authenticated user, plus
 * the previous secret if one exists. The GCS uses both to verify
 * locally-signed tokens during the rotation overlap window. The
 * secret is gated by auth — only the owning operator can read it.
 */
export const getMyCurrent = query({
  args: {},
  handler: async (
    ctx,
  ): Promise<{
    secretBase64: string;
    previousSecretBase64?: string;
    rotatedAt: number;
  } | null> => {
    const userId = await getAuthUserId(ctx);
    if (!userId) return null;
    const row = await ctx.db
      .query("operator_hmac_secrets")
      .withIndex("by_user", (q) => q.eq("userId", userId))
      .first();
    if (!row) return null;
    return {
      secretBase64: row.secretBase64,
      previousSecretBase64: row.previousSecretBase64,
      rotatedAt: row.rotatedAt,
    };
  },
});
