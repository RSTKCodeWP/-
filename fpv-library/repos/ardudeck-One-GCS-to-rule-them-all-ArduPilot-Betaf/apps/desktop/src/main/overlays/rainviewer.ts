import type { RainViewerMeta } from '../../shared/overlay-types.js';

const API_URL = 'https://api.rainviewer.com/public/weather-maps.json';
const REFETCH_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes

let cachedMeta: RainViewerMeta | null = null;
let lastFetchTime = 0;

/**
 * Get the latest RainViewer radar tile path.
 * Caches the result for 5 minutes to avoid excessive API calls.
 */
export async function getRainViewerMeta(): Promise<RainViewerMeta | null> {
  const now = Date.now();

  if (cachedMeta && now - lastFetchTime < REFETCH_INTERVAL_MS) {
    return cachedMeta;
  }

  try {
    const response = await fetch(API_URL);
    if (!response.ok) return cachedMeta;

    const data = await response.json();
    const radarPast = data?.radar?.past;
    if (!Array.isArray(radarPast) || radarPast.length === 0) return cachedMeta;

    const latest = radarPast[radarPast.length - 1];
    cachedMeta = {
      path: latest.path,
      time: latest.time,
    };
    lastFetchTime = now;
    return cachedMeta;
  } catch {
    return cachedMeta; // Return stale cache on error
  }
}
