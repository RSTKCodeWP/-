/**
 * @module perception-health.test
 * @description Unit tests for the perception session-state + throughput +
 * execution-target derivations behind the Perception session card and the
 * pipeline execution-target badge.
 * @license GPL-3.0-only
 */

import { describe, expect, it } from "vitest";

import {
  batchesPerSecond,
  executionTarget,
  perceptionSessionState,
} from "../perception-health";

describe("perceptionSessionState", () => {
  it("maps a fresh feed to live", () => {
    expect(perceptionSessionState("fresh", "offload")).toBe("live");
    expect(perceptionSessionState("fresh", undefined)).toBe("live");
  });

  it("maps a stale feed to stalled", () => {
    expect(perceptionSessionState("stale", "offload")).toBe("stalled");
    expect(perceptionSessionState("stale", "local")).toBe("stalled");
  });

  it("maps an idle feed with a running tier to opening", () => {
    expect(perceptionSessionState("idle", "local")).toBe("opening");
    expect(perceptionSessionState("idle", "offload")).toBe("opening");
    expect(perceptionSessionState("idle", "hybrid")).toBe("opening");
  });

  it("maps an idle feed with no perception context to closed", () => {
    expect(perceptionSessionState("idle", "none")).toBe("closed");
    expect(perceptionSessionState("idle", undefined)).toBe("closed");
  });
});

describe("batchesPerSecond", () => {
  it("reports ~10 Hz for batches spaced 100ms over the window", () => {
    // 10 samples at 0,100,...,900ms; span 900ms, (10-1)/0.9 = 10.
    const times = Array.from({ length: 10 }, (_, i) => i * 100);
    expect(batchesPerSecond(times, 900, 3000)).toBeCloseTo(10, 5);
  });

  it("is accurate during warm-up (only a few samples in the window)", () => {
    // 3 samples at 1000,1100,1200; (3-1)/0.2 = 10.
    expect(batchesPerSecond([1000, 1100, 1200], 1200, 3000)).toBeCloseTo(10, 5);
  });

  it("returns null when fewer than two samples are in the window", () => {
    expect(batchesPerSecond([], 1000, 3000)).toBeNull();
    expect(batchesPerSecond([500], 1000, 3000)).toBeNull();
  });

  it("drops samples that have aged out of the window (returns null)", () => {
    // now=5000, window=3000 -> cutoff 2000; the lone sample at 0 is excluded.
    expect(batchesPerSecond([0], 5000, 3000)).toBeNull();
  });

  it("ignores future samples and a non-positive window", () => {
    expect(batchesPerSecond([100, 200], 200, 0)).toBeNull();
    // 300 is in the future relative to now=200 -> excluded, leaving one sample.
    expect(batchesPerSecond([100, 300], 200, 3000)).toBeNull();
  });
});

describe("executionTarget", () => {
  it("labels an offload tier with its target detail", () => {
    expect(executionTarget("offload", "ws.local:8092")).toEqual({
      kind: "offload",
      detail: "ws.local:8092",
    });
  });

  it("offload with no target carries no detail (never fabricated)", () => {
    expect(executionTarget("offload", null)).toEqual({
      kind: "offload",
      detail: undefined,
    });
  });

  it("labels local and hybrid tiers", () => {
    expect(executionTarget("local", null)).toEqual({ kind: "local" });
    expect(executionTarget("hybrid", null)).toEqual({ kind: "auto" });
  });

  it("returns null for an unknown or none tier (no badge)", () => {
    expect(executionTarget("none", null)).toBeNull();
    expect(executionTarget(undefined, "ws.local:8092")).toBeNull();
  });
});
