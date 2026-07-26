import { describe, expect, it } from "vitest";

import { coverageGeoJSON, droneGeoJSON, footprintGeoJSON, trackGeoJSON } from "./telemetryLayers";
import type { DronePose } from "../store/telemetry";

const pose: DronePose = { lat: 30.21, lon: -88.52, heading_deg: 90, agl_m: 30 };
const footprint: [number, number][] = [
  [-88.522, 30.213],
  [-88.518, 30.213],
  [-88.518, 30.209],
  [-88.522, 30.209],
];

describe("trackGeoJSON", () => {
  it("builds a LineString from the trail", () => {
    const fc = trackGeoJSON([[-88.52, 30.21], [-88.521, 30.211]]);
    expect(fc.features[0].geometry.type).toBe("LineString");
    expect(fc.features[0].geometry.coordinates).toHaveLength(2);
  });

  it("emits no feature for a trail with <2 points (nothing to draw)", () => {
    expect(trackGeoJSON([]).features).toHaveLength(0);
    expect(trackGeoJSON([[-88.52, 30.21]]).features).toHaveLength(0);
  });
});

describe("droneGeoJSON", () => {
  it("builds a point at the drone with its heading as a property", () => {
    const fc = droneGeoJSON(pose);
    expect(fc.features[0].geometry).toEqual({ type: "Point", coordinates: [-88.52, 30.21] });
    expect(fc.features[0].properties?.heading_deg).toBe(90);
  });

  it("emits no feature when there is no pose", () => {
    expect(droneGeoJSON(null).features).toHaveLength(0);
  });
});

describe("footprintGeoJSON", () => {
  it("builds a closed polygon from the footprint corners", () => {
    const fc = footprintGeoJSON(footprint);
    const ring = fc.features[0].geometry.coordinates[0];
    expect(ring[0]).toEqual(ring[ring.length - 1]); // closed
  });

  it("emits no feature when there is no footprint", () => {
    expect(footprintGeoJSON(null).features).toHaveLength(0);
  });
});

describe("coverageGeoJSON", () => {
  it("builds one polygon per swept footprint (the searched-area layer)", () => {
    const fc = coverageGeoJSON([footprint, footprint]);
    expect(fc.features).toHaveLength(2);
    expect(fc.features[0].geometry.type).toBe("Polygon");
  });

  it("emits an empty collection when nothing has been searched yet", () => {
    expect(coverageGeoJSON([]).features).toHaveLength(0);
  });
});
