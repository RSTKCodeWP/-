import { beforeEach, describe, expect, it } from "vitest";

import { useClearanceStore } from "./clearanceStore";

describe("clearance store", () => {
  beforeEach(() => useClearanceStore.getState().reset());

  it("a track with no recorded clearance reads as NEW", () => {
    expect(useClearanceStore.getState().get(42)).toBe("NEW");
  });

  it("sets and reads a clearance state", () => {
    useClearanceStore.getState().set(42, "ASSIGNED");
    expect(useClearanceStore.getState().get(42)).toBe("ASSIGNED");
  });

  it("exposes the full map for the view-model", () => {
    useClearanceStore.getState().set(1, "EN_ROUTE");
    useClearanceStore.getState().set(2, "FOUND");
    const map = useClearanceStore.getState().states;
    expect(map.get(1)).toBe("EN_ROUTE");
    expect(map.get(2)).toBe("FOUND");
  });

  it("snapshots the dispatched coordinate so later motion can be measured", () => {
    useClearanceStore.getState().snapshot(42, 30.215, -88.52);
    const snap = useClearanceStore.getState().dispatchSnapshot.get(42);
    expect(snap).toEqual({ lat: 30.215, lon: -88.52 });
  });

  it("computes delta-from-dispatched in meters when the contact moves", () => {
    useClearanceStore.getState().snapshot(42, 30.215, -88.52);
    // ~0.001 deg lat ≈ 111 m north
    const d = useClearanceStore.getState().deltaMeters(42, 30.216, -88.52);
    expect(d).not.toBeNull();
    expect(d!).toBeGreaterThan(100);
    expect(d!).toBeLessThan(120);
  });

  it("delta is null with no snapshot (nothing dispatched yet)", () => {
    expect(useClearanceStore.getState().deltaMeters(7, 30, -88)).toBeNull();
  });
});
