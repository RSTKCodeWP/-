import type { ContactRecord } from "../types/wire";
import { contactStatus } from "../ui/contactStatus";
import type { Status } from "../ui/status";

/* The map-edge coordinate adapter — the ONE sanctioned place where HADES's (lat, lon)
 * degrees order flips to MapLibre's [lon, lat] (DESIGN.md §3.1). Everything upstream stays
 * (lat, lon); this is the single, tested swap so it can never be a silent inline mistake. */

export type LngLat = [number, number];

const METERS_PER_DEG_LAT = 111_320;

export function toLngLat(lat: number, lon: number): LngLat {
  return [lon, lat];
}

export function metersToDegreesLat(m: number): number {
  return m / METERS_PER_DEG_LAT;
}

export interface ContactPinProps {
  track_id: number;
  status: Status;
  tier: ContactRecord["priority_tier"];
  actionability: ContactRecord["actionability_class"];
  r95_m: number;
  detection_conf: number;
  localization_conf: number;
  heading_limited: boolean;
  selected: boolean;
}

export interface ContactFeature {
  type: "Feature";
  geometry: { type: "Point"; coordinates: LngLat };
  properties: ContactPinProps;
}

export interface ContactFeatureCollection {
  type: "FeatureCollection";
  features: ContactFeature[];
}

/* Map located contacts to a GeoJSON FeatureCollection for the pin layer. A contact with a
 * null fix (CUE_ONLY, no fused coordinate) is OMITTED — it must not plot a false pin
 * (it surfaces in the list + as a CUE-ONLY cue, but never as a point on the map). */
export function contactsToGeoJSON(
  contacts: Iterable<ContactRecord>,
  selectedId: number | null = null,
): ContactFeatureCollection {
  const features: ContactFeature[] = [];
  for (const c of contacts) {
    if (c.lat === null || c.lon === null) continue;
    features.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: toLngLat(c.lat, c.lon) },
      properties: {
        track_id: c.track_id,
        status: contactStatus(c),
        tier: c.priority_tier,
        actionability: c.actionability_class,
        r95_m: c.r95_m,
        detection_conf: c.detection_conf,
        localization_conf: c.localization_conf,
        heading_limited: c.heading_limited,
        selected: c.track_id === selectedId,
      },
    });
  }
  return { type: "FeatureCollection", features };
}
