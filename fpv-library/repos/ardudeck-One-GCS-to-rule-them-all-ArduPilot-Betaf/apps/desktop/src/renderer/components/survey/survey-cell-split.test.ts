import { describe, it, expect } from 'vitest';
import {
  extractSplitCells,
  cellWorkloads,
  partitionContiguous,
  assignWaypointsToRuns,
  sliceWaypointsByRuns,
  cellGroupHull,
  type SplitCell,
} from './survey-cell-split';

// Three cells side by side (lon bands), tracks giving workloads 2:1:1.
const CELLS: SplitCell[] = [
  {
    cellId: 0,
    polygon: [[8.0, 53.0], [8.01, 53.0], [8.01, 53.01], [8.0, 53.01]],
    tracks: [
      [[8.001, 53.001], [8.001, 53.009]],
      [[8.005, 53.001], [8.005, 53.009]],
    ],
  },
  {
    cellId: 1,
    polygon: [[8.01, 53.0], [8.02, 53.0], [8.02, 53.01], [8.01, 53.01]],
    tracks: [[[8.015, 53.001], [8.015, 53.009]]],
  },
  {
    cellId: 2,
    polygon: [[8.02, 53.0], [8.03, 53.0], [8.03, 53.01], [8.02, 53.01]],
    tracks: [[[8.025, 53.001], [8.025, 53.009]]],
  },
];

const GR = { provider: 'topas', cells: CELLS, cellOrder: [0, 1, 2] };

describe('extractSplitCells', () => {
  it('accepts a valid decomposition and preserves order', () => {
    const out = extractSplitCells(GR)!;
    expect(out.cells).toHaveLength(3);
    expect(out.cellOrder).toEqual([0, 1, 2]);
  });

  it('rejects null, missing cells, malformed rings', () => {
    expect(extractSplitCells(null)).toBeNull();
    expect(extractSplitCells({})).toBeNull();
    expect(extractSplitCells({ cells: [{ cellId: 0, polygon: [[1, 2]] }] })).toBeNull();
    expect(extractSplitCells({ cells: [{ cellId: 'x', polygon: CELLS[0]!.polygon }] })).toBeNull();
  });

  it('falls back to declaration order when cellOrder is inconsistent', () => {
    const out = extractSplitCells({ cells: CELLS, cellOrder: [7, 8] })!;
    expect(out.cellOrder).toEqual([0, 1, 2]);
  });
});

describe('partitionContiguous', () => {
  it('balances by workload, keeping runs contiguous', () => {
    const weights = cellWorkloads(CELLS, [0, 1, 2]);
    expect(weights[0]).toBeGreaterThan(weights[1]! * 1.5); // cell 0 has 2 tracks
    // Two vehicles: heavy cell alone, the two light cells together.
    expect(partitionContiguous(weights, 2)).toEqual([[0, 1], [1, 3]]);
  });

  it('never returns more runs than items', () => {
    expect(partitionContiguous([5, 5], 4)).toEqual([[0, 1], [1, 2]]);
    expect(partitionContiguous([], 3)).toEqual([]);
  });
});

describe('waypoint slicing', () => {
  // Path visiting cell 0, transit, cell 1, cell 2 (lat/lng waypoints).
  const WPS = [
    { lat: 53.002, lng: 8.002 },
    { lat: 53.008, lng: 8.002 },
    { lat: 53.008, lng: 8.0095 }, // still cell 0
    { lat: 53.008, lng: 8.012 }, // cell 1
    { lat: 53.002, lng: 8.012 },
    { lat: 53.002, lng: 8.022 }, // cell 2
    { lat: 53.008, lng: 8.022 },
  ];

  it('assigns waypoints to fly-order runs, transits inherit the next cell', () => {
    const runs = assignWaypointsToRuns(WPS, CELLS, [0, 1, 2]);
    expect(runs).toEqual([0, 0, 0, 1, 1, 2, 2]);
  });

  it('slices per partition preserving order and coverage', () => {
    const runs = assignWaypointsToRuns(WPS, CELLS, [0, 1, 2]);
    const slices = sliceWaypointsByRuns(WPS, runs, [[0, 1], [1, 3]]);
    expect(slices[0]).toHaveLength(3);
    expect(slices[1]).toHaveLength(4);
    expect([...slices[0]!, ...slices[1]!]).toEqual(WPS);
  });

  it('cellGroupHull outlines the group', () => {
    const hull = cellGroupHull(CELLS, [0, 1, 2], [1, 3]);
    expect(hull.length).toBeGreaterThanOrEqual(4);
    const lngs = hull.map((p) => p.lng);
    expect(Math.min(...lngs)).toBeCloseTo(8.01, 5);
    expect(Math.max(...lngs)).toBeCloseTo(8.03, 5);
  });
});
