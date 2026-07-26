import { describe, it, expect } from "vitest";
import { normalizeCapabilities } from "../normalizer";

describe("normalizeCapabilities runtimeMode passthrough", () => {
  it("passes a known runtime mode through unchanged", () => {
    for (const mode of ["native", "hybrid", "packaged"] as const) {
      const caps = normalizeCapabilities({ tier: 4, runtimeMode: mode });
      expect(caps.runtimeMode).toBe(mode);
    }
  });

  it("round-trips a legacy heartbeat (no field) to undefined", () => {
    const caps = normalizeCapabilities({ tier: 4 });
    expect(caps.runtimeMode).toBeUndefined();
  });

  it("normalizes an unrecognized value to undefined (forward-compatible)", () => {
    const caps = normalizeCapabilities({ tier: 4, runtimeMode: "quantum" });
    expect(caps.runtimeMode).toBeUndefined();
  });

  it("normalizes a non-string value to undefined", () => {
    const caps = normalizeCapabilities({ tier: 4, runtimeMode: 7 });
    expect(caps.runtimeMode).toBeUndefined();
  });
});
