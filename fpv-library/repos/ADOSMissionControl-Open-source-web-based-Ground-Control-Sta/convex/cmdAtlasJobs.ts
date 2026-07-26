/**
 * @module cmdAtlasJobs
 * @description Convex functions for ADOS Atlas reconstruction jobs.
 * User-facing reads require authentication and resolve ownership through the
 * capturing device (cmd_drones). The agent write path is an internal mutation
 * (admin-key only, not client-callable); the HTTP action validates the device
 * API key before calling it, mirroring cmdDroneStatus.pushStatus.
 * @license GPL-3.0-only
 */

import { v } from "convex/values";
import { internalMutation, query } from "./_generated/server";
import { getAuthUserId } from "@convex-dev/auth/server";

/** List Atlas jobs captured by a device the authenticated user owns. */
export const listForDevice = query({
  args: { deviceId: v.string() },
  handler: async (ctx, { deviceId }) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) return [];
    const drone = await ctx.db
      .query("cmd_drones")
      .withIndex("by_deviceId", (q) => q.eq("deviceId", deviceId))
      .first();
    if (!drone || drone.userId !== userId) return [];
    return await ctx.db
      .query("cmd_atlasJobs")
      .withIndex("by_device", (q) => q.eq("deviceId", deviceId))
      .order("desc")
      .collect();
  },
});

/**
 * List Atlas jobs reconstructed on a compute node. Ownership rides the
 * capturing device, so only jobs whose deviceId maps to a cmd_drones row
 * owned by the authenticated user are returned (a compute node's jobs are
 * visible to the owner of the capturing device).
 */
export const listByComputeNode = query({
  args: { computeNodeId: v.string() },
  handler: async (ctx, { computeNodeId }) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) return [];
    const jobs = await ctx.db
      .query("cmd_atlasJobs")
      .withIndex("by_computeNode", (q) => q.eq("computeNodeId", computeNodeId))
      .order("desc")
      .collect();
    const owned: typeof jobs = [];
    const ownership = new Map<string, boolean>();
    for (const job of jobs) {
      let isOwned = ownership.get(job.deviceId);
      if (isOwned === undefined) {
        const drone = await ctx.db
          .query("cmd_drones")
          .withIndex("by_deviceId", (q) => q.eq("deviceId", job.deviceId))
          .first();
        isOwned = !!drone && drone.userId === userId;
        ownership.set(job.deviceId, isOwned);
      }
      if (isOwned) owned.push(job);
    }
    return owned;
  },
});

/** Get a single Atlas job, verifying ownership through the capturing device. */
export const get = query({
  args: { jobId: v.id("cmd_atlasJobs") },
  handler: async (ctx, { jobId }) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) return null;
    const job = await ctx.db.get(jobId);
    if (!job) return null;
    const drone = await ctx.db
      .query("cmd_drones")
      .withIndex("by_deviceId", (q) => q.eq("deviceId", job.deviceId))
      .first();
    if (!drone || drone.userId !== userId) return null;
    return job;
  },
});

/**
 * Upsert an Atlas job from the compute agent (called via HTTP action, no user
 * auth — the action validates the device API key before calling this internal
 * mutation, mirroring cmdDroneStatus.pushStatus). The upsert key is
 * (computeNodeId, deviceId, sessionId) when sessionId is set, else
 * (computeNodeId, deviceId, inputBag); with neither set the job is always
 * inserted (no stable identity to match on). The deviceId is part of the key so
 * two drones streaming to one shared compute node can never overwrite each
 * other's row even on a same-session collision. Returns the job id.
 */
export const upsertJob = internalMutation({
  args: {
    deviceId: v.string(),
    computeNodeId: v.string(),
    kind: v.string(),
    status: v.string(),
    sessionId: v.optional(v.string()),
    inputBag: v.optional(v.string()),
    outputUrl: v.optional(v.string()),
    derivedFrom: v.optional(v.string()),
    metadata: v.optional(v.any()),
    startedAt: v.optional(v.number()),
    finishedAt: v.optional(v.number()),
  },
  handler: async (ctx, args) => {
    const candidates = await ctx.db
      .query("cmd_atlasJobs")
      .withIndex("by_computeNode", (q) =>
        q.eq("computeNodeId", args.computeNodeId),
      )
      .collect();

    const existing = candidates.find(
      (job) =>
        job.deviceId === args.deviceId &&
        (args.sessionId !== undefined
          ? job.sessionId === args.sessionId
          : args.inputBag !== undefined
            ? job.inputBag === args.inputBag
            : false),
    );

    if (existing) {
      // Patch every field except createdAt, which is preserved from insert.
      await ctx.db.patch(existing._id, { ...args });
      return existing._id;
    }

    return await ctx.db.insert("cmd_atlasJobs", {
      ...args,
      createdAt: Date.now(),
    });
  },
});
