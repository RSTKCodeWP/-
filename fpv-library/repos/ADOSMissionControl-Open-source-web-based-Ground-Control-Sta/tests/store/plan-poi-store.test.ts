/**
 * Unit tests for the plan-attached POI store. Pure CRUD + selection +
 * snapshot/restore (deep-copy, no aliasing). The store depends only on zustand,
 * so no mocks are required.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect, beforeEach } from "vitest";
import { usePlanPoiStore, type PointOfInterest } from "@/stores/plan-poi-store";

function poi(overrides: Partial<PointOfInterest> = {}): PointOfInterest {
  return { id: Math.random().toString(36).slice(2, 10), lat: 12.97, lon: 77.59, ...overrides };
}

function reset() {
  usePlanPoiStore.setState({ points: [], selectedId: null });
}

describe("plan-poi-store", () => {
  beforeEach(reset);

  it("starts empty with no selection", () => {
    const s = usePlanPoiStore.getState();
    expect(s.points).toEqual([]);
    expect(s.selectedId).toBeNull();
  });

  it("adds points in order", () => {
    usePlanPoiStore.getState().addPoint(poi({ id: "a", label: "Alpha" }));
    usePlanPoiStore.getState().addPoint(poi({ id: "b", note: "second" }));
    const pts = usePlanPoiStore.getState().points;
    expect(pts.map((p) => p.id)).toEqual(["a", "b"]);
    expect(pts[0].label).toBe("Alpha");
    expect(pts[1].note).toBe("second");
  });

  it("updates a point by id, leaving others untouched", () => {
    usePlanPoiStore.getState().addPoint(poi({ id: "a", lat: 1, lon: 2 }));
    usePlanPoiStore.getState().addPoint(poi({ id: "b", lat: 3, lon: 4 }));
    usePlanPoiStore.getState().updatePoint("a", { label: "Home", lat: 10 });
    const [a, b] = usePlanPoiStore.getState().points;
    expect(a).toMatchObject({ id: "a", label: "Home", lat: 10, lon: 2 });
    expect(b).toMatchObject({ id: "b", lat: 3, lon: 4 });
  });

  it("removes a point and clears the selection when the removed one was selected", () => {
    usePlanPoiStore.getState().addPoint(poi({ id: "a" }));
    usePlanPoiStore.getState().addPoint(poi({ id: "b" }));
    usePlanPoiStore.getState().select("a");
    usePlanPoiStore.getState().removePoint("a");
    expect(usePlanPoiStore.getState().points.map((p) => p.id)).toEqual(["b"]);
    expect(usePlanPoiStore.getState().selectedId).toBeNull();
  });

  it("removing a non-selected point keeps the selection", () => {
    usePlanPoiStore.getState().addPoint(poi({ id: "a" }));
    usePlanPoiStore.getState().addPoint(poi({ id: "b" }));
    usePlanPoiStore.getState().select("a");
    usePlanPoiStore.getState().removePoint("b");
    expect(usePlanPoiStore.getState().selectedId).toBe("a");
  });

  it("select / clear updates the selection", () => {
    usePlanPoiStore.getState().addPoint(poi({ id: "a" }));
    usePlanPoiStore.getState().select("a");
    expect(usePlanPoiStore.getState().selectedId).toBe("a");
    usePlanPoiStore.getState().select(null);
    expect(usePlanPoiStore.getState().selectedId).toBeNull();
  });

  it("clearPoints wipes points and selection", () => {
    usePlanPoiStore.getState().addPoint(poi({ id: "a" }));
    usePlanPoiStore.getState().select("a");
    usePlanPoiStore.getState().clearPoints();
    expect(usePlanPoiStore.getState().points).toEqual([]);
    expect(usePlanPoiStore.getState().selectedId).toBeNull();
  });

  it("snapshot/restore round-trips points and selection", () => {
    usePlanPoiStore.getState().addPoint(poi({ id: "a", label: "A" }));
    usePlanPoiStore.getState().addPoint(poi({ id: "b", note: "n" }));
    usePlanPoiStore.getState().select("b");
    const snap = usePlanPoiStore.getState().snapshot();

    usePlanPoiStore.getState().clearPoints();
    expect(usePlanPoiStore.getState().points).toHaveLength(0);

    usePlanPoiStore.getState().restore(snap);
    expect(usePlanPoiStore.getState().points.map((p) => p.id)).toEqual(["a", "b"]);
    expect(usePlanPoiStore.getState().selectedId).toBe("b");
  });

  it("a later mutation does not corrupt a captured snapshot (deep copy)", () => {
    usePlanPoiStore.getState().addPoint(poi({ id: "a", label: "orig" }));
    const snap = usePlanPoiStore.getState().snapshot();

    // Mutate the live store after capture.
    usePlanPoiStore.getState().updatePoint("a", { label: "changed" });
    expect(usePlanPoiStore.getState().points[0].label).toBe("changed");

    // The snapshot must still carry the original value, not the aliased one.
    expect(snap.points[0].label).toBe("orig");
  });
});
