import { describe, expect, it } from "vitest";

import { circlePolygon, contactsToCirclesGeoJSON } from "./circle";
import type { ContactRecord } from "../types/wire";

/* Uncertainty/sweep circles are drawn at the TRUE r95_m radius (DESIGN-SYSTEM §5.1) — the
 * honest equal-coverage sweep radius, never a fixed decorative dot. A geodesic circle as a
 * GeoJSON polygon, so MapLibre renders a real metric circle. */

function c(over: Partial<ContactRecord>): ContactRecord {
  return {
    type: "contact",
    frame_id: 0,
    track_id: 1,
    lat: 30,
    lon: -88,
    r95_m: 50,
    actionability_class: "SWEEP",
    semi_major_m: 22,
    semi_minor_m: 14,
    orientation_deg: 30,
    priority_tier: "candidate",
    convergence_state: "STABLE",
    heading_limited: false,
    aspect_spread_deg: 40,
    detection_conf: 0.9,
    localization_conf: 0.6,
    mc_reject_fraction: 0,
    moving_suspected: false,
    age_frames: 30,
    ...over,
  };
}

describe("circlePolygon", () => {
  it("returns a closed ring (first point == last point)", () => {
    const ring = circlePolygon(30, -88, 50, 32);
    expect(ring[0]).toEqual(ring[ring.length - 1]);
  });

  it("has the requested number of steps (+1 for closure)", () => {
    expect(circlePolygon(30, -88, 50, 32)).toHaveLength(33);
  });

  it("every vertex is ~r meters from the center (within 1% at this scale)", () => {
    const lat = 30,
      lon = -88,
      r = 100;
    const ring = circlePolygon(lat, lon, r, 64);
    // crude planar distance check using local meters-per-degree
    const mPerDegLat = 111_320;
    const mPerDegLon = 111_320 * Math.cos((lat * Math.PI) / 180);
    for (const [vlon, vlat] of ring) {
      const dx = (vlon - lon) * mPerDegLon;
      const dy = (vlat - lat) * mPerDegLat;
      const dist = Math.hypot(dx, dy);
      expect(Math.abs(dist - r) / r).toBeLessThan(0.01);
    }
  });
});

describe("contactsToCirclesGeoJSON", () => {
  it("draws a circle polygon for each located contact at its r95_m", () => {
    const fc = contactsToCirclesGeoJSON([c({ track_id: 1, r95_m: 40 })]);
    expect(fc.features).toHaveLength(1);
    expect(fc.features[0].geometry.type).toBe("Polygon");
    expect(fc.features[0].properties.track_id).toBe(1);
  });

  it("omits a null-fix contact (no circle for a contact with no point)", () => {
    const fc = contactsToCirclesGeoJSON([c({ track_id: 2, lat: null, lon: null })]);
    expect(fc.features).toHaveLength(0);
  });

  it("carries status so the ring tints to match its pin", () => {
    const fc = contactsToCirclesGeoJSON([
      c({ track_id: 1, actionability_class: "PINPOINT", priority_tier: "strong" }),
    ]);
    expect(fc.features[0].properties.status).toBe("warning");
  });
});
