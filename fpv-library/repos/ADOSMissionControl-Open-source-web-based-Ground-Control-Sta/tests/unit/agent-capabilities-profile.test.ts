/**
 * Verifies the agent capabilities store's profile + role normaliser.
 * Profile is forward-permissive — unknown strings clamp to "drone" so
 * a future agent variant cannot wedge the GCS. Role accepts the three
 * ground-station values plus null (explicit drone heartbeat).
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { useAgentCapabilitiesStore } from "@/stores/agent-capabilities-store";

const initialState = useAgentCapabilitiesStore.getState();

function baseCaps() {
  const state = useAgentCapabilitiesStore.getState();
  return {
    tier: 0,
    cameras: [],
    compute: state.compute,
    vision: state.vision,
    models: state.models,
  };
}

beforeEach(() => {
  useAgentCapabilitiesStore.setState(initialState, true);
});

afterEach(() => {
  useAgentCapabilitiesStore.setState(initialState, true);
});

describe("agent-capabilities-store profile + role normaliser", () => {
  it("defaults to drone profile and undefined role", () => {
    const s = useAgentCapabilitiesStore.getState();
    expect(s.profile).toBe("drone");
    expect(s.role).toBeUndefined();
  });

  it("accepts camelCase profile=ground-station", () => {
    useAgentCapabilitiesStore.getState().setCapabilities({
      ...baseCaps(),
      profile: "ground-station",
    });
    expect(useAgentCapabilitiesStore.getState().profile).toBe("ground-station");
  });

  it("accepts snake_case node_profile=workstation", () => {
    useAgentCapabilitiesStore.getState().setCapabilities({
      ...baseCaps(),
      node_profile: "workstation",
    });
    expect(useAgentCapabilitiesStore.getState().profile).toBe("workstation");
  });

  it("clamps unknown profile strings to drone", () => {
    // Suppress the console.warn dev-tooling hint for this test.
    const originalWarn = console.warn;
    console.warn = () => {};
    try {
      useAgentCapabilitiesStore.getState().setCapabilities({
        ...baseCaps(),
        profile: "future-thing",
      });
      expect(useAgentCapabilitiesStore.getState().profile).toBe("drone");
    } finally {
      console.warn = originalWarn;
    }
  });

  it("accepts each valid ground-station role", () => {
    for (const role of ["direct", "relay", "receiver"] as const) {
      useAgentCapabilitiesStore.getState().setCapabilities({
        ...baseCaps(),
        profile: "ground-station",
        role,
      });
      expect(useAgentCapabilitiesStore.getState().role).toBe(role);
    }
  });

  it("explicit role: null sets state.role to null", () => {
    useAgentCapabilitiesStore.getState().setCapabilities({
      ...baseCaps(),
      profile: "drone",
      role: null,
    });
    expect(useAgentCapabilitiesStore.getState().role).toBeNull();
  });

  it("unknown role string keeps prior role (forward-permissive)", () => {
    // Seed with a known role.
    useAgentCapabilitiesStore.getState().setCapabilities({
      ...baseCaps(),
      profile: "ground-station",
      role: "relay",
    });
    expect(useAgentCapabilitiesStore.getState().role).toBe("relay");
    // Send a sparse heartbeat with an unknown role.
    useAgentCapabilitiesStore.getState().setCapabilities({
      ...baseCaps(),
      profile: "ground-station",
      role: "future-role",
    });
    // Prior known role survives.
    expect(useAgentCapabilitiesStore.getState().role).toBe("relay");
  });

  it("clear() resets profile to drone and role to undefined", () => {
    useAgentCapabilitiesStore.getState().setCapabilities({
      ...baseCaps(),
      profile: "ground-station",
      role: "receiver",
    });
    useAgentCapabilitiesStore.getState().clear();
    const s = useAgentCapabilitiesStore.getState();
    expect(s.profile).toBe("drone");
    expect(s.role).toBeUndefined();
  });
});
