/**
 * Pure logic for the survey plan replay animation.
 *
 * A TOPAS-style generatorResult carries the planning pipeline's intermediate
 * artifacts (decomposition cells, visit order, per-cell tracks). The replay
 * overlay animates those stages on the map for demo / presentation:
 *
 *   decompose -> route -> tracks -> path -> fade -> done
 *
 * `parseReplayData` runtime-validates the opaque generatorResult (same
 * philosophy as survey/generator-overlays.ts: module output persisted in
 * mission files is untrusted - never throw on it). `computeReplayFrame` maps
 * elapsed ms to what is visible, so the animation is unit-testable without
 * React or Leaflet.
 */

export interface ReplayCell {
  /** Position in the original cells array; drives the stable per-cell hue. */
  index: number;
  polygon: Array<{ lat: number; lng: number }>;
  /** Straight coverage segments inside the cell. */
  tracks: Array<[{ lat: number; lng: number }, { lat: number; lng: number }]>;
  /** Polygon vertex average - good enough to anchor badges + route lines. */
  centroid: { lat: number; lng: number };
}

export interface ReplayData {
  cells: ReplayCell[];
  /** Visit order as indices into `cells` (resolved from cellId or index). */
  order: number[];
}

export type ReplayStage = 'decompose' | 'route' | 'tracks' | 'path' | 'fade' | 'done';

export interface ReplayFrame {
  stage: ReplayStage;
  /** Cells shown as filled polygons, counted in `cells` array order. */
  visibleCells: number;
  /** Numbered order badges shown, counted along `order`. */
  visibleBadges: number;
  /** Centroid-to-centroid route lines shown (badge k connects to k-1). */
  visibleConnections: number;
  /** Cells (along `order`) whose track segments are drawn. */
  visibleTrackCells: number;
  /** Revealed prefix of the group's mission waypoints, 0..1. */
  pathFraction: number;
  /** 1 while animating, ramps to 0 during the fade stage. */
  fadeOpacity: number;
  finished: boolean;
}

export const CELL_STEP_MS = 250;
export const ROUTE_STEP_MS = 300;
export const TRACK_STEP_MS = 200;
export const PATH_DURATION_MS = 4000;
export const FADE_DURATION_MS = 2000;

// A plan with hundreds of cells is a geometry dump, not a presentable replay;
// same spirit as the caps in survey/generator-overlays.ts. Order references
// resolve by position, so unlike overlays we reject rather than truncate.
const MAX_CELLS = 200;
const MAX_POLYGON_POINTS = 2000;
const MAX_TRACKS_PER_CELL = 2000;

/** Distinct per-cell hue, keyed by the cell's position in the cells array. */
export function cellColor(index: number): string {
  return `hsl(${(index * 47) % 360} 70% 55%)`;
}

function isFiniteNumber(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v);
}

/** Parse one GeoJSON-ordered [lon, lat] pair into map-ordered lat/lng. */
function parseLonLat(raw: unknown): { lat: number; lng: number } | null {
  if (!Array.isArray(raw) || raw.length < 2) return null;
  const lon = raw[0];
  const lat = raw[1];
  if (!isFiniteNumber(lon) || !isFiniteNumber(lat)) return null;
  if (Math.abs(lat) > 90 || Math.abs(lon) > 180) return null;
  return { lat, lng: lon };
}

function parseCell(raw: unknown, index: number): ReplayCell | null {
  const c = raw as { cellId?: unknown; polygon?: unknown; tracks?: unknown };
  if (!Array.isArray(c?.polygon) || c.polygon.length < 3 || c.polygon.length > MAX_POLYGON_POINTS) {
    return null;
  }
  const polygon: Array<{ lat: number; lng: number }> = [];
  for (const p of c.polygon) {
    const pt = parseLonLat(p);
    if (!pt) return null;
    polygon.push(pt);
  }

  // Tracks are cosmetic per-segment decorations; a bad segment is dropped
  // rather than sinking the whole cell.
  const tracks: ReplayCell['tracks'] = [];
  if (Array.isArray(c.tracks)) {
    for (const seg of c.tracks.slice(0, MAX_TRACKS_PER_CELL)) {
      if (!Array.isArray(seg) || seg.length < 2) continue;
      const a = parseLonLat(seg[0]);
      const b = parseLonLat(seg[1]);
      if (a && b) tracks.push([a, b]);
    }
  }

  let latSum = 0;
  let lngSum = 0;
  for (const p of polygon) {
    latSum += p.lat;
    lngSum += p.lng;
  }
  const centroid = { lat: latSum / polygon.length, lng: lngSum / polygon.length };

  return { index, polygon, tracks, centroid };
}

