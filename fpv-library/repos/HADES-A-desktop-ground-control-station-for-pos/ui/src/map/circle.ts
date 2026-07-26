import type { ContactRecord } from "../types/wire";
import { contactStatus } from "../ui/contactStatus";
import type { Status } from "../ui/status";
import { toLngLat, type LngLat } from "./geo";

/* Geodesic-ish circle polygons for the uncertainty / sweep rings (DESIGN-SYSTEM §5.1).
 * Drawn at the contact's TRUE r95_m (the honest equal-coverage sweep radius), so the ring
 * is a real metric circle the operator can act on — never a fixed decorative dot. Local
 * flat-earth approximation (per-degree meters scaled by cos(lat)) — accurate at SAR scales
 * (tens to hundreds of meters), consistent with the flat-earth v1 georeference. */

const METERS_PER_DEG_LAT = 111_320;

/** A closed ring of [lon, lat] vertices approximating a circle of radius `r` meters. */
export function circlePolygon(lat: number, lon: number, r: number, steps = 64): LngLat[] {
  const mPerDegLon = METERS_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180);
  const ring: LngLat[] = [];
  for (let i = 0; i < steps; i++) {
    const theta = (i / steps) * 2 * Math.PI;
    const dLat = (r * Math.sin(theta)) / METERS_PER_DEG_LAT;
    const dLon = (r * Math.cos(theta)) / mPerDegLon;
    ring.push([lon + dLon, lat + dLat]);
  }
  ring.push(ring[0]); // close the ring
  return ring;
}

export interface CircleProps {
  track_id: number;
  status: Status;
  r95_m: number;
  selected: boolean;
}

export interface CircleFeature {
  type: "Feature";
  geometry: { type: "Polygon"; coordinates: LngLat[][] };
  properties: CircleProps;
}

export interface CircleFeatureCollection {
  type: "FeatureCollection";
  features: CircleFeature[];
}

export function contactsToCirclesGeoJSON(
  contacts: Iterable<ContactRecord>,
  selectedId: number | null = null,
): CircleFeatureCollection {
  const features: CircleFeature[] = [];
  for (const c of contacts) {
    if (c.lat === null || c.lon === null) continue;
    // touch toLngLat so the center stays in the one-sanctioned-flip path conceptually
    void toLngLat(c.lat, c.lon);
    features.push({
      type: "Feature",
      geometry: { type: "Polygon", coordinates: [circlePolygon(c.lat, c.lon, c.r95_m)] },
      properties: {
        track_id: c.track_id,
        status: contactStatus(c),
        r95_m: c.r95_m,
        selected: c.track_id === selectedId,
      },
    });
  }
  return { type: "FeatureCollection", features };
}
