/**
 * The region contract.
 *
 * `RegionSource` is the seam the acquisition strategy plugs into. Phase 1 ships exactly one
 * implementation, `LocalRegionSource`, which scans the baked-region directories already on
 * disk. A server-baked pack source or a client-side bake source is a second implementation
 * of this interface, not a change to the UI: the UI only ever sees `RegionSummary` and
 * `prepare()`.
 *
 * `prepare()` exists specifically so a future source can do work (download, bake) with
 * progress while the local source resolves immediately. Nothing in Phase 1 may assume it
 * is instant.
 */

/** Where a region is, from the player's point of view. */
export type RegionAvailability =
  /** Baked and on disk, ready to fly now. */
  | 'local'
  /** Known to exist but not on this machine. No Phase 1 source produces this. */
  | 'remote'
  /** Being acquired or baked right now. No Phase 1 source produces this. */
  | 'preparing';

export interface RegionImagery {
  source: string | null;
  /** ISO date of the source scene, for example "2025-06-29". */
  date: string | null;
  /** Fraction 0..1, as the bake records it. */
  cloudCover: number | null;
  /** Metres per pixel of the source imagery. */
  resM: number | null;
}

export interface RegionSummary {
  /** Directory name, and the id every other call keys on. */
  name: string;
  displayName: string;
  availability: RegionAvailability;
  /** Absolute path to the baked directory. Null when the region is not local yet. */
  assetPath: string | null;
  home: { lat: number; lon: number } | null;
  elevationM: { min: number; max: number } | null;
  /** Ground coverage in metres, derived from the UTM box. */
  extentM: { width: number; height: number } | null;
  sizeTexels: { w: number; h: number } | null;
  metersPerTexel: number | null;
  /** Bytes on disk for the whole directory. Null when not local. */
  sizeBytes: number | null;
  imagery: RegionImagery;
  /** Attribution strings the bake recorded, deduplicated. */
  attribution: string[];
  utmEpsg: number | null;
  /**
   * What this region could not tell us. Shown in the UI rather than swallowed, because a
   * region missing home_wgs84 flies with the wrong GPS and the wrong solar latitude, and
   * that is invisible until someone looks at the map.
   */
  warnings: string[];
}

export interface RegionPrepareProgress {
  /** 0..1, or null when the work has no measurable total. */
  fraction: number | null;
  message: string;
}

export interface PreparedRegion {
  name: string;
  assetPath: string;
  home: { lat: number; lon: number } | null;
  warnings: string[];
}

export interface RegionSource {
  /** Stable id, so a config or a bug report says which source produced a region. */
  readonly id: string;
  readonly label: string;
  list(): Promise<RegionSummary[]>;
  /**
   * Make a region flyable and return where it landed. The local source only verifies; a
   * downloading or baking source does the real work here and reports progress.
   */
  prepare(name: string, onProgress?: (p: RegionPrepareProgress) => void): Promise<PreparedRegion>;
}

// ---------------------------------------------------------------------------
// Manifest reading, kept pure so it is testable without a filesystem.
// ---------------------------------------------------------------------------

export interface ParsedManifest {
  home: { lat: number; lon: number } | null;
  elevationM: { min: number; max: number } | null;
  extentM: { width: number; height: number } | null;
  sizeTexels: { w: number; h: number } | null;
  metersPerTexel: number | null;
  imagery: RegionImagery;
  attribution: string[];
  utmEpsg: number | null;
  warnings: string[];
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

function num(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

/**
 * Read a baked region's manifest.json. Every field is optional on the way out: regions
 * baked before a field existed are still listed and still flyable, they just show less.
 * Anything absent is reported through `warnings` instead of failing the region.
 */
export function parseRegionManifest(raw: unknown): ParsedManifest {
  const warnings: string[] = [];
  const empty: ParsedManifest = {
    home: null,
    elevationM: null,
    extentM: null,
    sizeTexels: null,
    metersPerTexel: null,
    imagery: { source: null, date: null, cloudCover: null, resM: null },
    attribution: [],
    utmEpsg: null,
    warnings,
  };
  if (!isRecord(raw)) {
    warnings.push('manifest.json is not a JSON object');
    return empty;
  }

  const homeRaw = isRecord(raw.home_wgs84) ? raw.home_wgs84 : null;
  const lat = homeRaw ? num(homeRaw.lat) : null;
  const lon = homeRaw ? num(homeRaw.lon) : null;
  const home = lat !== null && lon !== null ? { lat, lon } : null;
  if (!home) {
    warnings.push('no home_wgs84, re-bake this region or SITL reports the wrong position');
  }

  const elevRaw = isRecord(raw.elevation_m) ? raw.elevation_m : null;
  const eMin = elevRaw ? num(elevRaw.min) : null;
  const eMax = elevRaw ? num(elevRaw.max) : null;
  const elevationM = eMin !== null && eMax !== null ? { min: eMin, max: eMax } : null;
  if (!elevationM) warnings.push('no elevation_m range');

  const boxRaw = isRecord(raw.box_utm) ? raw.box_utm : null;
  const minX = boxRaw ? num(boxRaw.min_x) : null;
  const maxX = boxRaw ? num(boxRaw.max_x) : null;
  const minY = boxRaw ? num(boxRaw.min_y) : null;
  const maxY = boxRaw ? num(boxRaw.max_y) : null;
  const extentM =
    minX !== null && maxX !== null && minY !== null && maxY !== null
      ? { width: Math.abs(maxX - minX), height: Math.abs(maxY - minY) }
      : null;
  if (!extentM) warnings.push('no box_utm, size on the ground is unknown');

  const sizeRaw = isRecord(raw.size_texels) ? raw.size_texels : null;
  const w = sizeRaw ? num(sizeRaw.w) : null;
  const h = sizeRaw ? num(sizeRaw.h) : null;
  const sizeTexels = w !== null && h !== null ? { w, h } : null;

  const aerialRaw = isRecord(raw.aerial) ? raw.aerial : null;
  const imagery: RegionImagery = {
    source: aerialRaw && typeof aerialRaw.source === 'string' ? aerialRaw.source : null,
    date: aerialRaw && typeof aerialRaw.date === 'string' ? aerialRaw.date : null,
    cloudCover: aerialRaw ? num(aerialRaw.cloud_cover) : null,
    resM: aerialRaw ? num(aerialRaw.res_m) : null,
  };
  if (!imagery.date) warnings.push('no imagery date');

  const attribution: string[] = [];
  for (const key of ['aerial', 'canopy', 'built_height']) {
    const block = raw[key];
    if (isRecord(block) && typeof block.attribution === 'string') {
      attribution.push(block.attribution);
    }
  }

  return {
    home,
    elevationM,
    extentM,
    sizeTexels,
    metersPerTexel: num(raw.meters_per_texel),
    imagery,
    attribution: [...new Set(attribution)],
    utmEpsg: num(raw.utm_epsg),
    warnings,
  };
}

/** "sutomore" reads as a folder name; "Sutomore" reads as a place. */
export function regionDisplayName(name: string): string {
  return name
    .split(/[-_]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}
