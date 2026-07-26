/**
 * @module cmdMcpReachDb
 * @description Internal DB functions for the ADOS MCP reach surface. They are
 * split out from `cmdMcpReach` so the reach ACTIONS can reference them via
 * `internal.cmdMcpReachDb.*` without the same-module circular type inference that
 * an action-calling-its-own-module's-internal-function triggers.
 *
 * These are `internal*` (never client-callable); the caller in `cmdMcpReach` has
 * already verified the credential and resolved the owning `userId`, so each here
 * takes `userId` as a trusted argument and scopes every read/write to it.
 *
 * @license GPL-3.0-only
 */

import { v } from "convex/values";
import { internalMutation, internalQuery } from "./_generated/server";
import { relayCommandValidator } from "./commandVocabulary";

export const lookupByHash = internalQuery({
  args: { tokenHash: v.string() },
  handler: async (ctx, { tokenHash }) => {
    return await ctx.db
      .query("cmd_mcpTokens")
      .withIndex("by_tokenHash", (q) => q.eq("tokenHash", tokenHash))
      .first();
  },
});

export const touchLastUsed = internalMutation({
  args: { id: v.id("cmd_mcpTokens") },
  handler: async (ctx, { id }) => {
    await ctx.db.patch(id, { lastUsedAt: Date.now() });
  },
});

export const listNodesForUser = internalQuery({
  args: { userId: v.string() },
  handler: async (ctx, { userId }) => {
    const drones = await ctx.db
      .query("cmd_drones")
      .withIndex("by_userId", (q) => q.eq("userId", userId))
      .collect();
    return await Promise.all(
      drones.map(async (drone) => {
        const status = await ctx.db
          .query("cmd_droneStatus")
          .withIndex("by_deviceId", (q) => q.eq("deviceId", drone.deviceId))
          .first();
        return {
          drone: {
            deviceId: drone.deviceId,
            name: drone.name,
            agentVersion: drone.agentVersion,
            board: drone.board,
            tier: drone.tier,
            os: drone.os,
            mdnsHost: drone.mdnsHost,
            lastIp: drone.lastIp,
            lastSeen: drone.lastSeen,
            fcConnected: drone.fcConnected,
          },
          status,
        };
      }),
    );
  },
});

export const getStatusForUser = internalQuery({
  args: { userId: v.string(), deviceId: v.string() },
  handler: async (ctx, { userId, deviceId }) => {
    const drone = await ctx.db
      .query("cmd_drones")
      .withIndex("by_deviceId", (q) => q.eq("deviceId", deviceId))
      .first();
    if (!drone || drone.userId !== userId) throw new Error("Not found");
    return await ctx.db
      .query("cmd_droneStatus")
      .withIndex("by_deviceId", (q) => q.eq("deviceId", deviceId))
      .first();
  },
});

export const enqueueForUser = internalMutation({
  args: {
    userId: v.string(),
    deviceId: v.string(),
    command: relayCommandValidator,
    args: v.optional(v.any()),
  },
  handler: async (ctx, args) => {
    const drone = await ctx.db
      .query("cmd_drones")
      .withIndex("by_deviceId", (q) => q.eq("deviceId", args.deviceId))
      .first();
    if (!drone || drone.userId !== args.userId) throw new Error("Not found");
    const id = await ctx.db.insert("cmd_droneCommands", {
      deviceId: args.deviceId,
      userId: drone.userId,
      command: args.command,
      args: args.args,
      status: "pending",
      createdAt: Date.now(),
    });
    return { commandId: id };
  },
});

export const getCommandForUser = internalQuery({
  args: { userId: v.string(), commandId: v.id("cmd_droneCommands") },
  handler: async (ctx, { userId, commandId }) => {
    const command = await ctx.db.get(commandId);
    if (!command || command.userId !== userId) throw new Error("Not found");
    return command;
  },
});

/**
 * Insert a batch of MCP audit events for one operator, idempotently. A row whose
 * contentHash already exists is skipped, so a server re-push (retry, restart)
 * never duplicates. The caller has already verified the credential and resolved
 * the trusted userId + tokenId.
 */
export const insertAuditEvents = internalMutation({
  args: {
    userId: v.string(),
    tokenId: v.string(),
    events: v.array(
      v.object({
        tool: v.string(),
        node: v.string(),
        decision: v.union(
          v.literal("allowed"),
          v.literal("denied"),
          v.literal("confirmed"),
          v.literal("operator_absent"),
        ),
        result: v.string(),
        plane: v.union(v.literal("lan_direct"), v.literal("cloud_relay"), v.literal("on_box")),
        latencyMs: v.number(),
        tsUs: v.number(),
        mcpSession: v.optional(v.string()),
        argsRedacted: v.optional(v.boolean()),
        sensitiveRead: v.optional(v.boolean()),
        contentHash: v.string(),
      }),
    ),
  },
  handler: async (ctx, { userId, tokenId, events }) => {
    let inserted = 0;
    for (const e of events) {
      const dup = await ctx.db
        .query("cmd_mcpAuditEvents")
        .withIndex("by_contentHash", (q) => q.eq("contentHash", e.contentHash))
        .first();
      if (dup) continue;
      await ctx.db.insert("cmd_mcpAuditEvents", { userId, tokenId, ...e, createdAt: Date.now() });
      inserted++;
    }
    return { inserted };
  },
});
