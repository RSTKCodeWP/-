import { describe, it, expect } from "vitest";
import { normalizeCapabilities } from "../normalizer";

describe("normalizeCapabilities cameraUsbRecovery clamp", () => {
  it("keeps a well-formed block and coerces its fields", () => {
    const caps = normalizeCapabilities({
      tier: 4,
      cameraUsbRecovery: {
        state: "port_cycling",
        case: "present_wedged",
        attempts: 1,
        maxAttempts: 3,
        cameraPresent: false,
        expected: true,
        pppsCapable: true,
        powerContention: true,
        contentionPeer: "1-1.2",
      },
    });
    expect(caps.cameraUsbRecovery?.state).toBe("port_cycling");
    expect(caps.cameraUsbRecovery?.case).toBe("present_wedged");
    expect(caps.cameraUsbRecovery?.attempts).toBe(1);
    expect(caps.cameraUsbRecovery?.maxAttempts).toBe(3);
    expect(caps.cameraUsbRecovery?.cameraPresent).toBe(false);
    expect(caps.cameraUsbRecovery?.expected).toBe(true);
    expect(caps.cameraUsbRecovery?.pppsCapable).toBe(true);
    expect(caps.cameraUsbRecovery?.powerContention).toBe(true);
    expect(caps.cameraUsbRecovery?.contentionPeer).toBe("1-1.2");
  });

  it("accepts each known recovery state", () => {
    for (const state of [
      "idle",
      "monitoring",
      "rebinding",
      "port_cycling",
      "hub_resetting",
      "needs_hub_reset",
      "guard_blocked",
      "exhausted",
    ] as const) {
      const caps = normalizeCapabilities({
        tier: 4,
        cameraUsbRecovery: { state },
      });
      expect(caps.cameraUsbRecovery?.state).toBe(state);
    }
  });

  it("coerces non-finite numbers and missing booleans to safe defaults", () => {
    const caps = normalizeCapabilities({
      tier: 4,
      cameraUsbRecovery: {
        state: "monitoring",
        attempts: "nope",
        maxAttempts: Infinity,
        case: 123,
      },
    });
    expect(caps.cameraUsbRecovery?.attempts).toBe(0);
    expect(caps.cameraUsbRecovery?.maxAttempts).toBe(0);
    // A non-string case drops to null rather than surfacing junk.
    expect(caps.cameraUsbRecovery?.case).toBeNull();
    // Missing booleans default to false.
    expect(caps.cameraUsbRecovery?.cameraPresent).toBe(false);
    expect(caps.cameraUsbRecovery?.expected).toBe(false);
    expect(caps.cameraUsbRecovery?.pppsCapable).toBe(false);
  });

  it("drops the whole block when state is unknown", () => {
    expect(
      normalizeCapabilities({
        tier: 4,
        cameraUsbRecovery: { state: "weird", attempts: 2 },
      }).cameraUsbRecovery,
    ).toBeUndefined();
  });

  it("round-trips a legacy heartbeat (no field) to undefined", () => {
    expect(normalizeCapabilities({ tier: 4 }).cameraUsbRecovery).toBeUndefined();
  });

  it("normalizes a non-object value to undefined", () => {
    expect(
      normalizeCapabilities({ tier: 4, cameraUsbRecovery: "rebinding" })
        .cameraUsbRecovery,
    ).toBeUndefined();
    expect(
      normalizeCapabilities({ tier: 4, cameraUsbRecovery: null })
        .cameraUsbRecovery,
    ).toBeUndefined();
  });
});
