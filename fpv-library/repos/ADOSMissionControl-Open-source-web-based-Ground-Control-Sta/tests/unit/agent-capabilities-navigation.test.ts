/**
 * Verifies the agent capabilities store's navigation passthrough.
 * The store accepts the heartbeat navigation block as-is, surfaces
 * the four required fields plus any optional metrics the agent
 * advertises, and keeps the prior value when a sparse heartbeat
 * omits the block.
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

describe("agent-capabilities-store navigation passthrough", () => {
  it("defaults navigation to undefined", () => {
    expect(useAgentCapabilitiesStore.getState().navigation).toBeUndefined();
  });

  it("accepts the four required fields and ignores optional metrics", () => {
    useAgentCapabilitiesStore.getState().setCapabilities({
      ...baseCaps(),
      navigation: {
        opticalFlowSupported: true,
        vioSupported: false,
        rangefinderTopology: "companion",
        recommendedCameraId: "cam0",
      },
    } as unknown as Record<string, unknown>);
    const nav = useAgentCapabilitiesStore.getState().navigation;
    expect(nav).toBeDefined();
    expect(nav?.opticalFlowSupported).toBe(true);
    expect(nav?.vioSupported).toBe(false);
    expect(nav?.rangefinderTopology).toBe("companion");
    expect(nav?.recommendedCameraId).toBe("cam0");
    expect(nav?.flowQuality).toBeUndefined();
  });

  it("surfaces optional metrics when present", () => {
    useAgentCapabilitiesStore.getState().setCapabilities({
      ...baseCaps(),
      navigation: {
        opticalFlowSupported: true,
        vioSupported: true,
        rangefinderTopology: "both",
        recommendedCameraId: null,
        flowQuality: 0.82,
        flowRateHz: 30,
        flowDistanceM: 4.2,
        vioState: "active",
        vioResetCounter: 1,
        vioQuality: 0.9,
        companionState: "active",
      },
    } as unknown as Record<string, unknown>);
    const nav = useAgentCapabilitiesStore.getState().navigation;
    expect(nav?.recommendedCameraId).toBeNull();
    expect(nav?.flowQuality).toBeCloseTo(0.82);
    expect(nav?.flowRateHz).toBe(30);
    expect(nav?.flowDistanceM).toBeCloseTo(4.2);
    expect(nav?.vioState).toBe("active");
    expect(nav?.vioResetCounter).toBe(1);
    expect(nav?.vioQuality).toBeCloseTo(0.9);
    expect(nav?.companionState).toBe("active");
  });

  it("accepts null rangefinderTopology and null recommendedCameraId", () => {
    useAgentCapabilitiesStore.getState().setCapabilities({
      ...baseCaps(),
      navigation: {
        opticalFlowSupported: false,
        vioSupported: false,
        rangefinderTopology: null,
        recommendedCameraId: null,
      },
    } as unknown as Record<string, unknown>);
    const nav = useAgentCapabilitiesStore.getState().navigation;
    expect(nav?.rangefinderTopology).toBeNull();
    expect(nav?.recommendedCameraId).toBeNull();
  });

  it("legacy heartbeats without navigation leave the field undefined", () => {
    useAgentCapabilitiesStore.getState().setCapabilities(baseCaps());
    expect(useAgentCapabilitiesStore.getState().navigation).toBeUndefined();
  });

  it("forward-permissive: a sparse heartbeat keeps the prior block", () => {
    // Seed with a navigation block.
    useAgentCapabilitiesStore.getState().setCapabilities({
      ...baseCaps(),
      navigation: {
        opticalFlowSupported: true,
        vioSupported: true,
        rangefinderTopology: "fc",
        recommendedCameraId: "cam0",
        vioState: "active",
      },
    } as unknown as Record<string, unknown>);
    expect(
      useAgentCapabilitiesStore.getState().navigation?.vioState,
    ).toBe("active");

    // Sparse heartbeat: no navigation. Prior value survives.
    useAgentCapabilitiesStore.getState().setCapabilities(baseCaps());
    const nav = useAgentCapabilitiesStore.getState().navigation;
    expect(nav).toBeDefined();
    expect(nav?.opticalFlowSupported).toBe(true);
    expect(nav?.vioState).toBe("active");
  });

  it("latest navigation block replaces the prior one when both are present", () => {
    useAgentCapabilitiesStore.getState().setCapabilities({
      ...baseCaps(),
      navigation: {
        opticalFlowSupported: true,
        vioSupported: true,
        rangefinderTopology: "fc",
        recommendedCameraId: "cam0",
        vioState: "active",
      },
    } as unknown as Record<string, unknown>);
    useAgentCapabilitiesStore.getState().setCapabilities({
      ...baseCaps(),
      navigation: {
        opticalFlowSupported: true,
        vioSupported: true,
        rangefinderTopology: "fc",
        recommendedCameraId: "cam0",
        vioState: "degraded",
        vioResetCounter: 3,
      },
    } as unknown as Record<string, unknown>);
    const nav = useAgentCapabilitiesStore.getState().navigation;
    expect(nav?.vioState).toBe("degraded");
    expect(nav?.vioResetCounter).toBe(3);
  });

  it("clear() resets navigation to undefined", () => {
    useAgentCapabilitiesStore.getState().setCapabilities({
      ...baseCaps(),
      navigation: {
        opticalFlowSupported: true,
        vioSupported: false,
        rangefinderTopology: "companion",
        recommendedCameraId: "cam0",
      },
    } as unknown as Record<string, unknown>);
    expect(
      useAgentCapabilitiesStore.getState().navigation,
    ).toBeDefined();
    useAgentCapabilitiesStore.getState().clear();
    expect(
      useAgentCapabilitiesStore.getState().navigation,
    ).toBeUndefined();
  });
});
