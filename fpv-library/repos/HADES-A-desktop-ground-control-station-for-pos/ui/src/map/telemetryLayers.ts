import type { Feature, FeatureCollection, Geometry, LineString, Point, Polygon } from "geojson";

import type { DronePose } from "../store/telemetry";
import type { LngLat } from "./geo";
import { toLngLat } from "./geo";

/* GeoJSON builders for the map's non-pin telemetry layers (DESIGN-SYSTEM §5.1; impl-plan
 * Task 5.5c): the drone flight TRACK, the drone POINT (+heading), the current camera
 * FOOTPRINT, and the accumulated searched-area COVERAGE — the design's "most important
 * non-pin layer." All take [lon,lat] (the map-edge order) and return ready-to-render FCs. */

function fc<G extends Geometry>(features: Feature<G>[]): FeatureCollection<G> {
  return { type: "FeatureCollection", features };
}

export function trackGeoJSON(trail: LngLat[]): FeatureCollection<LineString> {
  if (trail.length < 2) return fc<LineString>([]);
  return fc<LineString>([
    { type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: trail } },
  ]);
}

export function droneGeoJSON(pose: DronePose | null): FeatureCollection<Point> {
  if (!pose) return fc<Point>([]);
  return fc<Point>([
    {
      type: "Feature",
      properties: { heading_deg: pose.heading_deg, agl_m: pose.agl_m },
      geometry: { type: "Point", coordinates: toLngLat(pose.lat, pose.lon) },
    },
  ]);
}

function closedRing(corners: LngLat[]): LngLat[] {
  const ring = [...corners];
  const first = ring[0];
  const last = ring[ring.length - 1];
  if (first && last && (first[0] !== last[0] || first[1] !== last[1])) ring.push(first);
  return ring;
}

export function footprintGeoJSON(corners: LngLat[] | null): FeatureCollection<Polygon> {
  if (!corners || corners.length < 3) return fc<Polygon>([]);
  return fc<Polygon>([
    { type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [closedRing(corners)] } },
  ]);
}

export function coverageGeoJSON(swept: LngLat[][]): FeatureCollection<Polygon> {
  return fc<Polygon>(
    swept
      .filter((c) => c.length >= 3)
      .map((corners) => ({
        type: "Feature" as const,
        properties: {},
        geometry: { type: "Polygon" as const, coordinates: [closedRing(corners)] },
      })),
  );
}
