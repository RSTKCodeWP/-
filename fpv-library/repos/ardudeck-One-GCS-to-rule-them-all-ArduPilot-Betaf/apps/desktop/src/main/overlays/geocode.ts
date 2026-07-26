/**
 * geocode — place/address lookup for the "Go to location" search.
 *
 * Runs in main (like the wind/airspace fetches) so the external request carries
 * a proper User-Agent and isn't subject to renderer CORS. Uses OpenStreetMap
 * Nominatim, which is free and keyless; we keep volume low (manual searches,
 * one result set at a time) per their usage policy.
 */

import type { GeocodeResult } from '../../shared/overlay-types.js';

const NOMINATIM = 'https://nominatim.openstreetmap.org/search';
const USER_AGENT = 'ArduDeck Area Editor (https://ardudeck.com)';

export async function geocodeSearch(query: string): Promise<GeocodeResult[]> {
  const q = query.trim();
  if (!q) return [];

  const url = `${NOMINATIM}?format=jsonv2&limit=5&q=${encodeURIComponent(q)}`;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);
  try {
    const res = await fetch(url, {
      headers: { 'User-Agent': USER_AGENT, Accept: 'application/json' },
      signal: controller.signal,
    });
    if (!res.ok) return [];
    const raw = (await res.json()) as Array<{ lat: string; lon: string; display_name: string }>;
    return raw
      .map((r) => ({ label: r.display_name, lat: Number(r.lat), lon: Number(r.lon) }))
      .filter((r) => Number.isFinite(r.lat) && Number.isFinite(r.lon));
  } catch {
    return [];
  } finally {
    clearTimeout(timeout);
  }
}
