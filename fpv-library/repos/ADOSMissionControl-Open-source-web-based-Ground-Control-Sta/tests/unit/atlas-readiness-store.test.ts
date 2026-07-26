/**
 * Tests for the per-drone Atlas readiness store: set / get / clear and the
 * synchronous `isCapturing(deviceId)` helper the node-detail surface registry
 * reads to decide whether the Live World tab is shown.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect, beforeEach } from "vitest";
import { useAtlasReadinessStore } from "@/stores/atlas-readiness-store";
import type { AtlasReadiness } from "@/lib/agent/atlas-control-client";

function readiness(overrides: Partial<AtlasReadiness>): AtlasReadiness {
  return {
    enabled: true,
    profile: "drone",
    captureProfile: "balanced",
    reconstructSteps: 30000,
    camerasConfigured: 6,
    poseSource: "local_vio",
    serviceRunning: true,
    capturing: false,
    state: "idle",
    sessionId: null,
    cameraCount: 6,
    keyframes: 0,
    ingestRateHz: 0,
    ...overrides,
  };
}

beforeEach(() => {
  useAtlasReadinessStore.setState({ readiness: {} });
});

describe("atlas-readiness-store", () => {
  it("stores and reads readiness per device id", () => {
    const s = useAtlasReadinessStore.getState();
    s.setReadiness("dev1", readiness({ sessionId: "a" }));
    expect(useAtlasReadinessStore.getState().getReadiness("dev1")?.sessionId).toBe(
      "a",
    );
    expect(useAtlasReadinessStore.getState().getReadiness("dev2")).toBeNull();
  });

  it("isCapturing reflects the capturing flag, keyed by device", () => {
    const s = useAtlasReadinessStore.getState();
    s.setReadiness("dev1", readiness({ capturing: true }));
    s.setReadiness("dev2", readiness({ capturing: false }));
    const g = useAtlasReadinessStore.getState();
    expect(g.isCapturing("dev1")).toBe(true);
    expect(g.isCapturing("dev2")).toBe(false);
    expect(g.isCapturing("missing")).toBe(false);
  });

  it("isCapturing derives an active session from state, not just the bool", () => {
    const s = useAtlasReadinessStore.getState();
    // An agent may report capturing:false while paused/finalizing — the Live
    // World tab must stay visible through those states (Rule 44).
    s.setReadiness("paused", readiness({ capturing: false, state: "paused" }));
    s.setReadiness(
      "finalizing",
      readiness({ capturing: false, state: "finalizing" }),
    );
    s.setReadiness("bagged", readiness({ capturing: false, state: "bagged" }));
    const g = useAtlasReadinessStore.getState();
    expect(g.isCapturing("paused")).toBe(true);
    expect(g.isCapturing("finalizing")).toBe(true);
    expect(g.isCapturing("bagged")).toBe(false);
  });

  it("clear drops one device without touching others", () => {
    const s = useAtlasReadinessStore.getState();
    s.setReadiness("dev1", readiness({ capturing: true }));
    s.setReadiness("dev2", readiness({ capturing: true }));
    useAtlasReadinessStore.getState().clear("dev1");
    const g = useAtlasReadinessStore.getState();
    expect(g.getReadiness("dev1")).toBeNull();
    expect(g.isCapturing("dev2")).toBe(true);
  });

  it("setReadiness replaces the object reference (drives reactive selectors)", () => {
    const s = useAtlasReadinessStore.getState();
    const first = readiness({ keyframes: 1 });
    s.setReadiness("dev1", first);
    const before = useAtlasReadinessStore.getState().readiness;
    s.setReadiness("dev1", readiness({ keyframes: 2 }));
    const after = useAtlasReadinessStore.getState().readiness;
    expect(after).not.toBe(before);
    expect(after.dev1.keyframes).toBe(2);
  });
});
