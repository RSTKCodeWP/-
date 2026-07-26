import type { AirspaceData, AirspaceType, AirportData, AirportFrequency, OverlayFetchParams } from '../../shared/overlay-types.js';

const BASE_URL = 'https://api.core.openaip.net/api';
const MIN_FETCH_INTERVAL_MS = 30_000; // 30 seconds
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

// ─── Cache ───────────────────────────────────────────────────────────────────

interface CacheEntry<T> {
  data: T;
  timestamp: number;
  key: string;
}

let airspaceCache: CacheEntry<AirspaceData[]> | null = null;
let airportCache: CacheEntry<AirportData[]> | null = null;
let lastAirspaceFetch = 0;
let lastAirportFetch = 0;

function getCacheKey(params: OverlayFetchParams): string {
  const lat = Math.round(params.lat * 10) / 10;
  const lon = Math.round(params.lon * 10) / 10;
  const z = Math.round(params.zoom);
  return `${lat},${lon},${z}`;
}

function getRadiusForZoom(zoom: number): number {
  if (zoom < 6) return 500_000;
  if (zoom < 8) return 200_000;
  if (zoom < 10) return 100_000;
  return 50_000;
}

// ─── Airspace type mapping ───────────────────────────────────────────────────

function mapAirspaceType(typeId: number): AirspaceType {
  if (typeId === 1) return 'restricted';
  if (typeId === 3) return 'prohibited';
  if (typeId === 2) return 'danger';
  if (typeId === 4) return 'ctr';
  if (typeId === 5 || typeId === 9) return 'tma';
  return 'other';
}

function parseLimitFt(limit: Record<string, unknown>): number {
  const value = typeof limit.value === 'number' ? limit.value : 0;
  const unit = limit.unit;
  if (unit === 1) return Math.round(value * 3.28084); // meters to feet
  if (unit === 2) return value * 100; // FL to feet
  return value; // already feet
}

// ─── Fetch functions ─────────────────────────────────────────────────────────

export async function fetchAirspace(params: OverlayFetchParams, apiKey: string): Promise<AirspaceData[]> {
  const now = Date.now();
  const key = getCacheKey(params);

  if (now - lastAirspaceFetch < MIN_FETCH_INTERVAL_MS) {
    return airspaceCache?.data ?? [];
  }

  if (airspaceCache && airspaceCache.key === key && now - airspaceCache.timestamp < CACHE_TTL_MS) {
    return airspaceCache.data;
  }

  const radius = getRadiusForZoom(params.zoom);
  const url = `${BASE_URL}/airspaces?pos=${params.lat},${params.lon}&dist=${radius}&limit=200`;

  try {
    lastAirspaceFetch = now;
    const response = await fetch(url, {
      headers: { 'x-openaip-api-key': apiKey },
    });

    if (!response.ok) {
      console.warn(`[OpenAIP] Airspace fetch failed: ${response.status}`);
      return airspaceCache?.data ?? [];
    }

    const json = await response.json();
    const items: AirspaceData[] = [];

    for (const item of json.items ?? json) {
      const geometry = item.geometry;
      if (!geometry?.coordinates?.[0]) continue;

      const coords: Array<[number, number]> = geometry.coordinates[0].map(
        (c: number[]) => [c[1], c[0]], // GeoJSON [lon, lat] → [lat, lon]
      );

      items.push({
        name: item.name ?? '',
        type: mapAirspaceType(item.type ?? 0),
        points: coords,
        lowerLimitFt: parseLimitFt(item.lowerLimit ?? {}),
        upperLimitFt: parseLimitFt(item.upperLimit ?? {}),
      });
    }

    airspaceCache = { data: items, timestamp: now, key };
    return items;
  } catch (err) {
    console.warn('[OpenAIP] Airspace fetch error:', err);
    return airspaceCache?.data ?? [];
  }
}

export async function fetchAirports(params: OverlayFetchParams, apiKey: string): Promise<AirportData[]> {
  const now = Date.now();
  const key = getCacheKey(params);

  if (now - lastAirportFetch < MIN_FETCH_INTERVAL_MS) {
    return airportCache?.data ?? [];
  }

  if (airportCache && airportCache.key === key && now - airportCache.timestamp < CACHE_TTL_MS) {
    return airportCache.data;
  }

  const radius = getRadiusForZoom(params.zoom);
  const url = `${BASE_URL}/airports?pos=${params.lat},${params.lon}&dist=${radius}&limit=100`;

  try {
    lastAirportFetch = now;
    const response = await fetch(url, {
      headers: { 'x-openaip-api-key': apiKey },
    });

    if (!response.ok) {
      console.warn(`[OpenAIP] Airports fetch failed: ${response.status}`);
      return airportCache?.data ?? [];
    }

    const json = await response.json();
    const items: AirportData[] = [];

    for (const item of json.items ?? json) {
      const geo = item.geometry?.coordinates;
      if (!geo) continue;

      const freqs: AirportFrequency[] = [];
      for (const f of item.frequencies ?? []) {
        const val = typeof f.value === 'string' ? parseFloat(f.value) : f.value;
        if (val > 0) {
          freqs.push({ name: f.name ?? '', valueMhz: val, type: f.type ?? 0 });
        }
      }

      items.push({
        name: item.name ?? '',
        icaoCode: item.icaoCode ?? '',
        lat: geo[1],
        lon: geo[0],
        elevationM: item.elevation?.value ?? 0,
        type: item.type ?? 0,
        frequencies: freqs,
      });
    }

    airportCache = { data: items, timestamp: now, key };
    return items;
  } catch (err) {
    console.warn('[OpenAIP] Airports fetch error:', err);
    return airportCache?.data ?? [];
  }
}
