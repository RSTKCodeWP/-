/**
 * Weather API utility using Open-Meteo's free forecast service.
 * https://open-meteo.com/en/docs
 *
 * - Free, no API key required (same provider as the elevation client)
 * - Site-specific gridded forecast: wind at 10m, gusts, temperature, precip
 * - Daily sunrise/sunset for the daylight window
 *
 * Used by the flight briefing panel to show current conditions at the mission
 * site. Wind here is the meteorological convention: the direction the wind is
 * blowing FROM, in degrees.
 */

const OPEN_METEO_FORECAST_URL = 'https://api.open-meteo.com/v1/forecast';

// Conditions change slowly relative to planning; cache per rounded site for a
// few minutes so panning/recompute doesn't hammer the API.
const WEATHER_TTL_MS = 10 * 60 * 1000;

export interface WeatherSummary {
  windSpeedMs: number;
  windGustMs: number;
  windDirDeg: number;   // direction the wind comes FROM
  tempC: number;
  precipMm: number;
  sunriseIso: string | null;
  sunsetIso: string | null;
  /** "Now" in the SITE's timezone, so daylight-margin math stays correct. */
  currentTimeIso: string | null;
  fetchedAtMs: number;
}

const weatherCache = new Map<string, WeatherSummary>();

function cacheKey(lat: number, lon: number): string {
  // ~1km precision is plenty for a forecast; keeps the cache warm across edits.
  return `${lat.toFixed(2)},${lon.toFixed(2)}`;
}

/**
 * Fetch current conditions + today's daylight window for a site. Returns null
 * on any failure so callers can degrade gracefully (the briefing just omits
 * the weather card).
 */
export async function getCurrentWeather(lat: number, lon: number): Promise<WeatherSummary | null> {
  const key = cacheKey(lat, lon);
  const cached = weatherCache.get(key);
  if (cached && Date.now() - cached.fetchedAtMs < WEATHER_TTL_MS) {
    return cached;
  }

  const params = new URLSearchParams({
    latitude: lat.toFixed(4),
    longitude: lon.toFixed(4),
    current: 'temperature_2m,precipitation,wind_speed_10m,wind_direction_10m,wind_gusts_10m',
    daily: 'sunrise,sunset',
    wind_speed_unit: 'ms',
    timezone: 'auto',
    forecast_days: '1',
  });

  try {
    const response = await fetch(`${OPEN_METEO_FORECAST_URL}?${params.toString()}`);
    if (!response.ok) {
      console.warn('Weather API error:', response.status);
      return null;
    }
    const data = await response.json();
    const c = data?.current;
    if (!c) return null;

    const summary: WeatherSummary = {
      windSpeedMs: Number(c.wind_speed_10m ?? 0),
      windGustMs: Number(c.wind_gusts_10m ?? 0),
      windDirDeg: Number(c.wind_direction_10m ?? 0),
      tempC: Number(c.temperature_2m ?? 0),
      precipMm: Number(c.precipitation ?? 0),
      sunriseIso: data?.daily?.sunrise?.[0] ?? null,
      sunsetIso: data?.daily?.sunset?.[0] ?? null,
      currentTimeIso: c.time ?? null,
      fetchedAtMs: Date.now(),
    };
    weatherCache.set(key, summary);
    return summary;
  } catch (error) {
    console.warn('Failed to fetch weather:', error);
    return null;
  }
}

/** Compass abbreviation (N, NE, ...) for a bearing in degrees. */
export function compassPoint(deg: number): string {
  const points = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
  return points[Math.round(((deg % 360) / 45)) % 8]!;
}
