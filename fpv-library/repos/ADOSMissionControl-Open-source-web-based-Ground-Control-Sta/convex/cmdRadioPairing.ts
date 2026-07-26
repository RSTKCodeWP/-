/**
 * @module cmdRadioPairing
 * @description Convex mutations + queries that drive the WFB radio
 * pairing flow over the cloud command relay.
 *
 * The GCS owns the orchestration loop (`pairRigsRemote` in
 * `src/lib/api/radio-pairing.ts`): it calls `enqueueWfbPairInit` for
 * the GS rig, polls the resulting command row via the reactive
 * `getCommandWithData` query until status flips to "completed", reads
 * the drone-key blob from the result `data` column, and calls
 * `enqueueWfbPairApply` to forward it to the drone rig. We don't
 * orchestrate inside Convex because (a) actions can't be reactive,
 * (b) we'd have to introduce a Node-runtime action just to sleep, and
 * (c) the existing mutation + reactive-query pattern already fits.
 *
 * The cmd_droneCommands.command field is `v.string()`, so we don't
 * extend a union here; we just wrap the well-known command names in
 * typed helpers so callers get string-literal autocomplete and the
 * GCS keeps a single source of truth for command names.
 *
 * @license GPL-3.0-only
 */

import { v } from "convex/values";

import { mutation, query } from "./_generated/server";
import {
  requireOwnedCommand,
  requireOwnedDroneByDeviceId,
} from "./cmdDroneAccess";

/**
 * Enqueue `wfb_pair_init_remote` for the GS rig. The agent generates
 * a libsodium keypair, persists `gs.key` locally, and returns the
 * matching `drone.key` bytes (base64) in the command result `data`.
 */
export const enqueueWfbPairInit = mutation({
  args: {
    gsDeviceId: v.string(),
    droneDeviceId: v.string(),
  },
  handler: async (ctx, { gsDeviceId, droneDeviceId }) => {
    // Validate ownership of BOTH rigs up front so a malicious caller
    // cannot enqueue a pair-init against a GS they don't own and then
    // try to apply the resulting blob to a drone they do own.
    const gs = await requireOwnedDroneByDeviceId(ctx, gsDeviceId);
    await requireOwnedDroneByDeviceId(ctx, droneDeviceId);

    const id = await ctx.db.insert("cmd_droneCommands", {
      deviceId: gsDeviceId,
      userId: gs.userId,
      command: "wfb_pair_init_remote",
      args: { peerDeviceId: droneDeviceId },
      status: "pending",
      createdAt: Date.now(),
    });
    return { commandId: id };
  },
});

/**
 * Enqueue `wfb_pair_apply_remote` for the drone rig. Caller supplies
 * the `blobB64` (drone-key bytes from a matching wfb_pair_init_remote
 * result) and the GS device-id to persist as the peer.
 */
export const enqueueWfbPairApply = mutation({
  args: {
    droneDeviceId: v.string(),
    gsDeviceId: v.string(),
    blobB64: v.string(),
  },
  handler: async (ctx, { droneDeviceId, gsDeviceId, blobB64 }) => {
    const drone = await requireOwnedDroneByDeviceId(ctx, droneDeviceId);
    await requireOwnedDroneByDeviceId(ctx, gsDeviceId);

    const id = await ctx.db.insert("cmd_droneCommands", {
      deviceId: droneDeviceId,
      userId: drone.userId,
      command: "wfb_pair_apply_remote",
      args: { peerDeviceId: gsDeviceId, blobB64 },
      status: "pending",
      createdAt: Date.now(),
    });
    return { commandId: id };
  },
});

/**
 * Enqueue `wfb_pair_unpair` for either side. Used as the rollback
 * action when the orchestration loop detects a fingerprint mismatch
 * between the GS and drone, and as the explicit operator unpair from
 * the GCS UI.
 */
