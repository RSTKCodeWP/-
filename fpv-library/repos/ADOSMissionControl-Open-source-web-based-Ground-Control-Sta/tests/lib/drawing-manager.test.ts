/**
 * Unit tests for the DrawingManager's imperative surface and the invariant that
 * it no longer registers its own document keyboard listeners (the planner
 * keyboard dispatcher owns the keys now).
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Use the shared manual leaflet mock so the manager can build feature groups,
// markers, polylines, etc. without a real DOM map. The factory re-exports the
// manual mock's default as the module default (leaflet is a default export).
vi.mock("leaflet", async () => {
  const mock = await import("../__mocks__/leaflet");
  return { default: mock.default };
});

import { DrawingManager } from "@/lib/drawing/drawing-manager";

/** A minimal fake Leaflet map exposing only what the DrawingManager touches. */
function makeFakeMap() {
  const handlers: Record<string, ((e: unknown) => void)[]> = {};
  return {
    on: vi.fn((event: string, fn: (e: unknown) => void) => {
      (handlers[event] ??= []).push(fn);
    }),
    off: vi.fn((event: string, fn: (e: unknown) => void) => {
      handlers[event] = (handlers[event] ?? []).filter((h) => h !== fn);
    }),
    removeLayer: vi.fn(),
    doubleClickZoom: { enable: vi.fn(), disable: vi.fn() },
    dragging: { enable: vi.fn(), disable: vi.fn() },
    // Pixel projection helpers used by the polygon snap-to-close check and the
    // measure-line label placement. The point exposes both an {x,y} shape and a
    // distanceTo() (the manager uses each in a different path).
    latLngToContainerPoint: vi.fn(() => ({ x: 0, y: 0, distanceTo: () => 1000 })),
    containerPointToLatLng: vi.fn(() => ({ lat: 0, lng: 0 })),
    // Emit a synthetic leaflet mouse event into a registered handler.
    fire(event: string, lat: number, lng: number) {
      for (const h of handlers[event] ?? []) h({ latlng: { lat, lng } });
    },
    _handlers: handlers,
  };
}

type FakeMap = ReturnType<typeof makeFakeMap>;

function makeManager(map: FakeMap) {
  // The fake map satisfies the subset of L.Map the manager calls; the cast keeps
  // the test focused on behaviour rather than reconstructing the full leaflet type.
  return new DrawingManager(map as unknown as import("leaflet").Map);
}

describe("DrawingManager imperative surface", () => {
  let addSpy: ReturnType<typeof vi.spyOn>;
  let removeSpy: ReturnType<typeof vi.spyOn>;

  /** Count document listener registrations of a given event type. */
  const countByType = (spy: ReturnType<typeof vi.spyOn>, type: string): number =>
    (spy.mock.calls as unknown as unknown[][]).filter((call) => call[0] === type).length;

  beforeEach(() => {
    addSpy = vi.spyOn(document, "addEventListener");
    removeSpy = vi.spyOn(document, "removeEventListener");
  });

  afterEach(() => {
    addSpy.mockRestore();
    removeSpy.mockRestore();
  });

  it("starts idle (mode null, no vertices)", () => {
    const manager = makeManager(makeFakeMap());
    expect(manager.getMode()).toBeNull();
    expect(manager.getVertexCount()).toBe(0);
  });

  it("enters polygon mode and collects vertices from map clicks", () => {
    const map = makeFakeMap();
    const manager = makeManager(map);

    manager.startPolygonDraw();
    expect(manager.getMode()).toBe("polygon");

    map.fire("click", 1, 1);
    map.fire("click", 2, 2);
    expect(manager.getVertexCount()).toBe(2);
  });

  it("popVertex removes the last polygon vertex while drawing", () => {
    const map = makeFakeMap();
    const onVertices = vi.fn();
    const manager = makeManager(map);
    manager.setCallbacks({ onVerticesUpdate: onVertices });

    manager.startPolygonDraw();
    map.fire("click", 1, 1);
    map.fire("click", 2, 2);
    onVertices.mockClear();

    manager.popVertex();
    expect(manager.getVertexCount()).toBe(1);
    expect(onVertices).toHaveBeenCalledWith([[1, 1]]);
  });

  it("popVertex is a no-op when not drawing a polygon", () => {
    const manager = makeManager(makeFakeMap());
    expect(() => manager.popVertex()).not.toThrow();
    expect(manager.getVertexCount()).toBe(0);

    manager.startMeasure();
    expect(() => manager.popVertex()).not.toThrow();
  });

  it("complete finishes a polygon with 3+ vertices and exits draw mode", () => {
    const map = makeFakeMap();
    const onComplete = vi.fn();
    const manager = makeManager(map);
    manager.setCallbacks({ onPolygonComplete: onComplete });

    manager.startPolygonDraw();
    map.fire("click", 0, 0);
    map.fire("click", 0, 1);
    map.fire("click", 1, 1);

    manager.complete();
    expect(onComplete).toHaveBeenCalledTimes(1);
    expect(manager.getMode()).toBeNull();
  });

  it("complete does nothing with fewer than 3 polygon vertices", () => {
    const map = makeFakeMap();
    const onComplete = vi.fn();
    const manager = makeManager(map);
    manager.setCallbacks({ onPolygonComplete: onComplete });

    manager.startPolygonDraw();
    map.fire("click", 0, 0);
    map.fire("click", 0, 1);

    manager.complete();
    expect(onComplete).not.toHaveBeenCalled();
    expect(manager.getMode()).toBe("polygon");
  });

  it("cancelDraw exits draw mode and fires the cancel callback", () => {
    const map = makeFakeMap();
    const onCancel = vi.fn();
    const manager = makeManager(map);
    manager.setCallbacks({ onCancel });

    manager.startPolygonDraw();
    manager.cancelDraw();
    expect(manager.getMode()).toBeNull();
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("cancelDraw is a no-op (no callback) when idle", () => {
    const onCancel = vi.fn();
    const manager = makeManager(makeFakeMap());
    manager.setCallbacks({ onCancel });
    manager.cancelDraw();
    expect(onCancel).not.toHaveBeenCalled();
  });

  it("complete finishes a measurement and exits measure mode", () => {
    const map = makeFakeMap();
    const manager = makeManager(map);
    manager.startMeasure();
    expect(manager.getMode()).toBe("measure");

    map.fire("click", 0, 0);
    map.fire("click", 1, 1);
    manager.complete();
    expect(manager.getMode()).toBeNull();
  });

  describe("keyboard ownership invariant", () => {
    it("registers NO document keydown listener for polygon mode", () => {
      const manager = makeManager(makeFakeMap());
      manager.startPolygonDraw();
      expect(countByType(addSpy, "keydown")).toBe(0);
    });

    it("registers NO document keydown listener for circle mode", () => {
      const manager = makeManager(makeFakeMap());
      manager.startCircleDraw();
      expect(countByType(addSpy, "keydown")).toBe(0);
    });

    it("registers NO document keydown listener for measure mode", () => {
      const manager = makeManager(makeFakeMap());
      manager.startMeasure();
      expect(countByType(addSpy, "keydown")).toBe(0);
    });

    it("removes NO document keydown listener on cancel (none were added)", () => {
      const manager = makeManager(makeFakeMap());
      manager.startPolygonDraw();
      manager.cancelDraw();
      expect(countByType(removeSpy, "keydown")).toBe(0);
    });
  });
});
