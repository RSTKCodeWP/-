/**
 * Shared authorization helpers for cloud-relay drone records.
 *
 * User-facing Convex functions must prove the authenticated user owns the
 * paired device before exposing status or queueing commands. Agent-facing
 * HTTP actions validate device API keys before calling internal functions.
 */

import { getAuthUserId } from "@convex-dev/auth/server";
import type { MutationCtx, QueryCtx } from "./_generated/server";
import type { Doc, Id } from "./_generated/dataModel";

type AuthCtx = QueryCtx | MutationCtx;

export async function requireOwnedDroneByDeviceId(
  ctx: AuthCtx,
  deviceId: string,
): Promise<Doc<"cmd_drones">> {
  const userId = await getAuthUserId(ctx);
  if (!userId) throw new Error("Not authenticated");

  const drone = await ctx.db
    .query("cmd_drones")
    .withIndex("by_deviceId", (q) => q.eq("deviceId", deviceId))
    .first();

  if (!drone || drone.userId !== userId) {
    throw new Error("Not found");
  }
  return drone;
}

export async function requireOwnedCommand(
  ctx: AuthCtx,
  commandId: Id<"cmd_droneCommands">,
): Promise<Doc<"cmd_droneCommands">> {
  const userId = await getAuthUserId(ctx);
  if (!userId) throw new Error("Not authenticated");

  const command = await ctx.db.get(commandId);
  if (!command || command.userId !== userId) {
    throw new Error("Not found");
  }

  await requireOwnedDroneByDeviceId(ctx, command.deviceId);
  return command;
}

export async function requireCommandForDevice(
  ctx: Pick<MutationCtx, "db">,
  commandId: Id<"cmd_droneCommands">,
  deviceId: string,
): Promise<Doc<"cmd_droneCommands">> {
  const command = await ctx.db.get(commandId);
  if (!command || command.deviceId !== deviceId) {
    throw new Error("Not found");
  }
  return command;
}
