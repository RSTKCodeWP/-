/**
 * @module no-fly-zones
 * @description Static no-fly zone data for major Indian airports and restricted areas.
 * Rendered as red semi-transparent polygons on the map.
 * @license GPL-3.0-only
 */

export interface NoFlyZone {
  name: string;
  type: "airport" | "military" | "restricted";
  /** Approximate center for label placement [lat, lon]. */
  center: [number, number];
  /** Polygon boundary points [lat, lon][]. For airports, approximated as circle vertices. */
  polygon: [number, number][];
}

/**
 * Generate a circle approximation polygon (32 vertices) centered at [lat, lon]
 * with given radius in meters.
 */
function circlePolygon(lat: number, lon: number, radiusM: number, points = 32): [number, number][] {
  const R = 6371000;
  const result: [number, number][] = [];
  for (let i = 0; i < points; i++) {
    const angle = (2 * Math.PI * i) / points;
    const dLat = (radiusM * Math.cos(angle)) / R;
    const dLon = (radiusM * Math.sin(angle)) / (R * Math.cos((lat * Math.PI) / 180));
    result.push([
      lat + (dLat * 180) / Math.PI,
      lon + (dLon * 180) / Math.PI,
    ]);
  }
  return result;
}

/** 5 km radius around major Indian airports (DGCA standard no-fly perimeter). */
const AIRPORT_RADIUS = 5000;

export const NO_FLY_ZONES: NoFlyZone[] = [
  {
    name: "DEL - Indira Gandhi Intl",
    type: "airport",
    center: [28.5562, 77.1000],
    polygon: circlePolygon(28.5562, 77.1000, AIRPORT_RADIUS),
  },
  {
    name: "BLR - Kempegowda Intl",
    type: "airport",
    center: [13.1979, 77.7063],
    polygon: circlePolygon(13.1979, 77.7063, AIRPORT_RADIUS),
  },
  {
    name: "BOM - Chhatrapati Shivaji Intl",
    type: "airport",
    center: [19.0896, 72.8656],
    polygon: circlePolygon(19.0896, 72.8656, AIRPORT_RADIUS),
  },
  {
    name: "MAA - Chennai Intl",
    type: "airport",
    center: [12.9941, 80.1709],
    polygon: circlePolygon(12.9941, 80.1709, AIRPORT_RADIUS),
  },
  {
    name: "HYD - Rajiv Gandhi Intl",
    type: "airport",
    center: [17.2403, 78.4294],
    polygon: circlePolygon(17.2403, 78.4294, AIRPORT_RADIUS),
  },
  {
    name: "CCU - Netaji Subhas Chandra Bose Intl",
    type: "airport",
    center: [22.6547, 88.4467],
    polygon: circlePolygon(22.6547, 88.4467, AIRPORT_RADIUS),
  },
];
