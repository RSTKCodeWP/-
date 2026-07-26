/**
 * proximity — pure geometry for traffic situational awareness: distance/bearing
 * from the operator's vehicle to a contact, and a severity tier driving the
 * highlight on the map. Visual only in alpha (audio alerts are a beta item).
 */

import type { TrafficContact } from '../../../../shared/traffic-types';

export type ProximityTier = 'none' | 'caution' | 'warning';

export interface OwnPosition {
  lat: number;
  lon: number;
  altMeters?: number;
}

export interface ProximityThresholds {
  rangeMeters: number;
  verticalMeters: number;
}

const R = 6371000; // earth radius, metres

export function haversineMeters(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

/** Initial bearing from point 1 to point 2, degrees true [0,360). */
export function bearingDeg(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const φ1 = (lat1 * Math.PI) / 180;
  const φ2 = (lat2 * Math.PI) / 180;
  const Δλ = ((lon2 - lon1) * Math.PI) / 180;
  const y = Math.sin(Δλ) * Math.cos(φ2);
  const x = Math.cos(φ1) * Math.sin(φ2) - Math.sin(φ1) * Math.cos(φ2) * Math.cos(Δλ);
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

export interface ProximityResult {
  tier: ProximityTier;
  distanceMeters: number;
  bearingDeg: number;
  /** Vertical separation in metres, or undefined when the contact alt is unknown. */
  verticalMeters?: number;
}

/**
 * Classify a contact relative to own position. `warning` = inside both the range
 * and vertical thresholds; `caution` = inside 2x either threshold. Unknown contact
 * altitude is treated as co-altitude (can't be ruled out → fail safe).
 */
export function classifyProximity(
  contact: TrafficContact,
  own: OwnPosition | null,
  t: ProximityThresholds,
): ProximityResult | null {
  if (!own) return null;
  const distanceMeters = haversineMeters(own.lat, own.lon, contact.lat, contact.lon);
  const bearing = bearingDeg(own.lat, own.lon, contact.lat, contact.lon);
  const vSep =
    contact.altMeters != null && own.altMeters != null
      ? Math.abs(contact.altMeters - own.altMeters)
      : undefined;
  const vWithin = (limit: number): boolean => vSep == null || vSep <= limit;

  let tier: ProximityTier = 'none';
  if (distanceMeters <= t.rangeMeters && vWithin(t.verticalMeters)) tier = 'warning';
  else if (distanceMeters <= t.rangeMeters * 2 && vWithin(t.verticalMeters * 2)) tier = 'caution';

  return { tier, distanceMeters, bearingDeg: bearing, verticalMeters: vSep };
}
