import { describe, it, expect } from 'vitest';
import {
  CELL_STEP_MS,
  ROUTE_STEP_MS,
  TRACK_STEP_MS,
  PATH_DURATION_MS,
  FADE_DURATION_MS,
  cellColor,
  computeReplayFrame,
  hasReplayData,
  parseReplayData,
  replayTotalDurationMs,
} from './plan-replay';

// GeoJSON [lon, lat] order, matching the TOPAS generatorResult wire shape.
function makeCell(cellId: number, lonOffset = 0) {
  return {
    cellId,
    trackHeadingRad: 0.5,
    polygon: [
      [8.84 + lonOffset, 53.1],
      [8.85 + lonOffset, 53.1],
      [8.85 + lonOffset, 53.11],
      [8.84 + lonOffset, 53.11],
    ],
    tracks: [
      [[8.84 + lonOffset, 53.101], [8.85 + lonOffset, 53.101]],
      [[8.84 + lonOffset, 53.105], [8.85 + lonOffset, 53.105]],
    ],
  };
}

const result = {
  provider: 'topas',
  cellOrder: [7, 5, 6],
  cells: [makeCell(5, 0), makeCell(6, 0.02), makeCell(7, 0.04)],
  overlays: [],
  summaryMetrics: {},
};

describe('parseReplayData', () => {
  it('rejects null / structurally invalid generatorResult', () => {
    expect(parseReplayData(null)).toBeNull();
    expect(parseReplayData(undefined)).toBeNull();
    expect(parseReplayData('nope')).toBeNull();
    expect(parseReplayData({})).toBeNull();
    expect(parseReplayData({ cells: [], cellOrder: [] })).toBeNull();
    expect(parseReplayData({ cells: result.cells, cellOrder: 'nope' })).toBeNull();
    expect(parseReplayData({ cells: 'nope', cellOrder: [0] })).toBeNull();
  });

  it('rejects malformed cell geometry', () => {
    // Too few polygon vertices.
    expect(
      parseReplayData({ cellOrder: [0], cells: [{ cellId: 0, polygon: [[8.84, 53.1], [8.85, 53.1]], tracks: [] }] }),
    ).toBeNull();
    // Non-numeric coordinate.
    expect(
      parseReplayData({
        cellOrder: [0],
        cells: [{ cellId: 0, polygon: [['x', 53.1], [8.85, 53.1], [8.85, 53.11]], tracks: [] }],
      }),
    ).toBeNull();
    // Out-of-range latitude (would also catch swapped lon/lat pairs).
    expect(
      parseReplayData({
        cellOrder: [0],
        cells: [{ cellId: 0, polygon: [[8.84, 153.1], [8.85, 53.1], [8.85, 53.11]], tracks: [] }],
      }),
    ).toBeNull();
  });

  it('rejects over-cap cell counts', () => {
    const cells = Array.from({ length: 250 }, (_, i) => makeCell(i));
    expect(parseReplayData({ cellOrder: [0], cells })).toBeNull();
  });

  it('rejects when no cellOrder entry resolves', () => {
    expect(parseReplayData({ ...result, cellOrder: [99, -1, 3.5] })).toBeNull();
  });

  it('converts [lon, lat] to lat/lng and resolves order by cellId', () => {
    const data = parseReplayData(result)!;
    expect(data).not.toBeNull();
    expect(data.cells).toHaveLength(3);
    expect(data.cells[0]!.polygon[0]).toEqual({ lat: 53.1, lng: 8.84 });
    expect(data.cells[0]!.tracks).toHaveLength(2);
    // cellOrder [7, 5, 6] -> array indices [2, 0, 1].
    expect(data.order).toEqual([2, 0, 1]);
    // Centroid of the first cell's square.
    expect(data.cells[0]!.centroid.lat).toBeCloseTo(53.105);
    expect(data.cells[0]!.centroid.lng).toBeCloseTo(8.845);
  });

  it('falls back to index resolution and drops duplicate / bad order entries', () => {
    const noIds = {
      cellOrder: [1, 1, 0, 99],
      cells: [
        { polygon: makeCell(0).polygon, tracks: [] },
        { polygon: makeCell(0, 0.02).polygon, tracks: [] },
      ],
    };
    expect(parseReplayData(noIds)!.order).toEqual([1, 0]);
  });

  it('drops malformed track segments without sinking the cell', () => {
    const data = parseReplayData({
      cellOrder: [0],
      cells: [
        {
          cellId: 0,
          polygon: makeCell(0).polygon,
          tracks: [[[8.84, 53.1], [8.85, 53.1]], [[8.84, 53.1]], 'junk', [[8.84, 'x'], [8.85, 53.1]]],
        },
      ],
    })!;
    expect(data.cells[0]!.tracks).toEqual([[{ lat: 53.1, lng: 8.84 }, { lat: 53.1, lng: 8.85 }]]);
  });
});

