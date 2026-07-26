/**
 * Live survey execution progress.
 *
 * Pure helpers that turn (group waypoints, MISSION_CURRENT seq, vehicle
 * position) into render-ready progress: completed fraction, the flown path
 * prefix for map tinting, ETA, and - when the group's generatorResult carries
 * TOPAS-style cells - a per-cell completion state.
 *
 * `currentSeq` follows the mission-store convention: it is already translated
 * through fcSeqOffset, so it compares directly against missionItems[].seq
 * (the waypoint with seq === currentSeq is the one being flown TO; everything
 * with a lower seq is done).
 */
import type { LatLng } from './survey-types';
import { distanceLatLng, latLngToLocal } from './geo-math';
import { pointInRing } from './geo-edit';

export interface ProgressWaypoint {
  seq: number;
  lat: number;
  lng: number;
}

export interface GroupProgress {
  /** At least one waypoint of the group has been passed. */
  started: boolean;
  /** Every waypoint of the group has been passed. */
  finished: boolean;
  /** 0..1 of the group's path length flown (includes the partial live leg). */
  completedFraction: number;
  /**
   * The flown portion of the group path: passed waypoints plus, on the live
   * leg, the vehicle position projected onto the segment toward the current
   * target. Ready to feed a Polyline.
   */
  completedPath: LatLng[];
  remainingMeters: number;
  /** Seconds to finish the group at the given groundspeed; null when unknown. */
  etaSeconds: number | null;
}

const EMPTY_PROGRESS: GroupProgress = {
  started: false,
  finished: false,
  completedFraction: 0,
  completedPath: [],
  remainingMeters: 0,
  etaSeconds: null,
};

// Below this the vehicle is effectively hovering and any ETA would be noise.
const MIN_ETA_SPEED_MPS = 0.3;

export function computeGroupProgress(
  items: ProgressWaypoint[],
  currentSeq: number | null,
  vehiclePos: LatLng | null,
  groundspeedMps = 0,
): GroupProgress {
  if (items.length === 0 || currentSeq === null) return EMPTY_PROGRESS;

  const ordered = [...items].sort((a, b) => a.seq - b.seq);
  const doneCount = ordered.reduce((n, it) => (it.seq < currentSeq ? n + 1 : n), 0);
  const finished = doneCount === ordered.length;

  const legs: number[] = [];
  let totalMeters = 0;
  for (let i = 0; i < ordered.length - 1; i++) {
    const a = ordered[i]!;
    const b = ordered[i + 1]!;
    const d = distanceLatLng({ lat: a.lat, lng: a.lng }, { lat: b.lat, lng: b.lng });
    legs.push(d);
    totalMeters += d;
  }

  let completedMeters = 0;
  for (let i = 0; i < doneCount - 1; i++) completedMeters += legs[i]!;

  const completedPath: LatLng[] = ordered
    .slice(0, doneCount)
    .map((it) => ({ lat: it.lat, lng: it.lng }));

  // Live leg: project the vehicle onto the segment from the last passed
  // waypoint toward the current target so the tint follows the vehicle
  // instead of jumping a whole leg at a time.
  if (!finished && doneCount > 0 && vehiclePos) {
    const from = ordered[doneCount - 1]!;
    const to = ordered[doneCount]!;
    const legLen = legs[doneCount - 1] ?? 0;
    if (legLen > 0) {
      const origin = { lat: from.lat, lng: from.lng };
      const seg = latLngToLocal(origin, { lat: to.lat, lng: to.lng });
      const veh = latLngToLocal(origin, vehiclePos);
      const segLenSq = seg.x * seg.x + seg.y * seg.y;
      const t = segLenSq > 0
        ? Math.min(1, Math.max(0, (veh.x * seg.x + veh.y * seg.y) / segLenSq))
        : 0;
      if (t > 0) {
        completedMeters += t * legLen;
        completedPath.push({
          lat: from.lat + (to.lat - from.lat) * t,
          lng: from.lng + (to.lng - from.lng) * t,
        });
      }
    }
  }

  const completedFraction = finished
    ? 1
    : totalMeters > 0
      ? Math.min(1, Math.max(0, completedMeters / totalMeters))
      : 0;
  const remainingMeters = Math.max(0, totalMeters - completedMeters);
  const etaSeconds =
    !finished && doneCount > 0 && groundspeedMps >= MIN_ETA_SPEED_MPS
      ? remainingMeters / groundspeedMps
      : null;

  return {
    started: doneCount > 0,
    finished,
    completedFraction,
    completedPath,
    remainingMeters,
    etaSeconds,
  };
}

