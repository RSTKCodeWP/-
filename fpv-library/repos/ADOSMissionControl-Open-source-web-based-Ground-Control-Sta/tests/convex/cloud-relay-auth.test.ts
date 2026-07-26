import { readFile } from "node:fs/promises";
import path from "node:path";
import { describe, expect, it, vi } from "vitest";

const authMocks = vi.hoisted(() => ({
  getAuthUserId: vi.fn(),
}));

vi.mock("@convex-dev/auth/server", () => ({
  getAuthUserId: authMocks.getAuthUserId,
}));

import {
  requireCommandForDevice,
  requireOwnedCommand,
  requireOwnedDroneByDeviceId,
} from "../../convex/cmdDroneAccess";

type Row = Record<string, unknown>;

function makeCtx(options: {
  userId: string | null;
  drones?: Row[];
  commands?: Row[];
}) {
  authMocks.getAuthUserId.mockResolvedValue(options.userId);
  const rowsByTable: Record<string, Row[]> = {
    cmd_drones: options.drones ?? [],
    cmd_droneCommands: options.commands ?? [],
  };

  return {
    db: {
      get: vi.fn(async (id: string) =>
        (options.commands ?? []).find((row) => row._id === id) ?? null
      ),
      query: vi.fn((table: string) => ({
        withIndex: (_index: string, apply: (q: unknown) => unknown) => {
          const filters: Array<[string, unknown]> = [];
          const q = {
            eq(field: string, value: unknown) {
              filters.push([field, value]);
              return q;
            },
          };
          apply(q);
          const rows = (rowsByTable[table] ?? []).filter((row) =>
            filters.every(([field, value]) => row[field] === value),
          );
          return {
            first: vi.fn(async () => rows[0] ?? null),
            collect: vi.fn(async () => rows),
          };
        },
      })),
    },
  };
}

describe("cloud relay authorization helpers", () => {
  it("allows an authenticated owner to access their paired device", async () => {
    const ctx = makeCtx({
      userId: "user-a",
      drones: [{ _id: "drone-a", userId: "user-a", deviceId: "device-a" }],
    });

    await expect(
      requireOwnedDroneByDeviceId(ctx as never, "device-a"),
    ).resolves.toMatchObject({ _id: "drone-a" });
  });

  it("rejects unauthenticated and cross-user device access", async () => {
    await expect(
      requireOwnedDroneByDeviceId(
        makeCtx({
          userId: null,
          drones: [{ userId: "user-a", deviceId: "device-a" }],
        }) as never,
        "device-a",
      ),
    ).rejects.toThrow("Not authenticated");

    await expect(
      requireOwnedDroneByDeviceId(
        makeCtx({
          userId: "user-b",
          drones: [{ userId: "user-a", deviceId: "device-a" }],
        }) as never,
        "device-a",
      ),
    ).rejects.toThrow("Not found");
  });

  it("requires command ownership and matching paired-device ownership", async () => {
    const command = {
      _id: "command-a",
      userId: "user-a",
      deviceId: "device-a",
      command: "arm",
      status: "pending",
    };

    await expect(
      requireOwnedCommand(
        makeCtx({
          userId: "user-a",
          drones: [{ userId: "user-a", deviceId: "device-a" }],
          commands: [command],
        }) as never,
        "command-a" as never,
      ),
    ).resolves.toMatchObject(command);

    await expect(
      requireOwnedCommand(
        makeCtx({
          userId: "user-a",
          drones: [{ userId: "user-b", deviceId: "device-a" }],
          commands: [command],
        }) as never,
        "command-a" as never,
      ),
    ).rejects.toThrow("Not found");
  });

  it("prevents an agent from acknowledging another device command", async () => {
    const ctx = makeCtx({
      userId: null,
      commands: [{ _id: "command-a", deviceId: "device-a" }],
    });

    await expect(
      requireCommandForDevice(ctx as never, "command-a" as never, "device-a"),
    ).resolves.toMatchObject({ _id: "command-a" });
    await expect(
      requireCommandForDevice(ctx as never, "command-a" as never, "device-b"),
    ).rejects.toThrow("Not found");
  });

  it("blocks a non-owner from cancelling another user's command", async () => {
    // cancelCommand is client-callable and must authenticate the caller via
    // requireOwnedCommand (owner-bound), not the agent-facing
    // requireCommandForDevice (deviceId-only). Prove the owner-bound helper
    // rejects a signed-in user who supplies a victim's commandId.
    const victimCommand = {
      _id: "command-victim",
      userId: "user-victim",
      deviceId: "device-victim",
      command: "wfb_pair_init_remote",
      status: "pending",
    };

    await expect(
      requireOwnedCommand(
        makeCtx({
          userId: "user-attacker",
          drones: [{ userId: "user-victim", deviceId: "device-victim" }],
          commands: [victimCommand],
        }) as never,
        "command-victim" as never,
      ),
    ).rejects.toThrow("Not found");
  });

  it("wires cancelCommand to the owner-checked authz path", async () => {
    const radio = await readFile(
      path.join(process.cwd(), "convex/cmdRadioPairing.ts"),
      "utf8",
    );
    // The cancelCommand handler must authenticate + own-check the caller and
    // must not fall back to the agent-facing deviceId-only helper. The helper
    // is no longer imported or called here (a comment may still name it).
    expect(radio).toContain("export const cancelCommand = mutation");
    expect(radio).toContain("await requireOwnedCommand(ctx, commandId)");
    expect(radio).not.toContain("import {\n  requireCommandForDevice,");
    expect(radio).not.toContain("await requireCommandForDevice(");
  });

  it("keeps agent-only relay functions out of the public Convex API", async () => {
    const [commands, status, drones] = await Promise.all([
      readFile(path.join(process.cwd(), "convex/cmdDroneCommands.ts"), "utf8"),
      readFile(path.join(process.cwd(), "convex/cmdDroneStatus.ts"), "utf8"),
      readFile(path.join(process.cwd(), "convex/cmdDrones.ts"), "utf8"),
    ]);

    expect(commands).toContain("export const getPendingCommands = internalQuery");
    expect(commands).toContain("export const ackCommand = internalMutation");
    expect(status).toContain("export const pushStatus = internalMutation");
    expect(drones).toContain("export const getDroneByDeviceId = internalQuery");
  });
});
