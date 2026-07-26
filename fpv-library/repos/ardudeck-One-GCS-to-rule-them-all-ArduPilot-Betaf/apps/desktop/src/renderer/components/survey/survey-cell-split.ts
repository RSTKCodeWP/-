/**
 * Cell-aware fleet split.
 *
 * When a survey was produced by a decomposing engine (TOPAS), its
 * `generatorResult.cells` are clean, non-overlapping regions with known track
 * workloads - far better split boundaries than the geometric bands the
 * generic fleet split cuts. This module partitions the cells into contiguous
 * runs of the engine's fly order, balanced by per-cell track length, and
 * slices the ALREADY-GENERATED plan waypoints along those runs - no
 * re-generation, no extra engine calls.
 *
 * Pure and dependency-light so it unit-tests in plain node.
 */

import type { LatLng } from './survey-types';

type LonLat = [number, number];

export interface SplitCell {
  cellId: number;
  /** Exterior ring, GeoJSON [lon, lat] order. */
  polygon: LonLat[];
  /** Track segments, each [start, end] in [lon, lat]. */
  tracks: Array<[LonLat, LonLat]>;
}

const MAX_CELLS = 512;

function isLonLat(p: unknown): p is LonLat {
  return (
    Array.isArray(p) &&
    p.length >= 2 &&
    typeof p[0] === 'number' &&
    typeof p[1] === 'number' &&
    Math.abs(p[0] as number) <= 180 &&
    Math.abs(p[1] as number) <= 90
  );
}

/**
 * Extract cells + fly order from an opaque generatorResult. Returns null when
 * the survey has no usable decomposition (fall back to the band split).
 * Runtime-validated - the blob comes from modules and mission files.
 */
export function extractSplitCells(
  generatorResult: unknown,
): { cells: SplitCell[]; cellOrder: number[] } | null {
  const gr = generatorResult as
    | { cells?: unknown; cellOrder?: unknown }
    | null
    | undefined;
  if (!gr || !Array.isArray(gr.cells) || gr.cells.length === 0) return null;
  if (gr.cells.length > MAX_CELLS) return null;

  const cells: SplitCell[] = [];
  for (const raw of gr.cells) {
    const c = raw as { cellId?: unknown; polygon?: unknown; tracks?: unknown };
    if (typeof c?.cellId !== 'number' || !Array.isArray(c.polygon) || c.polygon.length < 3) {
      return null;
    }
    if (!c.polygon.every(isLonLat)) return null;
    const tracks: Array<[LonLat, LonLat]> = [];
    if (Array.isArray(c.tracks)) {
      for (const t of c.tracks) {
        const seg = t as [unknown, unknown];
        if (Array.isArray(seg) && isLonLat(seg[0]) && isLonLat(seg[1])) {
          tracks.push([seg[0], seg[1]]);
        }
      }
    }
    cells.push({ cellId: c.cellId, polygon: c.polygon as LonLat[], tracks });
  }

  const ids = new Set(cells.map((c) => c.cellId));
  const cellOrder =
    Array.isArray(gr.cellOrder) &&
    gr.cellOrder.length === cells.length &&
    gr.cellOrder.every((id) => typeof id === 'number' && ids.has(id))
      ? (gr.cellOrder as number[])
      : cells.map((c) => c.cellId);

  return { cells, cellOrder };
}

function distM(a: LonLat, b: LonLat): number {
  const mLat = 110_540;
  const mLng = 111_320 * Math.cos(((a[1] + b[1]) / 2) * (Math.PI / 180));
  return Math.hypot((b[0] - a[0]) * mLng, (b[1] - a[1]) * mLat);
}

/** Per-cell workload: summed track length in meters (min 1 so empty cells count). */
export function cellWorkloads(cells: SplitCell[], cellOrder: number[]): number[] {
  const byId = new Map(cells.map((c) => [c.cellId, c]));
  return cellOrder.map((id) => {
    const cell = byId.get(id);
    if (!cell) return 1;
    const total = cell.tracks.reduce((s, [a, b]) => s + distM(a, b), 0);
    return Math.max(1, total);
  });
}

/**
 * Linear partition: split the weight sequence into up to k CONTIGUOUS runs
 * minimizing the largest run sum (classic DP). Contiguity in fly order keeps
 * every vehicle's share connected on the ground and preserves the engine's
 * routing inside each share. Returns index ranges [start, end) over the
 * sequence; fewer than k runs when there are fewer items.
 */