/**
 * Validate an opaque generatorResult into replayable data. Returns null when
 * the shape is unusable (missing cells, malformed coordinates, over caps, or
 * an order that resolves to nothing). Never throws.
 */
export function parseReplayData(generatorResult: unknown): ReplayData | null {
  const raw = generatorResult as { cellOrder?: unknown; cells?: unknown } | null | undefined;
  if (!raw || !Array.isArray(raw.cells) || !Array.isArray(raw.cellOrder)) return null;
  if (raw.cells.length === 0 || raw.cells.length > MAX_CELLS) return null;

  const cells: ReplayCell[] = [];
  const indexByCellId = new Map<number, number>();
  for (let i = 0; i < raw.cells.length; i++) {
    const cell = parseCell(raw.cells[i], i);
    if (!cell) return null;
    cells.push(cell);
    const id = (raw.cells[i] as { cellId?: unknown })?.cellId;
    if (isFiniteNumber(id) && !indexByCellId.has(id)) indexByCellId.set(id, i);
  }

  // Order entries are cellIds in the documented shape, but tolerate plain
  // indices too (both are "number[]" on the wire). Unresolvable or duplicate
  // entries are dropped.
  const order: number[] = [];
  const seen = new Set<number>();
  for (const entry of raw.cellOrder) {
    if (!isFiniteNumber(entry)) continue;
    const idx =
      indexByCellId.get(entry) ??
      (Number.isInteger(entry) && entry >= 0 && entry < cells.length ? entry : undefined);
    if (idx === undefined || seen.has(idx)) continue;
    seen.add(idx);
    order.push(idx);
  }
  if (order.length === 0) return null;

  return { cells, order };
}

/** Whether a group's generatorResult can drive the replay animation. */
export function hasReplayData(generatorResult: unknown): boolean {
  return parseReplayData(generatorResult) !== null;
}

interface StageBounds {
  decomposeEnd: number;
  routeEnd: number;
  tracksEnd: number;
  pathEnd: number;
  fadeEnd: number;
}

function stageBounds(data: ReplayData): StageBounds {
  const decomposeEnd = data.cells.length * CELL_STEP_MS;
  const routeEnd = decomposeEnd + data.order.length * ROUTE_STEP_MS;
  const tracksEnd = routeEnd + data.order.length * TRACK_STEP_MS;
  const pathEnd = tracksEnd + PATH_DURATION_MS;
  return { decomposeEnd, routeEnd, tracksEnd, pathEnd, fadeEnd: pathEnd + FADE_DURATION_MS };
}

/** Total runtime of the replay, including the end fade. */
export function replayTotalDurationMs(data: ReplayData): number {
  return stageBounds(data).fadeEnd;
}

/** Map elapsed time to what the overlay should draw. Stages are additive. */
export function computeReplayFrame(elapsedMs: number, data: ReplayData): ReplayFrame {
  const t = Math.max(0, elapsedMs);
  const b = stageBounds(data);
  const nCells = data.cells.length;
  const nOrder = data.order.length;

  const visibleCells = Math.min(nCells, Math.floor(t / CELL_STEP_MS));
  const visibleBadges =
    t < b.decomposeEnd
      ? 0
      : Math.min(nOrder, Math.floor((t - b.decomposeEnd) / ROUTE_STEP_MS) + 1);
  const visibleTrackCells =
    t < b.routeEnd ? 0 : Math.min(nOrder, Math.floor((t - b.routeEnd) / TRACK_STEP_MS) + 1);
  const pathFraction =
    t < b.tracksEnd ? 0 : Math.min(1, (t - b.tracksEnd) / PATH_DURATION_MS);

  const stage: ReplayStage =
    t >= b.fadeEnd
      ? 'done'
      : t >= b.pathEnd
        ? 'fade'
        : t >= b.tracksEnd
          ? 'path'
          : t >= b.routeEnd
            ? 'tracks'
            : t >= b.decomposeEnd
              ? 'route'
              : 'decompose';

  const fadeOpacity =
    stage === 'done' ? 0 : stage === 'fade' ? 1 - (t - b.pathEnd) / FADE_DURATION_MS : 1;

  return {
    stage,
    visibleCells,
    visibleBadges,
    visibleConnections: Math.max(0, visibleBadges - 1),
    visibleTrackCells,
    pathFraction,
    fadeOpacity,
    finished: stage === 'done',
  };
}
