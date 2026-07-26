/**
 * @module geotiff-loader
 * @description Loads a GeoTIFF (.tif/.tiff) orthophoto and rasterizes it into a
 * data-URL PNG plus its geographic bounds, so it can be overlaid on the Leaflet
 * planner map as an `imageOverlay`. Only files whose geo bounding box can be
 * resolved to WGS84 lat/lon are placed: geographic (EPSG:4326) files are used
 * directly, Web Mercator (EPSG:3857 and equivalents) files are reprojected with
 * the closed-form spherical inverse. Any other projected CRS, or a
 * non-georeferenced file, returns `null` (no guessed placement).
 *
 * Large rasters are downsampled at read time to a maximum edge of
 * {@link MAX_RASTER_DIM} pixels so the browser does not choke building the
 * canvas; geotiff.js resamples during `readRasters` rather than after.
 * @license GPL-3.0-only
 */

import { fromArrayBuffer } from "geotiff";

/** `[[south, west], [north, east]]` in WGS84 degrees — a Leaflet bounds literal. */
export type RasterBounds = [[number, number], [number, number]];

/** Result of a successful load: georeferenced bounds + a rasterized PNG data URL. */
export interface LoadedRaster {
  bounds: RasterBounds;
  dataUrl: string;
  name?: string;
}

/**
 * The subset of GeoTIFF geo keys this loader reads to decide the CRS. Values are
 * numeric EPSG-style codes; any of them may be absent.
 */
export interface GeoKeyHints {
  /** 1 = projected, 2 = geographic, 3 = geocentric. */
  GTModelTypeGeoKey?: number;
  GeographicTypeGeoKey?: number;
  ProjectedCSTypeGeoKey?: number;
}

/**
 * Cap the longest rasterized edge. A 2048px edge keeps the largest overlay at
 * ~4.2M pixels (~17MB RGBA) which the browser handles comfortably; anything
 * larger is downsampled by geotiff.js at read time.
 */
export const MAX_RASTER_DIM = 2048;

const EARTH_RADIUS_M = 6378137;

/**
 * EPSG (and legacy/ESRI) codes that denote spherical Web Mercator. These share
 * the same forward/inverse spherical projection, so one inverse serves them all.
 */
const WEB_MERCATOR_CODES = new Set<number>([3857, 3785, 900913, 102100, 102113]);

/** WGS84 geographic (2D and 3D) codes whose bbox is already lon/lat degrees. */
const GEOGRAPHIC_CODES = new Set<number>([4326, 4979]);

/** Spherical Web Mercator inverse: meters east/north → [lon, lat] degrees. */
function mercatorToLonLat(x: number, y: number): [number, number] {
  const lon = (x / EARTH_RADIUS_M) * (180 / Math.PI);
  const lat = (2 * Math.atan(Math.exp(y / EARTH_RADIUS_M)) - Math.PI / 2) * (180 / Math.PI);
  return [lon, lat];
}

function isFiniteNumber(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n);
}

/** A bbox already expressed in lon/lat degrees lies fully inside the WGS84 range. */
function withinLonLatRange(minX: number, minY: number, maxX: number, maxY: number): boolean {
  return minX >= -180 && maxX <= 180 && minY >= -90 && maxY <= 90;
}

/**
 * Map a GeoTIFF bounding box `[minX, minY, maxX, maxY]` (in the file's CRS) to
 * Leaflet lat/lon bounds, using the geo keys to decide how to interpret it.
 *
 * Returns `null` when the box is malformed, when the CRS is a projected system
 * this loader cannot reproject (anything other than Web Mercator), or when the
 * resolved corners are not a valid non-degenerate WGS84 box. Never guesses.
 *
 * Exported for unit testing.
 */
export function bboxToLatLonBounds(
  bbox: readonly number[],
  geoKeys: GeoKeyHints | null | undefined,
): RasterBounds | null {
  if (!Array.isArray(bbox) || bbox.length < 4) return null;
  const [minX, minY, maxX, maxY] = bbox;
  if (![minX, minY, maxX, maxY].every(isFiniteNumber)) return null;

  const keys = geoKeys ?? {};
  const modelType = keys.GTModelTypeGeoKey;
  const geographicCode = keys.GeographicTypeGeoKey;
  const projectedCode = keys.ProjectedCSTypeGeoKey;

  let west: number;
  let south: number;
  let east: number;
  let north: number;

  if (projectedCode != null && WEB_MERCATOR_CODES.has(projectedCode)) {
    [west, south] = mercatorToLonLat(minX, minY);
    [east, north] = mercatorToLonLat(maxX, maxY);
  } else if (
    modelType === 2 ||
    (geographicCode != null && GEOGRAPHIC_CODES.has(geographicCode)) ||
    // No CRS hints at all, but the box already reads as lon/lat degrees: an
    // affine-transformed GeoTIFF with a degrees box is geographic.
    (modelType == null &&
      projectedCode == null &&
      withinLonLatRange(minX, minY, maxX, maxY))
  ) {
    west = minX;
    south = minY;
    east = maxX;
    north = maxY;
  } else {
    // A projected CRS we cannot reproject without a full transform library.
    return null;
  }

  if (![west, south, east, north].every(isFiniteNumber)) return null;
  if (south >= north || west >= east) return null;
  if (south < -90 || north > 90 || west < -180 || east > 180) return null;

  return [
    [south, west],
    [north, east],
  ];
}