export function partitionContiguous(weights: number[], k: number): Array<[number, number]> {
  const n = weights.length;
  if (n === 0) return [];
  const parts = Math.min(k, n);
  if (parts <= 1) return [[0, n]];

  const prefix = [0];
  for (const w of weights) prefix.push(prefix[prefix.length - 1]! + w);
  const rangeSum = (i: number, j: number) => prefix[j]! - prefix[i]!;

  // dp[j][i] = minimal max-run-sum splitting the first i items into j runs.
  const dp: number[][] = Array.from({ length: parts + 1 }, () => new Array<number>(n + 1).fill(Infinity));
  const cut: number[][] = Array.from({ length: parts + 1 }, () => new Array<number>(n + 1).fill(0));
  for (let i = 1; i <= n; i++) dp[1]![i] = rangeSum(0, i);
  for (let j = 2; j <= parts; j++) {
    for (let i = j; i <= n; i++) {
      for (let x = j - 1; x < i; x++) {
        const candidate = Math.max(dp[j - 1]![x]!, rangeSum(x, i));
        if (candidate < dp[j]![i]!) {
          dp[j]![i] = candidate;
          cut[j]![i] = x;
        }
      }
    }
  }

  const ranges: Array<[number, number]> = [];
  let end = n;
  for (let j = parts; j >= 1; j--) {
    const start = j === 1 ? 0 : cut[j]![end]!;
    ranges.unshift([start, end]);
    end = start;
  }
  return ranges;
}

function pointInRing(lng: number, lat: number, ring: LonLat[]): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const a = ring[i]!;
    const b = ring[j]!;
    if (a[1] > lat !== b[1] > lat && lng < ((b[0] - a[0]) * (lat - a[1])) / (b[1] - a[1]) + a[0]) {
      inside = !inside;
    }
  }
  return inside;
}

/**
 * Assign each plan waypoint to a cell (index into cellOrder). Points inside a
 * cell polygon get that cell; transit points between cells inherit the NEXT
 * assigned cell so a vehicle's slice starts with its approach leg. Leading
 * unassigned points go to the first cell.
 */
export function assignWaypointsToRuns(
  waypoints: LatLng[],
  cells: SplitCell[],
  cellOrder: number[],
): number[] {
  const ordered = cellOrder.map((id) => cells.find((c) => c.cellId === id));
  const raw: number[] = waypoints.map((wp) => {
    for (let k = 0; k < ordered.length; k++) {
      const cell = ordered[k];
      if (cell && pointInRing(wp.lng, wp.lat, cell.polygon)) return k;
    }
    return -1;
  });
  // Backfill transits with the next cell's index, trailing ones with the last.
  let next = ordered.length - 1;
  for (let i = raw.length - 1; i >= 0; i--) {
    if (raw[i]! >= 0) next = raw[i]!;
    else raw[i] = next;
  }
  return raw;
}

/**
 * Slice the plan waypoints into one contiguous piece per partition range.
 * Waypoint order is preserved; a piece may be empty when its cells contributed
 * no waypoints (degenerate cells) - callers skip empty pieces.
 */
export function sliceWaypointsByRuns(
  waypoints: LatLng[],
  runIndexPerWaypoint: number[],
  ranges: Array<[number, number]>,
): LatLng[][] {
  return ranges.map(([start, end]) =>
    waypoints.filter((_, i) => {
      const r = runIndexPerWaypoint[i]!;
      return r >= start && r < end;
    }),
  );
}

/** Convex hull (lat/lng) of a cell group's vertices - display outline only. */
export function cellGroupHull(cells: SplitCell[], cellOrder: number[], range: [number, number]): LatLng[] {
  const pts: Array<{ x: number; y: number }> = [];
  for (let k = range[0]; k < range[1]; k++) {
    const cell = cells.find((c) => c.cellId === cellOrder[k]);
    if (cell) for (const p of cell.polygon) pts.push({ x: p[0], y: p[1] });
  }
  if (pts.length < 3) return pts.map((p) => ({ lat: p.y, lng: p.x }));
  pts.sort((a, b) => a.x - b.x || a.y - b.y);
  const cross = (o: typeof pts[0], a: typeof pts[0], b: typeof pts[0]) =>
    (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x);
  const lower: typeof pts = [];
  for (const p of pts) {
    while (lower.length >= 2 && cross(lower[lower.length - 2]!, lower[lower.length - 1]!, p) <= 0) lower.pop();
    lower.push(p);
  }
  const upper: typeof pts = [];
  for (let i = pts.length - 1; i >= 0; i--) {
    const p = pts[i]!;
    while (upper.length >= 2 && cross(upper[upper.length - 2]!, upper[upper.length - 1]!, p) <= 0) upper.pop();
    upper.push(p);
  }
  lower.pop();
  upper.pop();
  return [...lower, ...upper].map((p) => ({ lat: p.y, lng: p.x }));
}
