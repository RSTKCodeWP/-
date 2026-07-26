/**
 * provider — the traffic source contract + small geo helpers.
 *
 * Every source (local receiver, hosted ADS-B API, OpenSky, OGN) implements
 * TrafficProvider. The TrafficService owns lifecycle, viewport fan-out, and
 * merging; providers only know how to produce contacts for a viewport.
 */

import type { TrafficContact, TrafficSource, ViewportBbox } from '../../shared/traffic-types.js';

export interface ProviderContext {
  /** Push this provider's current contacts. The service merges + dedupes. */
  emit(contacts: TrafficContact[]): void;
  log(msg: string): void;
}

export interface TrafficProvider {
  readonly source: TrafficSource;
  readonly id: string;
  start(ctx: ProviderContext): void;
  setViewport(v: ViewportBbox): void;
  stop(): void;
}

export const KM_TO_NM = 1 / 1.852;

export interface LatLonBbox {
  lamin: number;
  lamax: number;
  lomin: number;
  lomax: number;
}

/** Convert a centre+radius viewport to a lat/lon bounding box (OpenSky style). */
export function viewportToBbox(v: ViewportBbox): LatLonBbox {
  const dLat = v.radiusKm / 111;
  const dLon = v.radiusKm / (111 * Math.max(0.01, Math.cos((v.lat * Math.PI) / 180)));
  return {
    lamin: v.lat - dLat,
    lamax: v.lat + dLat,
    lomin: v.lon - dLon,
    lomax: v.lon + dLon,
  };
}

/** Great-circle distance in km. */
export function distanceKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

/** Whether a point lies within the reported viewport. The viewport radius is the
 *  distance to the rectangle's corner, so a circle of that radius circumscribes
 *  the visible area; the margin keeps contacts just off-edge from popping. */
export function withinViewport(lat: number, lon: number, v: ViewportBbox, marginFactor = 1.25): boolean {
  return distanceKm(v.lat, v.lon, lat, lon) <= v.radiusKm * marginFactor;
}
