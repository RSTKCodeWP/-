import { beforeEach, describe, expect, it } from "vitest";

import { useLayerStore, type LayerKey } from "./layers";

/* Operator layer toggles for the map (impl-plan Task 5.5d): show/hide coverage, track,
 * footprint, uncertainty rings. The configurability that earns its keep on an ops map is
 * declutter/layers, not panel geometry (research brief §3). All on by default. */

describe("layer-toggle store", () => {
  beforeEach(() => useLayerStore.getState().reset());

  it("all layers are visible by default", () => {
    const s = useLayerStore.getState();
    for (const k of ["coverage", "track", "footprint", "uncertainty"] as LayerKey[]) {
      expect(s.visible[k]).toBe(true);
    }
  });

  it("toggles a single layer without touching others", () => {
    useLayerStore.getState().toggle("coverage");
    const s = useLayerStore.getState();
    expect(s.visible.coverage).toBe(false);
    expect(s.visible.track).toBe(true);
  });

  it("toggling twice returns to visible", () => {
    useLayerStore.getState().toggle("track");
    useLayerStore.getState().toggle("track");
    expect(useLayerStore.getState().visible.track).toBe(true);
  });
});
