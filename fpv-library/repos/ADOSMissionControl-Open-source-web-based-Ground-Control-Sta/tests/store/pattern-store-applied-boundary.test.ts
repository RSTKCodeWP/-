import { describe, it, expect, beforeEach, vi } from 'vitest';

// Deterministic drawing store: no drawn shapes by default. Individual tests
// override getState when they need a drawn-polygon fallback.
const drawState: { polygons: unknown[]; circles: unknown[]; selectedPolygonIds: string[]; clearAll: () => void } = {
  polygons: [],
  circles: [],
  selectedPolygonIds: [],
  clearAll: vi.fn(),
};
vi.mock('@/stores/drawing-store', () => ({
  useDrawingStore: {
    getState: vi.fn(() => drawState),
  },
}));

vi.mock('@/lib/storage', () => ({
  indexedDBStorage: {
    storage: () => ({
      getItem: vi.fn(async () => null),
      setItem: vi.fn(async () => {}),
      removeItem: vi.fn(async () => {}),
    }),
  },
}));

import {
  usePatternStore,
  parallelTrackRect,
  expandingSquareReach,
  type AppliedBoundary,
} from '@/stores/pattern-store';

const RESULT = {
  waypoints: [{ lat: 12, lon: 77, alt: 50, speed: 5, command: 'WAYPOINT' }],
  previewLines: [],
  stats: { totalDistance: 100, estimatedTime: 20, photoCount: 0, coveredArea: 0, transectCount: 1 },
};

