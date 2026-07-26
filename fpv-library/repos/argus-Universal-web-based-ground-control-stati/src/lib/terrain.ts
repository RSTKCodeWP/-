/**
 * Terrain elevation service.
 *
 * Fetches ground elevation data from the backend SRTM API and provides
 * helpers for terrain-following mission planning.
 */

import { apiUrl } from './backend';

const elevationCache = new Map<string, number>();

/**
 * Get ground elevation (MSL) for a single point.
 * Results are cached to 4 decimal places (~11 m resolution).
 */
export async function getElevation(lat: number, lon: number): Promise<number> {
  const key = `${lat.toFixed(4)},${lon.toFixed(4)}`;
  if (elevationCache.has(key)) return elevationCache.get(key)!;

  const url = apiUrl(`/api/terrain/elevation?points=${lat.toFixed(6)},${lon.toFixed(6)}`);
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Terrain API ${res.status}`);
  const data: { elevations: number[] } = await res.json();
  const elev = data.elevations[0];
  elevationCache.set(key, elev);
  return elev;
}

/**
 * Batch-fetch ground elevations for an array of points.
 * API expects: /api/terrain/elevation?points=lat1,lon1;lat2,lon2;...
 * Returns:     { elevations: [elev1, elev2, ...] }
 */
export async function getElevationProfile(points: { lat: number; lon: number }[]): Promise<number[]> {
  if (points.length === 0) return [];

  // Check cache first — return early if every point is cached
  const keys = points.map((p) => `${p.lat.toFixed(4)},${p.lon.toFixed(4)}`);
  const allCached = keys.every((k) => elevationCache.has(k));
  if (allCached) return keys.map((k) => elevationCache.get(k)!);

  // Build query string (semicolon-separated lat,lon pairs)
  const pairs = points.map((p) => `${p.lat.toFixed(6)},${p.lon.toFixed(6)}`).join(';');
  const url = apiUrl(`/api/terrain/elevation?points=${pairs}`);
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Terrain API ${res.status}`);
  const data: { elevations: number[] } = await res.json();

  // Populate cache
  for (let i = 0; i < points.length; i++) {
    elevationCache.set(keys[i], data.elevations[i]);
  }

  return data.elevations;
}

/**
 * Adjust waypoint altitudes so that every point maintains a constant AGL
 * clearance over the terrain.
 *
 * Mission items use frame=3 (GLOBAL_RELATIVE_ALT) so the FC interprets alt
 * as meters above home. SRTM returns MSL, so we subtract the home ground
 * elevation: alt = (groundMSL - homeMSL) + targetAGL.
 *
 * @param homeLatLon  Home position for MSL-to-relative conversion. If null,
 *                    the first waypoint's ground elevation is used as reference.
 * @returns A new array (original waypoints are not mutated).
 */
export async function adjustWaypointsForTerrain(
  waypoints: { lat: number; lon: number; alt: number }[],
  targetAGL: number,
  homeLatLon?: { lat: number; lon: number } | null,
): Promise<{ lat: number; lon: number; alt: number }[]> {
  const elevations = await getElevationProfile(waypoints);
  let homeElev: number;
  if (homeLatLon && (homeLatLon.lat !== 0 || homeLatLon.lon !== 0)) {
    homeElev = await getElevation(homeLatLon.lat, homeLatLon.lon);
  } else {
    homeElev = elevations[0];
  }
  return waypoints.map((wp, i) => ({
    ...wp,
    alt: Math.round(elevations[i] - homeElev + targetAGL),
  }));
}

/**
 * Interpolate additional points along a route for a denser terrain profile.
 * Returns the original waypoint positions plus evenly-spaced intermediate
 * points (roughly one every `stepMeters`).
 */
export function interpolateRoute(
  waypoints: { lat: number; lon: number }[],
  stepMeters: number = 50,
): { lat: number; lon: number; wpIndex: number }[] {
  if (waypoints.length < 2) {
    return waypoints.map((p, i) => ({ lat: p.lat, lon: p.lon, wpIndex: i }));
  }

  const result: { lat: number; lon: number; wpIndex: number }[] = [];

  for (let i = 0; i < waypoints.length - 1; i++) {
    const a = waypoints[i];
    const b = waypoints[i + 1];
    const dlat = (b.lat - a.lat) * 111320;
    const dlon = (b.lon - a.lon) * 111320 * Math.cos((a.lat * Math.PI) / 180);
    const segLen = Math.sqrt(dlat * dlat + dlon * dlon);
    const steps = Math.max(1, Math.ceil(segLen / stepMeters));

    for (let s = 0; s < steps; s++) {
      const frac = s / steps;
      result.push({
        lat: a.lat + (b.lat - a.lat) * frac,
        lon: a.lon + (b.lon - a.lon) * frac,
        wpIndex: s === 0 ? i : -1,
      });
    }
  }
  // Final waypoint
  const last = waypoints[waypoints.length - 1];
  result.push({ lat: last.lat, lon: last.lon, wpIndex: waypoints.length - 1 });

  return result;
}
