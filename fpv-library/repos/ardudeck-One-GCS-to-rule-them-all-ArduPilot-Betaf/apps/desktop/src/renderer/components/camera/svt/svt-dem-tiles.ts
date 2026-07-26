/**
 * Tile-based DEM source for synthetic vision.
 *
 * Stitches the Terrarium-encoded elevation tiles the app already serves
 * (tile-cache://dem/{z}/{x}/{y}.png — cached in the main process) into one
 * in-memory heightfield. A handful of tiles cover tens of kilometres, so the
 * synthetic patch can be large and dense without the per-point DEM API's many
 * round-trips — and with no haze "wall" needed to hide a small patch edge.
 */

import { decodeTerrarium } from '../../../utils/terrain-colors';

const TILE_URL = 'tile-cache://dem/{z}/{x}/{y}.png';
const TILE_SIZE = 256;
/** Abandon a tile that hasn't loaded in this long (treat as missing). */
const TILE_TIMEOUT_MS = 12_000;
/**
 * Cap concurrent tile image loads across the whole renderer. With a swarm, many
 * synthetic-vision views load terrain at once; without a cap they starve the
 * connection pool and some Image loads never fire onload/onerror — which would
 * otherwise hang the whole terrain load forever.
 */
const MAX_CONCURRENT_TILES = 8;
let activeTileLoads = 0;
const tileQueue: Array<() => void> = [];

function acquireTileSlot(): Promise<void> {
  if (activeTileLoads < MAX_CONCURRENT_TILES) {
    activeTileLoads++;
    return Promise.resolve();
  }
  return new Promise<void>((resolve) => tileQueue.push(() => resolve())).then(() => {
    activeTileLoads++;
  });
}

function releaseTileSlot(): void {
  activeTileLoads--;
  const next = tileQueue.shift();
  if (next) next();
}

export interface Heightfield {
  zoom: number;
  /** Tile index of the top-left (NW) tile. */
  originTileX: number;
  originTileY: number;
  width: number;
  height: number;
  /** Elevation (m MSL) per pixel, row-major (width × height). */
  elev: Float32Array;
  /** How many tiles actually loaded (0 ⇒ offline / nothing cached). */
  loadedTiles: number;
}

/** Web-Mercator fractional tile X for a longitude. */
export function lonToTileX(lon: number, z: number): number {
  return ((lon + 180) / 360) * 2 ** z;
}

/** Web-Mercator fractional tile Y for a latitude. */
export function latToTileY(lat: number, z: number): number {
  const r = (lat * Math.PI) / 180;
  return ((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) * 2 ** z;
}

/**
 * Pick a zoom so the patch spans roughly three tiles per side — enough tiles to
 * be detailed, few enough to load quickly.
 */
export function pickZoom(halfSizeM: number, lat: number): number {
  const spanM = 2 * halfSizeM;
  const earthAtLat = 40_075_017 * Math.cos((lat * Math.PI) / 180);
  const z = Math.round(Math.log2((earthAtLat * 3) / Math.max(1, spanM)));
  return Math.max(8, Math.min(12, z));
}

async function loadTilePixels(z: number, x: number, y: number): Promise<Uint8ClampedArray | null> {
  await acquireTileSlot();
  return new Promise<Uint8ClampedArray | null>((resolve) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    let settled = false;
    const finish = (value: Uint8ClampedArray | null) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      img.onload = null;
      img.onerror = null;
      releaseTileSlot();
      resolve(value);
    };
    // A stalled custom-protocol request can fire neither onload nor onerror;
    // the timeout guarantees the promise (and the whole load) always settles.
    const timer = setTimeout(() => finish(null), TILE_TIMEOUT_MS);
    img.onload = () => {
      const c = document.createElement('canvas');
      c.width = TILE_SIZE;
      c.height = TILE_SIZE;
      const ctx = c.getContext('2d');
      if (!ctx) return finish(null);
      ctx.drawImage(img, 0, 0, TILE_SIZE, TILE_SIZE);
      try {
        finish(ctx.getImageData(0, 0, TILE_SIZE, TILE_SIZE).data);
      } catch {
        finish(null);
      }
    };
    img.onerror = () => finish(null);
    img.src = TILE_URL.replace('{z}', String(z)).replace('{x}', String(x)).replace('{y}', String(y));
  });
}

/** Load + stitch the DEM tiles covering a lat/lon bounding box. */
export async function loadHeightfield(
  minLat: number,
  minLon: number,
  maxLat: number,
  maxLon: number,
  zoom: number,
): Promise<Heightfield> {
  const n = 2 ** zoom;
  const clampTile = (v: number) => Math.max(0, Math.min(n - 1, v));
  const x0 = clampTile(Math.floor(lonToTileX(minLon, zoom)));
  const x1 = clampTile(Math.floor(lonToTileX(maxLon, zoom)));
  // Tile Y grows southward, so the northern (max) latitude maps to the smaller y.
  const y0 = clampTile(Math.floor(latToTileY(maxLat, zoom)));
  const y1 = clampTile(Math.floor(latToTileY(minLat, zoom)));

  const tilesX = x1 - x0 + 1;
  const tilesY = y1 - y0 + 1;
  const width = tilesX * TILE_SIZE;
  const height = tilesY * TILE_SIZE;
  const elev = new Float32Array(width * height);
  let loadedTiles = 0;

  await Promise.all(
    Array.from({ length: tilesX * tilesY }, (_unused, idx) => {
      const cx = idx % tilesX;
      const cy = Math.floor(idx / tilesX);
      return loadTilePixels(zoom, x0 + cx, y0 + cy).then((data) => {
        if (!data) return;
        loadedTiles++;
        for (let py = 0; py < TILE_SIZE; py++) {
          const dstRow = (cy * TILE_SIZE + py) * width + cx * TILE_SIZE;
          const srcRow = py * TILE_SIZE * 4;
          for (let px = 0; px < TILE_SIZE; px++) {
            const s = srcRow + px * 4;
            elev[dstRow + px] = decodeTerrarium(data[s]!, data[s + 1]!, data[s + 2]!);
          }
        }
      });
    }),
  );

  return { zoom, originTileX: x0, originTileY: y0, width, height, elev, loadedTiles };
}

/** Bilinearly sample elevation (m MSL) at a lat/lon, clamped to the field edges. */
export function sampleHeightfield(hf: Heightfield, lat: number, lon: number): number {
  const gx = lonToTileX(lon, hf.zoom) * TILE_SIZE - hf.originTileX * TILE_SIZE;
  const gy = latToTileY(lat, hf.zoom) * TILE_SIZE - hf.originTileY * TILE_SIZE;
  const x = Math.min(hf.width - 1, Math.max(0, gx));
  const y = Math.min(hf.height - 1, Math.max(0, gy));
  const x0 = Math.floor(x);
  const y0 = Math.floor(y);
  const x1 = Math.min(hf.width - 1, x0 + 1);
  const y1 = Math.min(hf.height - 1, y0 + 1);
  const tx = x - x0;
  const ty = y - y0;
  const e00 = hf.elev[y0 * hf.width + x0]!;
  const e10 = hf.elev[y0 * hf.width + x1]!;
  const e01 = hf.elev[y1 * hf.width + x0]!;
  const e11 = hf.elev[y1 * hf.width + x1]!;
  const e0 = e00 + (e10 - e00) * tx;
  const e1 = e01 + (e11 - e01) * tx;
  return e0 + (e1 - e0) * ty;
}