describe('pattern-store applied boundary', () => {
  beforeEach(() => {
    usePatternStore.setState({ appliedBoundary: null, patternResult: null });
    usePatternStore.getState().clear();
    drawState.polygons = [];
    drawState.circles = [];
    vi.clearAllMocks();
  });

  it('has appliedBoundary null in the initial state', () => {
    expect(usePatternStore.getState().appliedBoundary).toBeNull();
  });

  it('setAppliedBoundary stores the boundary, clearAppliedBoundary removes it', () => {
    const b: AppliedBoundary = { kind: 'polygon', positions: [[12, 77], [12, 78], [13, 78]] };
    usePatternStore.getState().setAppliedBoundary(b);
    expect(usePatternStore.getState().appliedBoundary).toEqual(b);
    usePatternStore.getState().clearAppliedBoundary();
    expect(usePatternStore.getState().appliedBoundary).toBeNull();
  });

  it('clear() with no generated result leaves appliedBoundary null', () => {
    usePatternStore.setState({ activePatternType: 'survey', surveyConfig: { polygon: [[12, 77], [12, 78], [13, 78]] } });
    usePatternStore.getState().clear();
    expect(usePatternStore.getState().appliedBoundary).toBeNull();
    expect(usePatternStore.getState().activePatternType).toBeNull();
  });

  it('clear() with a generated result and no geometry clears any prior outline', () => {
    usePatternStore.getState().setAppliedBoundary({ kind: 'point', center: [1, 2] });
    usePatternStore.setState({ activePatternType: 'expandingSquare', patternResult: RESULT });
    usePatternStore.getState().clear();
    expect(usePatternStore.getState().appliedBoundary).toBeNull();
  });

  it('clear() captures a survey polygon boundary when a result exists', () => {
    const poly: [number, number][] = [[12, 77], [12, 78], [13, 78]];
    usePatternStore.setState({ activePatternType: 'survey', surveyConfig: { polygon: poly }, patternResult: RESULT });
    usePatternStore.getState().clear();
    expect(usePatternStore.getState().appliedBoundary).toEqual({ kind: 'polygon', positions: poly });
  });

  it('clear() falls back to the last drawn polygon for survey', () => {
    drawState.polygons = [{ id: 'p1', vertices: [[12, 77], [12, 78], [13, 78]], area: 1 }];
    usePatternStore.setState({ activePatternType: 'survey', surveyConfig: {}, patternResult: RESULT });
    usePatternStore.getState().clear();
    expect(usePatternStore.getState().appliedBoundary).toEqual({
      kind: 'polygon',
      positions: [[12, 77], [12, 78], [13, 78]],
    });
  });

  it('clear() captures an orbit circle boundary', () => {
    usePatternStore.setState({ activePatternType: 'orbit', orbitConfig: { center: [12, 77], radius: 80 }, patternResult: RESULT });
    usePatternStore.getState().clear();
    expect(usePatternStore.getState().appliedBoundary).toEqual({ kind: 'circle', center: [12, 77], radius: 80 });
  });

  it('clear() captures a corridor polyline boundary', () => {
    const pts: [number, number][] = [[12, 77], [12.1, 77.1]];
    usePatternStore.setState({ activePatternType: 'corridor', corridorConfig: { pathPoints: pts }, patternResult: RESULT });
    usePatternStore.getState().clear();
    expect(usePatternStore.getState().appliedBoundary).toEqual({ kind: 'polyline', positions: pts });
  });

  it('clear() captures an expanding-square coverage ring', () => {
    usePatternStore.setState({
      activePatternType: 'expandingSquare',
      sarExpandingSquareConfig: { center: [12, 77], legSpacing: 50, maxLegs: 20 },
      patternResult: RESULT,
    });
    usePatternStore.getState().clear();
    const b = usePatternStore.getState().appliedBoundary;
    expect(b).toEqual({ kind: 'circle', center: [12, 77], radius: 500 });
  });

  it('clear() captures a sector-search coverage ring using the search radius', () => {
    usePatternStore.setState({
      activePatternType: 'sectorSearch',
      sarSectorSearchConfig: { center: [12, 77], radius: 300 },
      patternResult: RESULT,
    });
    usePatternStore.getState().clear();
    expect(usePatternStore.getState().appliedBoundary).toEqual({ kind: 'circle', center: [12, 77], radius: 300 });
  });

  it('clear() captures a parallel-track coverage rectangle', () => {
    usePatternStore.setState({
      activePatternType: 'parallelTrack',
      sarParallelTrackConfig: { startPoint: [12, 77], trackLength: 500, trackSpacing: 50, trackCount: 10, bearing: 0 },
      patternResult: RESULT,
    });
    usePatternStore.getState().clear();
    const b = usePatternStore.getState().appliedBoundary;
    expect(b?.kind).toBe('polygon');
    expect((b as { positions: [number, number][] }).positions).toHaveLength(4);
  });

  it('clear() captures a landing point marker', () => {
    usePatternStore.setState({
      activePatternType: 'fixedWingLanding',
      fixedWingLandingConfig: { landingPoint: [12, 77] },
      patternResult: RESULT,
    });
    usePatternStore.getState().clear();
    expect(usePatternStore.getState().appliedBoundary).toEqual({ kind: 'point', center: [12, 77] });
  });

  it('setPatternType hides the applied outline by activating a pattern without erasing it', () => {
    usePatternStore.getState().setAppliedBoundary({ kind: 'point', center: [1, 2] });
    usePatternStore.getState().setPatternType('survey');
    // The outline stays in memory (PatternOverlay only renders it while no pattern is active).
    expect(usePatternStore.getState().appliedBoundary).toEqual({ kind: 'point', center: [1, 2] });
    expect(usePatternStore.getState().activePatternType).toBe('survey');
  });
});

describe('pattern geometry helpers', () => {
  it('expandingSquareReach scales with leg spacing and count', () => {
    expect(expandingSquareReach({ legSpacing: 50, maxLegs: 20 })).toBe(500);
    expect(expandingSquareReach({ legSpacing: 100, maxLegs: 10 })).toBe(500);
    // Falls back to defaults when fields are missing.
    expect(expandingSquareReach({})).toBe(500);
  });

  it('parallelTrackRect returns four corners for a valid config', () => {
    const rect = parallelTrackRect({ startPoint: [12, 77], trackLength: 500, trackSpacing: 50, trackCount: 10, bearing: 0 });
    expect(rect).not.toBeNull();
    expect(rect).toHaveLength(4);
    expect(rect![0]).toEqual([12, 77]);
  });

  it('parallelTrackRect returns null when the area is degenerate', () => {
    expect(parallelTrackRect({ startPoint: [12, 77], trackLength: 0, trackSpacing: 50, trackCount: 10 })).toBeNull();
    expect(parallelTrackRect({ startPoint: [12, 77], trackLength: 500, trackSpacing: 50, trackCount: 1 })).toBeNull();
    expect(parallelTrackRect({ trackLength: 500, trackSpacing: 50, trackCount: 10 })).toBeNull();
  });
});