// ---------------------------------------------------------------------------
// TOPAS-style cells from generatorResult
// ---------------------------------------------------------------------------

export interface ProgressCell {
  cellId: string;
  /** Cell boundary in LatLng order (converted from the GeoJSON lon-lat input). */
  polygon: LatLng[];
}

export type CellState = 'untouched' | 'inProgress' | 'completed';

export interface CellProgress {
  cell: ProgressCell;
  state: CellState;
}

// generatorResult is opaque module output persisted in mission files - cap
// sizes and validate every value so a malformed or hostile blob is dropped,
// never thrown on (same stance as generator-overlays.ts).
const MAX_CELLS = 500;
const MAX_CELL_POINTS = 2000;

function isFiniteNumber(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v);
}

function parseCellPolygon(raw: unknown): LatLng[] | null {
  if (!Array.isArray(raw) || raw.length < 3 || raw.length > MAX_CELL_POINTS) return null;
  const points: LatLng[] = [];
  for (const p of raw) {
    // GeoJSON pair order: [lon, lat]
    if (!Array.isArray(p) || p.length < 2) return null;
    const lng = p[0];
    const lat = p[1];
    if (!isFiniteNumber(lat) || !isFiniteNumber(lng)) return null;
    if (Math.abs(lat) > 90 || Math.abs(lng) > 180) return null;
    points.push({ lat, lng });
  }
  return points;
}

/**
 * Extract renderable cells from an opaque generatorResult, in flight order
 * when a valid `cellOrder` index list is present. Never throws; returns []
 * when the blob has no usable cells.
 */
export function extractProgressCells(generatorResult: unknown): ProgressCell[] {
  const raw = (generatorResult as { cells?: unknown; cellOrder?: unknown } | null | undefined);
  if (!raw || !Array.isArray(raw.cells)) return [];

  const cells: Array<ProgressCell | null> = raw.cells.slice(0, MAX_CELLS).map((entry) => {
    const c = entry as { cellId?: unknown; polygon?: unknown };
    const polygon = parseCellPolygon(c?.polygon);
    if (!polygon) return null;
    const cellId =
      typeof c.cellId === 'string' || typeof c.cellId === 'number' ? String(c.cellId) : null;
    if (cellId === null) return null;
    return { cellId, polygon };
  });

  const valid = cells.filter((c): c is ProgressCell => c !== null);

  // cellOrder indexes into the original cells array. Only trust it when it is
  // a clean permutation-ish list of in-range indices; otherwise keep array order.
  const order = raw.cellOrder;
  if (
    Array.isArray(order) &&
    order.length === cells.length &&
    order.every((i) => isFiniteNumber(i) && Number.isInteger(i) && i >= 0 && i < cells.length) &&
    new Set(order).size === order.length
  ) {
    const reordered: ProgressCell[] = [];
    for (const i of order as number[]) {
      const c = cells[i];
      if (c) reordered.push(c);
    }
    return reordered;
  }
  return valid;
}

/**
 * Classify each cell by how much of the group's mission has passed through it:
 * completed = every group waypoint inside the cell has been passed,
 * inProgress = some passed (or the live target sits inside), else untouched.
 * Cells containing no waypoints stay untouched.
 */
export function computeCellStates(
  cells: ProgressCell[],
  items: ProgressWaypoint[],
  currentSeq: number | null,
): CellProgress[] {
  return cells.map((cell) => {
    let inside = 0;
    let done = 0;
    let containsTarget = false;
    for (const it of items) {
      if (!pointInRing({ lat: it.lat, lng: it.lng }, cell.polygon)) continue;
      inside++;
      if (currentSeq !== null && it.seq < currentSeq) done++;
      if (currentSeq !== null && it.seq === currentSeq) containsTarget = true;
    }
    let state: CellState = 'untouched';
    if (inside > 0 && done === inside) state = 'completed';
    else if (done > 0 || containsTarget) state = 'inProgress';
    return { cell, state };
  });
}

/** Compact "cell 4/10" style summary. Null when there are no cells. */
export function summarizeCells(
  cellStates: CellProgress[],
): { done: number; total: number; activeNumber: number } | null {
  if (cellStates.length === 0) return null;
  const done = cellStates.filter((c) => c.state === 'completed').length;
  const activeIdx = cellStates.findIndex((c) => c.state === 'inProgress');
  return {
    done,
    total: cellStates.length,
    activeNumber: activeIdx >= 0 ? activeIdx + 1 : done,
  };
}