describe('hasReplayData', () => {
  it('mirrors parse success', () => {
    expect(hasReplayData(result)).toBe(true);
    expect(hasReplayData(null)).toBe(false);
    expect(hasReplayData({ overlays: [] })).toBe(false);
  });
});

describe('computeReplayFrame', () => {
  const data = parseReplayData(result)!;
  // 3 cells: decompose ends at 750, route at 750 + 900, tracks at 1650 + 600,
  // path at 2250 + 4000, fade at 6250 + 2000.
  const decomposeEnd = 3 * CELL_STEP_MS;
  const routeEnd = decomposeEnd + 3 * ROUTE_STEP_MS;
  const tracksEnd = routeEnd + 3 * TRACK_STEP_MS;
  const pathEnd = tracksEnd + PATH_DURATION_MS;

  it('shows nothing at 0ms', () => {
    const f = computeReplayFrame(0, data);
    expect(f.stage).toBe('decompose');
    expect(f.visibleCells).toBe(0);
    expect(f.visibleBadges).toBe(0);
    expect(f.visibleConnections).toBe(0);
    expect(f.visibleTrackCells).toBe(0);
    expect(f.pathFraction).toBe(0);
    expect(f.fadeOpacity).toBe(1);
    expect(f.finished).toBe(false);
  });

  it('reveals cells one per step mid-decompose', () => {
    expect(computeReplayFrame(CELL_STEP_MS * 1.5, data).visibleCells).toBe(1);
    expect(computeReplayFrame(CELL_STEP_MS * 2.5, data).visibleCells).toBe(2);
    expect(computeReplayFrame(CELL_STEP_MS * 2.5, data).visibleBadges).toBe(0);
  });

  it('adds badges and connections during route, keeping all cells', () => {
    const f = computeReplayFrame(decomposeEnd + ROUTE_STEP_MS * 1.5, data);
    expect(f.stage).toBe('route');
    expect(f.visibleCells).toBe(3);
    expect(f.visibleBadges).toBe(2);
    expect(f.visibleConnections).toBe(1);
    expect(f.visibleTrackCells).toBe(0);
  });

  it('adds tracks per visited cell during the tracks stage', () => {
    const f = computeReplayFrame(routeEnd + TRACK_STEP_MS * 1.5, data);
    expect(f.stage).toBe('tracks');
    expect(f.visibleCells).toBe(3);
    expect(f.visibleBadges).toBe(3);
    expect(f.visibleConnections).toBe(2);
    expect(f.visibleTrackCells).toBe(2);
    expect(f.pathFraction).toBe(0);
  });

  it('grows the path fraction to 1 while keeping everything else', () => {
    const mid = computeReplayFrame(tracksEnd + PATH_DURATION_MS / 2, data);
    expect(mid.stage).toBe('path');
    expect(mid.visibleTrackCells).toBe(3);
    expect(mid.pathFraction).toBeCloseTo(0.5);
    expect(computeReplayFrame(pathEnd, data).pathFraction).toBe(1);
  });

  it('fades everything out after the path completes', () => {
    const f = computeReplayFrame(pathEnd + FADE_DURATION_MS / 2, data);
    expect(f.stage).toBe('fade');
    expect(f.pathFraction).toBe(1);
    expect(f.fadeOpacity).toBeCloseTo(0.5);
    expect(f.finished).toBe(false);
  });

  it('finishes past the fade', () => {
    const f = computeReplayFrame(pathEnd + FADE_DURATION_MS + 1, data);
    expect(f.stage).toBe('done');
    expect(f.finished).toBe(true);
    expect(f.fadeOpacity).toBe(0);
  });

  it('reports the total duration used by the finished flag', () => {
    const total = replayTotalDurationMs(data);
    expect(total).toBe(pathEnd + FADE_DURATION_MS);
    expect(computeReplayFrame(total - 1, data).finished).toBe(false);
    expect(computeReplayFrame(total, data).finished).toBe(true);
  });
});

describe('cellColor', () => {
  it('uses the shared hue formula', () => {
    expect(cellColor(0)).toBe('hsl(0 70% 55%)');
    expect(cellColor(2)).toBe('hsl(94 70% 55%)');
    expect(cellColor(10)).toBe('hsl(110 70% 55%)');
  });
});
