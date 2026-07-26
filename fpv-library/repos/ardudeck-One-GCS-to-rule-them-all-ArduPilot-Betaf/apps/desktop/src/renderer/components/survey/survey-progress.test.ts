import { describe, it, expect } from 'vitest';
import {
  computeGroupProgress,
  extractProgressCells,
  computeCellStates,
  summarizeCells,
  type ProgressWaypoint,
} from './survey-progress';

// A straight west-to-east lawnmower leg near the equator: 4 waypoints spaced
// ~111m apart in longitude, so leg lengths are equal and fractions are easy
// to reason about.
const ITEMS: ProgressWaypoint[] = [
  { seq: 10, lat: 0, lng: 0 },
  { seq: 11, lat: 0, lng: 0.001 },
  { seq: 12, lat: 0, lng: 0.002 },
  { seq: 13, lat: 0, lng: 0.003 },
];

describe('computeGroupProgress', () => {
  it('is empty for no items or unknown currentSeq', () => {
    expect(computeGroupProgress([], 5, null).started).toBe(false);
    const p = computeGroupProgress(ITEMS, null, null);
    expect(p.started).toBe(false);
    expect(p.completedFraction).toBe(0);
    expect(p.completedPath).toEqual([]);
  });

  it('has not started while flying to the first waypoint', () => {
    const p = computeGroupProgress(ITEMS, 10, { lat: 0, lng: -0.001 });
    expect(p.started).toBe(false);
    expect(p.finished).toBe(false);
    expect(p.completedFraction).toBe(0);
  });

  it('counts passed waypoints and stops the prefix there without a position', () => {
    const p = computeGroupProgress(ITEMS, 12, null);
    expect(p.started).toBe(true);
    expect(p.finished).toBe(false);
    // Wp 10 and 11 passed = one of three equal legs fully flown.
    expect(p.completedFraction).toBeCloseTo(1 / 3, 5);
    expect(p.completedPath).toEqual([
      { lat: 0, lng: 0 },
      { lat: 0, lng: 0.001 },
    ]);
  });

  it('interpolates the live leg from the vehicle position', () => {
    // Vehicle halfway between wp 11 and wp 12.
    const p = computeGroupProgress(ITEMS, 12, { lat: 0, lng: 0.0015 });
    expect(p.completedFraction).toBeCloseTo(0.5, 3);
    const tip = p.completedPath[p.completedPath.length - 1]!;
    expect(tip.lng).toBeCloseTo(0.0015, 6);
    expect(tip.lat).toBeCloseTo(0, 6);
  });

  it('clamps the projection to the current leg', () => {
    // Vehicle wildly past the target: tip must not overshoot wp 12.
    const p = computeGroupProgress(ITEMS, 12, { lat: 0, lng: 0.01 });
    const tip = p.completedPath[p.completedPath.length - 1]!;
    expect(tip.lng).toBeCloseTo(0.002, 6);
    expect(p.completedFraction).toBeCloseTo(2 / 3, 3);

    // Vehicle behind the previous waypoint: no tip is added (t clamps to 0).
    const back = computeGroupProgress(ITEMS, 12, { lat: 0, lng: 0.0005 });
    expect(back.completedFraction).toBeCloseTo(1 / 3, 3);
    expect(back.completedPath).toHaveLength(2);
  });

  it('is finished once currentSeq passes the last waypoint', () => {
    const p = computeGroupProgress(ITEMS, 14, { lat: 0, lng: 0.003 });
    expect(p.finished).toBe(true);
    expect(p.completedFraction).toBe(1);
    expect(p.completedPath).toHaveLength(4);
    expect(p.remainingMeters).toBe(0);
    expect(p.etaSeconds).toBeNull();
  });

  it('derives ETA from groundspeed and hides it when hovering', () => {
    const p = computeGroupProgress(ITEMS, 12, { lat: 0, lng: 0.0015 }, 5);
    // ~166.5m remaining at 5 m/s.
    expect(p.etaSeconds).not.toBeNull();
    expect(p.etaSeconds!).toBeCloseTo(p.remainingMeters / 5, 6);
    expect(computeGroupProgress(ITEMS, 12, null, 0.1).etaSeconds).toBeNull();
    // Not started yet: no ETA either.
    expect(computeGroupProgress(ITEMS, 10, null, 5).etaSeconds).toBeNull();
  });

  it('tolerates unsorted input', () => {
    const shuffled = [ITEMS[2]!, ITEMS[0]!, ITEMS[3]!, ITEMS[1]!];
    const p = computeGroupProgress(shuffled, 12, null);
    expect(p.completedFraction).toBeCloseTo(1 / 3, 5);
  });
});

