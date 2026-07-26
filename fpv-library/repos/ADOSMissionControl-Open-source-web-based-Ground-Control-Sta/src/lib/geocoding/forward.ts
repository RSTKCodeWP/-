/**
 * @module geocoding/forward
 * @description Forward geocoding via Nominatim (place name -> coordinates) for
 * the map location-search box. Honors the shared 1 req/s throttle + User-Agent,
 * caches results, never throws, and returns [] on any failure/offline. Callers
 * should try `parseLatLon` first (offline, no network) before falling back here.
 * @license GPL-3.0-only
 */

import { get as idbGet, set as idbSet } from "idb-keyval";
import { acquireFetchSlot, NOMINATIM_USER_AGENT } from "./nominatim-throttle";

export interface ForwardGeocodeResult {
  /** Friendly display name from Nominatim. */
  name: string;
  lat: number;
  lon: number;
}

const IDB_PREFIX = "altcmd:geocode:fwd:";
const NOMINATIM_URL = "https://nominatim.openstreetmap.org/search";

interface NominatimSearchItem {
  display_name?: string;
  lat?: string;
  lon?: string;
}

async function idbGetCached(key: string): Promise<ForwardGeocodeResult[] | undefined> {
  try {
    return (await idbGet(`${IDB_PREFIX}${key}`)) as ForwardGeocodeResult[] | undefined;
  } catch {
    return undefined;
  }
}

/**
 * Geocode a place-name query into up to `limit` candidate locations. Returns []
 * on any failure so the caller can degrade gracefully.
 */
export async function forwardGeocode(query: string, limit = 5): Promise<ForwardGeocodeResult[]> {
  const q = query.trim();
  if (q.length < 2) return [];

  const key = `${limit}:${q.toLowerCase()}`;
  const cached = await idbGetCached(key);
  if (cached) return cached;

  try {
    await acquireFetchSlot();
    const url = `${NOMINATIM_URL}?format=jsonv2&q=${encodeURIComponent(q)}&limit=${limit}`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 5000);
    const res = await fetch(url, {
      signal: controller.signal,
      headers: { "User-Agent": NOMINATIM_USER_AGENT, Accept: "application/json" },
    });
    clearTimeout(timer);
    if (!res.ok) return [];
    const body = (await res.json()) as NominatimSearchItem[];
    if (!Array.isArray(body)) return [];
    const results = body
      .map((i) => ({ name: i.display_name ?? "", lat: Number(i.lat), lon: Number(i.lon) }))
      .filter((r) => r.name && Number.isFinite(r.lat) && Number.isFinite(r.lon));
    if (results.length > 0) {
      try { await idbSet(`${IDB_PREFIX}${key}`, results); } catch { /* non-fatal */ }
    }
    return results;
  } catch {
    return [];
  }
}
