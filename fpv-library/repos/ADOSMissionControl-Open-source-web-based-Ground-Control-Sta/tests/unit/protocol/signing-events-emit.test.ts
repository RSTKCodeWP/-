import { describe, it, expect, vi } from "vitest";

import { emitSigningEvent } from "@/lib/api/signing-events";

function fakeClient() {
  const mutation = vi.fn().mockResolvedValue({ _id: "ev1" });
  return {
    client: { mutation } as unknown as NonNullable<Parameters<typeof emitSigningEvent>[0]>,
    mutation,
  };
}

describe("emitSigningEvent", () => {
  it("returns false when client is null", async () => {
    const ok = await emitSigningEvent(null, true, {
      droneId: "drone-a",
      eventType: "enrollment",
    });
    expect(ok).toBe(false);
  });

  it("returns false when user is not authenticated", async () => {
    const { client } = fakeClient();
    const ok = await emitSigningEvent(client, false, {
      droneId: "drone-a",
      eventType: "enrollment",
    });
    expect(ok).toBe(false);
  });

  it("calls the append mutation with the supplied event fields", async () => {
    const { client, mutation } = fakeClient();
    const ok = await emitSigningEvent(client, true, {
      droneId: "drone-a",
      eventType: "rotation",
      keyIdOld: "a1b2c3d4",
      keyIdNew: "e5f60708",
    });
    expect(ok).toBe(true);
    expect(mutation).toHaveBeenCalledTimes(1);
    const [, args] = mutation.mock.calls[0];
    expect(args.droneId).toBe("drone-a");
    expect(args.eventType).toBe("rotation");
    expect(args.keyIdOld).toBe("a1b2c3d4");
    expect(args.keyIdNew).toBe("e5f60708");
    expect(args.deviceFingerprint).toMatch(/^[0-9a-f]{12}$/);
  });

  it("never throws when the mutation errors", async () => {
    const mutation = vi.fn().mockRejectedValue(new Error("convex down"));
    const client = { mutation } as unknown as NonNullable<Parameters<typeof emitSigningEvent>[0]>;
    const ok = await emitSigningEvent(client, true, {
      droneId: "drone-a",
      eventType: "enrollment",
    });
    expect(ok).toBe(false);
  });

  it("never includes keyHex in the outgoing payload", async () => {
    const { client, mutation } = fakeClient();
    await emitSigningEvent(client, true, {
      droneId: "drone-a",
      eventType: "enrollment",
      keyIdNew: "e5f60708",
    });
    const [, args] = mutation.mock.calls[0];
    // Defensive: the types don't allow keyHex, but ensure nobody snuck
    // a raw key into the payload via any type sleight.
    expect((args as Record<string, unknown>).keyHex).toBeUndefined();
    for (const value of Object.values(args)) {
      if (typeof value === "string" && value.length === 64) {
        throw new Error("64-char string in event payload suggests a leaked keyHex");
      }
    }
  });
});
