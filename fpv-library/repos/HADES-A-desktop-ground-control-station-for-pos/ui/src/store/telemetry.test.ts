import { beforeEach, describe, expect, it } from "vitest";

import { useTelemetryStore } from "./telemetry";

/* Drone telemetry for the map's non-pin layers (impl-plan Task 5.5c): the drone's current
 * pose + heading, its accumulated TRACK (a trail of past positions), the current camera
 * FOOTPRINT polygon, and the accumulated searched-area COVERAGE. The service owns the
 * footprint geometry (georeference SSoT); the UI store just accumulates what it's given. */

describe("telemetry store", () => {
  beforeEach(() => useTelemetryStore.getState().reset());

  it("starts empty (no drone fix yet)", () => {
    const s = useTelemetryStore.getState();
    expect(s.pose).toBeNull();
    expect(s.track).toHaveLength(0);
    expect(s.footprint).toBeNull();
  });

  it("records a pose and appends to the track trail", () => {
    const s = useTelemetryStore.getState();
    s.pushPose({ lat: 30.21, lon: -88.52, heading_deg: 90, agl_m: 30 });
    s.pushPose({ lat: 30.211, lon: -88.521, heading_deg: 95, agl_m: 30 });

    const after = useTelemetryStore.getState();
    expect(after.pose?.heading_deg).toBe(95);
    expect(after.track).toHaveLength(2);
    expect(after.track[1]).toEqual([-88.521, 30.211]); // [lon,lat] for the map edge
  });

  it("sets the current camera footprint (polygon corners from the service)", () => {
    const corners: [number, number][] = [
      [-88.522, 30.213],
      [-88.518, 30.213],
      [-88.518, 30.209],
      [-88.522, 30.209],
    ];
    useTelemetryStore.getState().setFootprint(corners);
    expect(useTelemetryStore.getState().footprint).toEqual(corners);
  });

  it("accumulates searched-area coverage as footprints arrive", () => {
    const s = useTelemetryStore.getState();
    s.setFootprint([[-88.52, 30.21], [-88.51, 30.21], [-88.51, 30.2], [-88.52, 30.2]]);
    s.setFootprint([[-88.53, 30.22], [-88.52, 30.22], [-88.52, 30.21], [-88.53, 30.21]]);
    expect(useTelemetryStore.getState().coverage).toHaveLength(2); // two swept footprints
  });

  it("caps the track length so a long mission does not grow unbounded", () => {
    const s = useTelemetryStore.getState();
    for (let i = 0; i < 5000; i++) s.pushPose({ lat: 30 + i * 1e-5, lon: -88, heading_deg: 0, agl_m: 30 });
    expect(useTelemetryStore.getState().track.length).toBeLessThanOrEqual(2000);
  });
});