export const enqueueWfbPairUnpair = mutation({
  args: {
    deviceId: v.string(),
  },
  handler: async (ctx, { deviceId }) => {
    const drone = await requireOwnedDroneByDeviceId(ctx, deviceId);

    const id = await ctx.db.insert("cmd_droneCommands", {
      deviceId,
      userId: drone.userId,
      command: "wfb_pair_unpair",
      args: {},
      status: "pending",
      createdAt: Date.now(),
    });
    return { commandId: id };
  },
});

/**
 * Reactive read of a command row including its `data` payload. The
 * GCS poll loop subscribes to this and reads `data.blobB64` /
 * `data.fingerprint` once `status === "completed"`.
 */
export const getCommandWithData = query({
  args: { commandId: v.id("cmd_droneCommands") },
  handler: async (ctx, { commandId }) => {
    return await requireOwnedCommand(ctx, commandId);
  },
});

/**
 * Server-side fingerprint cross-check + atomic completion mark. The
 * GCS calls this once it has both the GS and drone command results;
 * if the fingerprints don't match, this mutation fires the
 * `wfb_pair_unpair` rollback for both rigs in the same Convex call.
 */
export const finalizePairing = mutation({
  args: {
    gsDeviceId: v.string(),
    droneDeviceId: v.string(),
    gsFingerprint: v.union(v.string(), v.null()),
    droneFingerprint: v.union(v.string(), v.null()),
  },
  handler: async (
    ctx,
    { gsDeviceId, droneDeviceId, gsFingerprint, droneFingerprint }
  ) => {
    const gs = await requireOwnedDroneByDeviceId(ctx, gsDeviceId);
    await requireOwnedDroneByDeviceId(ctx, droneDeviceId);

    const matched =
      gsFingerprint != null &&
      droneFingerprint != null &&
      gsFingerprint === droneFingerprint;

    if (!matched) {
      // Roll back: enqueue unpair for both rigs. The agents will
      // wipe keys and restart wfb services. Do NOT throw — return
      // the failure shape so the caller can render a user-facing
      // error without losing the rollback step.
      const ts = Date.now();
      await ctx.db.insert("cmd_droneCommands", {
        deviceId: gsDeviceId,
        userId: gs.userId,
        command: "wfb_pair_unpair",
        args: { reason: "fingerprint_mismatch" },
        status: "pending",
        createdAt: ts,
      });
      await ctx.db.insert("cmd_droneCommands", {
        deviceId: droneDeviceId,
        userId: gs.userId,
        command: "wfb_pair_unpair",
        args: { reason: "fingerprint_mismatch" },
        status: "pending",
        createdAt: ts,
      });
      return {
        paired: false,
        reason: "fingerprint_mismatch",
        gsFingerprint,
        droneFingerprint,
      };
    }

    return {
      paired: true,
      fingerprint: gsFingerprint,
      gsDeviceId,
      droneDeviceId,
      pairedAt: new Date().toISOString(),
    };
  },
});

/**
 * Mark a command as cancelled when the GCS poll loop times out. The
 * agent may still complete the command later (network glitch on the
 * way back), in which case the ack handler will see the cancelled
 * row and silently ignore it. Best-effort.
 */
export const cancelCommand = mutation({
  args: {
    commandId: v.id("cmd_droneCommands"),
    deviceId: v.string(),
  },
  handler: async (ctx, { commandId, deviceId }) => {
    // Client-callable: authenticate the caller and prove they own both the
    // command and its drone before touching the row. The agent-facing
    // requireCommandForDevice helper only matches deviceId (it runs after the
    // HTTP layer validates the device API key); using it here would let any
    // signed-in user flip another user's in-flight command by supplying the
    // victim's commandId + deviceId. requireOwnedCommand binds the row to the
    // authenticated owner; the deviceId guard then keeps the arg honest.
    const command = await requireOwnedCommand(ctx, commandId);
    if (command.deviceId !== deviceId) {
      throw new Error("Not found");
    }
    await ctx.db.patch(commandId, {
      status: "failed",
      result: { success: false, message: "cancelled by GCS" },
      completedAt: Date.now(),
    });
    return { ok: true };
  },
});
