/**
 * Zone alerting geometry — decides which traffic contacts sit inside which
 * perimeter alert zones. Pure functions (no React / no store) so the detection
 * logic is unit-testable. Detect-and-alert only; nothing here mitigates.
 */
import type { AlertZone, TrafficContact } from '../../../../shared/traffic-types';

const EARTH_R = 6371000;

export function haversineMeters(aLat: number, aLon: number, bLat: number, bLon: number): number {
  const dLat = ((bLat - aLat) * Math.PI) / 180;
  const dLon = ((bLon - aLon) * Math.PI) / 180;
  const s =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((aLat * Math.PI) / 180) * Math.cos((bLat * Math.PI) / 180) * Math.sin(dLon / 2) ** 2;
  return EARTH_R * 2 * Math.atan2(Math.sqrt(s), Math.sqrt(1 - s));
}

/** Ray-casting point-in-polygon on lat/lon (fine at perimeter scales). */
export function pointInPolygon(lat: number, lon: number, ring: Array<{ lat: number; lon: number }>): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const a = ring[i]!;
    const b = ring[j]!;
    const intersect =
      a.lat > lat !== b.lat > lat &&
      lon < ((b.lon - a.lon) * (lat - a.lat)) / (b.lat - a.lat) + a.lon;
    if (intersect) inside = !inside;
  }
  return inside;
}

/** Is a contact inside the zone's footprint AND altitude band? */
export function contactInZone(contact: TrafficContact, zone: AlertZone): boolean {
  if (!zone.enabled) return false;

  // Altitude gate (only when the contact reports an altitude).
  if (contact.altMeters !== undefined) {
    if (zone.minAltMeters !== undefined && contact.altMeters < zone.minAltMeters) return false;
    if (zone.maxAltMeters !== undefined && contact.altMeters > zone.maxAltMeters) return false;
  }

  if (zone.shape === 'circle' && zone.center && zone.radiusMeters !== undefined) {
    return haversineMeters(contact.lat, contact.lon, zone.center.lat, zone.center.lon) <= zone.radiusMeters;
  }
  if (zone.shape === 'polygon' && zone.polygon && zone.polygon.length >= 3) {
    return pointInPolygon(contact.lat, contact.lon, zone.polygon);
  }
  return false;
}

/** Stable key for an (zone, contact) intrusion pair. */
export function intrusionKey(zoneId: string, contactId: string): string {
  return `${zoneId}::${contactId}`;
}

export interface ZoneEvaluation {
  /** Current (zoneId::contactId) pairs inside a zone this frame. */
  current: Set<string>;
  /** Contact ids inside each zone (for map highlighting), keyed by zone id. */
  byZone: Map<string, Set<string>>;
}

/** Evaluate every contact against every zone. */
export function evaluateZones(contacts: TrafficContact[], zones: AlertZone[]): ZoneEvaluation {
  const current = new Set<string>();
  const byZone = new Map<string, Set<string>>();
  for (const zone of zones) {
    if (!zone.enabled) continue;
    const inSet = new Set<string>();
    for (const c of contacts) {
      if (contactInZone(c, zone)) {
        current.add(intrusionKey(zone.id, c.id));
        inSet.add(c.id);
      }
    }
    if (inSet.size > 0) byZone.set(zone.id, inSet);
  }
  return { current, byZone };
}