// Cells in GeoJSON [lon, lat] pair order, as a TOPAS-style generatorResult.
const CELLS_RESULT = {
  cells: [
    // Covers wp seq 10-11
    { cellId: 'A', polygon: [[-0.0005, -0.001], [0.0015, -0.001], [0.0015, 0.001], [-0.0005, 0.001]], tracks: [] },
    // Covers wp seq 12-13
    { cellId: 7, polygon: [[0.0015, -0.001], [0.0035, -0.001], [0.0035, 0.001], [0.0015, 0.001]], tracks: [] },
    // Contains no waypoints
    { cellId: 'empty', polygon: [[1, 1], [1.001, 1], [1.001, 1.001], [1, 1.001]] },
  ],
  cellOrder: [0, 1, 2],
};

describe('extractProgressCells', () => {
  it('parses cells and converts lon-lat pairs to LatLng', () => {
    const cells = extractProgressCells(CELLS_RESULT);
    expect(cells).toHaveLength(3);
    expect(cells[0]!.cellId).toBe('A');
    expect(cells[1]!.cellId).toBe('7');
    expect(cells[0]!.polygon[0]).toEqual({ lat: -0.001, lng: -0.0005 });
  });

  it('applies a valid cellOrder', () => {
    const cells = extractProgressCells({ ...CELLS_RESULT, cellOrder: [2, 0, 1] });
    expect(cells.map((c) => c.cellId)).toEqual(['empty', 'A', '7']);
  });

  it('ignores an invalid cellOrder', () => {
    const dup = extractProgressCells({ ...CELLS_RESULT, cellOrder: [0, 0, 1] });
    expect(dup.map((c) => c.cellId)).toEqual(['A', '7', 'empty']);
    const oob = extractProgressCells({ ...CELLS_RESULT, cellOrder: [0, 1, 9] });
    expect(oob.map((c) => c.cellId)).toEqual(['A', '7', 'empty']);
  });

  it('drops malformed input without throwing', () => {
    expect(extractProgressCells(null)).toEqual([]);
    expect(extractProgressCells(undefined)).toEqual([]);
    expect(extractProgressCells({ overlays: [] })).toEqual([]);
    expect(extractProgressCells({ cells: 'nope' })).toEqual([]);
    expect(extractProgressCells({ cells: [{ cellId: 'x', polygon: [[0, 0], [1, 1]] }] })).toEqual([]);
    expect(extractProgressCells({ cells: [{ cellId: 'x', polygon: [[0, 0], [1, 1], [0, 'a']] }] })).toEqual([]);
    // Out-of-range coordinates (lat beyond 90 in lon-lat order)
    expect(extractProgressCells({ cells: [{ cellId: 'x', polygon: [[0, 95], [1, 95], [1, 96]] }] })).toEqual([]);
    // Missing cellId
    expect(extractProgressCells({ cells: [{ polygon: [[0, 0], [0.001, 0], [0.001, 0.001]] }] })).toEqual([]);
  });
});

describe('computeCellStates', () => {
  const cells = extractProgressCells(CELLS_RESULT);

  it('marks cells untouched before any waypoint in them is passed', () => {
    const states = computeCellStates(cells, ITEMS, 10);
    expect(states.map((s) => s.state)).toEqual(['inProgress', 'untouched', 'untouched']);
  });

  it('tracks partial and full completion', () => {
    const states = computeCellStates(cells, ITEMS, 12);
    // Cell A (wp 10, 11) fully passed; cell 7 has the live target inside.
    expect(states.map((s) => s.state)).toEqual(['completed', 'inProgress', 'untouched']);
  });

  it('completes everything past the last waypoint', () => {
    const states = computeCellStates(cells, ITEMS, 14);
    expect(states.map((s) => s.state)).toEqual(['completed', 'completed', 'untouched']);
  });

  it('leaves cells untouched with a null currentSeq', () => {
    const states = computeCellStates(cells, ITEMS, null);
    expect(states.every((s) => s.state === 'untouched')).toBe(true);
  });
});

describe('summarizeCells', () => {
  const cells = extractProgressCells(CELLS_RESULT);

  it('is null without cells', () => {
    expect(summarizeCells([])).toBeNull();
  });

  it('reports the active cell number', () => {
    const summary = summarizeCells(computeCellStates(cells, ITEMS, 12))!;
    expect(summary.done).toBe(1);
    expect(summary.total).toBe(3);
    expect(summary.activeNumber).toBe(2);
  });

  it('falls back to the completed count when nothing is in progress', () => {
    const summary = summarizeCells(computeCellStates(cells, ITEMS, 14))!;
    expect(summary.done).toBe(2);
    expect(summary.activeNumber).toBe(2);
  });
});