/**
 * Rasterize a decoded GeoTIFF image to an RGBA PNG data URL, downsampling so the
 * longest edge is at most {@link MAX_RASTER_DIM}. Handles 1-band (grayscale),
 * 2-band (gray + alpha), 3-band (RGB) and 4-band (RGBA) images, and normalizes
 * samples wider than 8 bits to the 0-255 display range. Returns `null` when the
 * image is empty or a 2D canvas context is unavailable.
 */
async function rasterizeToDataUrl(
  image: Awaited<ReturnType<Awaited<ReturnType<typeof fromArrayBuffer>>["getImage"]>>,
): Promise<string | null> {
  const srcW = image.getWidth();
  const srcH = image.getHeight();
  if (!srcW || !srcH) return null;

  const scale = Math.min(1, MAX_RASTER_DIM / srcW, MAX_RASTER_DIM / srcH);
  const outW = Math.max(1, Math.round(srcW * scale));
  const outH = Math.max(1, Math.round(srcH * scale));

  const samples = image.getSamplesPerPixel();
  const raster = await image.readRasters({ interleave: true, width: outW, height: outH });

  // Normalize samples wider than 8 bits into the 0-255 display range. The max is
  // taken over the COLOUR bands only — an alpha band (present when there are 2 or 4
  // samples per pixel) is typically opaque (its full-scale value), and including it
  // would dominate the max and crush the real colour channels to near-black.
  const bits = image.getBitsPerSample();
  const hasAlpha = samples === 2 || samples === 4;
  const colourSamples = hasAlpha ? samples - 1 : samples;
  let norm = 1;
  if (bits > 8) {
    let max = 0;
    for (let i = 0; i < raster.length; i++) {
      if (i % samples >= colourSamples) continue; // skip the alpha band
      const v = raster[i];
      if (v > max) max = v;
    }
    norm = max > 0 ? 255 / max : 1;
  }

  const pixels = outW * outH;
  const rgba = new Uint8ClampedArray(pixels * 4);
  for (let p = 0; p < pixels; p++) {
    const s = p * samples;
    const o = p * 4;
    let r: number;
    let g: number;
    let b: number;
    let a = 255;
    if (samples >= 3) {
      r = raster[s] * norm;
      g = raster[s + 1] * norm;
      b = raster[s + 2] * norm;
      if (samples >= 4) a = raster[s + 3] * norm;
    } else {
      const gray = raster[s] * norm;
      r = gray;
      g = gray;
      b = gray;
      if (samples === 2) a = raster[s + 1] * norm;
    }
    rgba[o] = r;
    rgba[o + 1] = g;
    rgba[o + 2] = b;
    rgba[o + 3] = a;
  }

  const canvas = document.createElement("canvas");
  canvas.width = outW;
  canvas.height = outH;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.putImageData(new ImageData(rgba, outW, outH), 0, 0);
  return canvas.toDataURL("image/png");
}

/**
 * Load a GeoTIFF orthophoto from a raw file buffer and return its Leaflet
 * bounds + a rasterized PNG data URL, or `null` if the file is unreadable, has
 * no affine georeference, or is in a projected CRS this loader cannot place.
 */
export async function loadGeoTIFF(buffer: ArrayBuffer): Promise<LoadedRaster | null> {
  try {
    const tiff = await fromArrayBuffer(buffer);
    const image = await tiff.getImage();

    let bbox: number[];
    try {
      // Throws for a non-georeferenced image (no affine transformation).
      bbox = image.getBoundingBox();
    } catch {
      return null;
    }

    const geoKeys = image.getGeoKeys() as GeoKeyHints | null;
    const bounds = bboxToLatLonBounds(bbox, geoKeys);
    if (!bounds) return null;

    const dataUrl = await rasterizeToDataUrl(image);
    if (!dataUrl) return null;

    return { bounds, dataUrl };
  } catch (err) {
    console.error("Failed to load GeoTIFF:", err);
    return null;
  }
}
