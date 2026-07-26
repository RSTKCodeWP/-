/**
 * Slippy map tile coordinate math.
 *
 * Converts geographic coordinates to XYZ tile indices,
 * counts tiles in bounding boxes, and generates tile URLs
 * for bulk download.
 *
 * @module tile-math
 * @license GPL-3.0-only
 */

export interface LatLngBounds {
  north: number;
  south: number;
  east: number;
  west: number;
}

export interface TileProvider {
  url: string;
  subdomains: string[];
  maxZoom: number;
  avgTileKB: number;
}

export const TILE_PROVIDERS: Record<string, TileProvider> = {
  dark: {
    url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
    subdomains: ["a", "b", "c", "d"],
    maxZoom: 20,
    avgTileKB: 20,
  },
  osm: {
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    subdomains: ["a", "b", "c"],
    maxZoom: 19,
    avgTileKB: 25,
  },
  satellite: {
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    subdomains: [],
    maxZoom: 18,
    avgTileKB: 40,
  },
  terrain: {
    url: "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
    subdomains: ["a", "b", "c"],
    maxZoom: 17,
    avgTileKB: 20,
  },
};

/** Convert longitude to tile X index at zoom z. */
export function lonToTileX(lon: number, z: number): number {
  return Math.floor(((lon + 180) / 360) * Math.pow(2, z));
}

/** Convert latitude to tile Y index at zoom z. */
export function latToTileY(lat: number, z: number): number {
  const latRad = (lat * Math.PI) / 180;
  return Math.floor(
    ((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2) * Math.pow(2, z),
  );
}

/** Count tiles in a bounding box at a specific zoom level. */
export function tileCountAtZoom(bounds: LatLngBounds, z: number): number {
  const xMin = lonToTileX(bounds.west, z);
  const xMax = lonToTileX(bounds.east, z);
  const yMin = latToTileY(bounds.north, z);
  const yMax = latToTileY(bounds.south, z);
  return (xMax - xMin + 1) * (yMax - yMin + 1);
}

/** Count total tiles across a zoom range. */
export function totalTileCount(bounds: LatLngBounds, zMin: number, zMax: number): number {
  let total = 0;
  for (let z = zMin; z <= zMax; z++) {
    total += tileCountAtZoom(bounds, z);
  }
  return total;
}

/** Estimate total download size in bytes. */
export function estimateDownloadSize(
  bounds: LatLngBounds,
  zMin: number,
  zMax: number,
  avgTileKB: number,
): number {
  return totalTileCount(bounds, zMin, zMax) * avgTileKB * 1024;
}

/**
 * Detect a retina / HiDPI display. Mirrors Leaflet's `L.Browser.retina` so the
 * offline downloader stores the same `@2x` tile variant the on-screen layer
 * requests. Without this, on a HiDPI screen the write URL (no `@2x`) and the
 * read URL (`@2x`) never match and every cache lookup misses.
 */
export function isRetinaDisplay(): boolean {
  if (typeof window === "undefined") return false;
  return (window.devicePixelRatio || 1) > 1;
}

/**
 * Subdomain list for a known provider URL template, matching {@link TILE_PROVIDERS}.
 * Falls back to Leaflet's default `abc` scheme for an unrecognised template so the
 * read side stays compatible with any custom URL.
 */
export function subdomainsForUrl(urlTemplate: string): string[] {
  for (const provider of Object.values(TILE_PROVIDERS)) {
    if (provider.url === urlTemplate) return provider.subdomains;
  }
  return ["a", "b", "c"];
}

/**
 * Resolve a single tile URL from a template. This is the ONE place both the
 * offline downloader and the on-screen cached layer build a tile URL, so the
 * write key and the read key are byte-for-byte identical. The subdomain uses
 * the same `Math.abs(x + y) % len` scheme Leaflet uses internally, and `{r}`
 * resolves to `@2x` on HiDPI displays (only for templates that carry an `{r}`
 * slot, so non-retina providers are never affected).
 */
export function resolveTileUrl(
  urlTemplate: string,
  subdomains: string[],
  x: number,
  y: number,
  z: number,
  retina: boolean,
): string {
  const s = subdomains.length > 0
    ? subdomains[Math.abs(x + y) % subdomains.length]
    : "";
  return urlTemplate
    .replace("{s}", s)
    .replace("{z}", String(z))
    .replace("{x}", String(x))
    .replace("{y}", String(y))
    .replace("{r}", retina ? "@2x" : "");
}

/**
 * Generate all tile URLs for a bounding box and zoom range.
 * Yields URLs one at a time to avoid allocating a massive array.
 * URLs are built through {@link resolveTileUrl} so they match the on-screen
 * cached layer byte-for-byte, including the `@2x` retina variant and the
 * subdomain scheme.
 */
export function* generateTileUrls(
  bounds: LatLngBounds,
  zMin: number,
  zMax: number,
  provider: TileProvider,
  retina: boolean = isRetinaDisplay(),
): Generator<string> {
  for (let z = zMin; z <= zMax; z++) {
    const xMin = lonToTileX(bounds.west, z);
    const xMax = lonToTileX(bounds.east, z);
    const yMin = latToTileY(bounds.north, z);
    const yMax = latToTileY(bounds.south, z);

    for (let x = xMin; x <= xMax; x++) {
      for (let y = yMin; y <= yMax; y++) {
        yield resolveTileUrl(provider.url, provider.subdomains, x, y, z, retina);
      }
    }
  }
}

/** Format bytes as human-readable string. */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}
