import { describe, expect, it } from "vitest";

import type { ContactRecord } from "../types/wire";
import { contactsToGeoJSON, metersToDegreesLat, toLngLat } from "./geo";

/* The map edge is the ONE sanctioned place where (lat, lon) flips to MapLibre's [lon, lat]
 * (DESIGN.md §3.1). These pure helpers own that flip + the contact→GeoJSON mapping so the
 * convention is enforceable in one tested place, never a silent inline swap. */

function c(over: Partial<ContactRecord>): ContactRecord {
  return {
    type: "contact",
    frame_id: 0,
    track_id: 1,
    lat: 30.21487,
    lon: -88.52103,
    r95_m: 18,
    actionability_class: "PINPOINT",
    semi_major_m: 22,
    semi_minor_m: 14,
    orientation_deg: 30,
    priority_tier: "strong",
    convergence_state: "STABLE",
    heading_limited: false,
    aspect_spread_deg: 40,
    detection_conf: 0.94,
    localization_conf: 0.71,
    mc_reject_fraction: 0.02,
    moving_suspected: false,
    age_frames: 3,
    ...over,
  };
}

describe("toLngLat", () => {
  it("flips (lat, lon) → [lon, lat] for MapLibre (the one sanctioned flip)", () => {
    expect(toLngLat(30.21487, -88.52103)).toEqual([-88.52103, 30.21487]);
  });
});

describe("contactsToGeoJSON", () => {
  it("emits a FeatureCollection with one point per LOCATED contact", () => {
    const fc = contactsToGeoJSON([c({ track_id: 42 })]);
    expect(fc.type).toBe("FeatureCollection");
    expect(fc.features).toHaveLength(1);
    expect(fc.features[0].geometry).toEqual({ type: "Point", coordinates: [-88.52103, 30.21487] });
  });

  it("OMITS a CUE_ONLY contact with null coordinates (no false Null-Island pin)", () => {
    const fc = contactsToGeoJSON([
      c({ track_id: 1, lat: 30, lon: -88 }),
      c({ track_id: 2, lat: null, lon: null, actionability_class: "CUE_ONLY" }),
    ]);
    expect(fc.features).toHaveLength(1);
    expect(fc.features[0].properties.track_id).toBe(1);
  });

  it("carries the encoding properties a pin needs (status, tier, r95, selected)", () => {
    const fc = contactsToGeoJSON([c({ track_id: 42 })], 42);
    const p = fc.features[0].properties;
    expect(p.track_id).toBe(42);
    expect(p.status).toBe("warning"); // PINPOINT strong → world-urgency
    expect(p.r95_m).toBe(18);
    expect(p.selected).toBe(true);
  });

  it("marks non-selected contacts selected=false", () => {
    const fc = contactsToGeoJSON([c({ track_id: 42 })], 7);
    expect(fc.features[0].properties.selected).toBe(false);
  });
});

describe("metersToDegreesLat", () => {
  it("converts meters to a latitude-degree delta (~111.32 km per degree)", () => {
    expect(metersToDegreesLat(111320)).toBeCloseTo(1.0, 3);
  });
});
