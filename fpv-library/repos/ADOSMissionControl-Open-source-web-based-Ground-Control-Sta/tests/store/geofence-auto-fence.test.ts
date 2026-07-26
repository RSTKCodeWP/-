import { describe, it, expect, beforeEach, vi } from 'vitest';

vi.mock('@/stores/drone-manager', () => ({
  useDroneManager: {
    getState: vi.fn(() => ({ getSelectedProtocol: () => null })),
  },
}));

import { useGeofenceStore } from '@/stores/geofence-store';
import { polygonBounds } from '@/lib/drawing/geo-utils';

/** A closed-ish square of boundary points near Bangalore. */
const SQUARE: [number, number][] = [
  [12.970, 77.590],
  [12.970, 77.600],
  [12.980, 77.600],
  [12.980, 77.590],
];

describe('geofence-store generateFromBoundary', () => {
  beforeEach(() => {
    useGeofenceStore.getState().clearFence();
    useGeofenceStore.getState().setFenceType('circle');
    useGeofenceStore.getState().setEnabled(false);
    vi.clearAllMocks();
  });

  it('commits an enabled polygon fence', () => {
    useGeofenceStore.getState().generateFromBoundary(SQUARE, 100);
    const s = useGeofenceStore.getState();
    expect(s.enabled).toBe(true);
    expect(s.fenceType).toBe('polygon');
    expect(s.polygonPoints.length).toBeGreaterThanOrEqual(3);
  });

  it('produces a polygon whose bbox strictly encloses the input bbox', () => {
    useGeofenceStore.getState().generateFromBoundary(SQUARE, 100);
    const inB = polygonBounds(SQUARE);
    const outB = polygonBounds(useGeofenceStore.getState().polygonPoints);
    expect(outB.minLat).toBeLessThan(inB.minLat);
    expect(outB.maxLat).toBeGreaterThan(inB.maxLat);
    expect(outB.minLon).toBeLessThan(inB.minLon);
    expect(outB.maxLon).toBeGreaterThan(inB.maxLon);
  });

  it('encloses every input point within the generated fence bbox', () => {
    useGeofenceStore.getState().generateFromBoundary(SQUARE, 50);
    const outB = polygonBounds(useGeofenceStore.getState().polygonPoints);
    for (const [lat, lon] of SQUARE) {
      expect(lat).toBeGreaterThanOrEqual(outB.minLat);
      expect(lat).toBeLessThanOrEqual(outB.maxLat);
      expect(lon).toBeGreaterThanOrEqual(outB.minLon);
      expect(lon).toBeLessThanOrEqual(outB.maxLon);
    }
  });

  it('grows the fence when the buffer grows', () => {
    useGeofenceStore.getState().generateFromBoundary(SQUARE, 50);
    const small = polygonBounds(useGeofenceStore.getState().polygonPoints);
    useGeofenceStore.getState().generateFromBoundary(SQUARE, 500);
    const large = polygonBounds(useGeofenceStore.getState().polygonPoints);
    expect(large.maxLat - large.minLat).toBeGreaterThan(small.maxLat - small.minLat);
    expect(large.maxLon - large.minLon).toBeGreaterThan(small.maxLon - small.minLon);
  });

  it('handles a single point by wrapping a buffer box around it', () => {
    useGeofenceStore.getState().generateFromBoundary([[12.97, 77.59]], 100);
    const s = useGeofenceStore.getState();
    expect(s.enabled).toBe(true);
    const b = polygonBounds(s.polygonPoints);
    expect(b.maxLat).toBeGreaterThan(b.minLat);
    expect(b.maxLon).toBeGreaterThan(b.minLon);
  });

  it('is a no-op on an empty point list', () => {
    useGeofenceStore.getState().setPolygonPoints([[1, 2], [3, 4], [5, 6]]);
    useGeofenceStore.getState().generateFromBoundary([], 100);
    expect(useGeofenceStore.getState().polygonPoints).toEqual([[1, 2], [3, 4], [5, 6]]);
    expect(useGeofenceStore.getState().enabled).toBe(false);
  });

  it('clamps a non-positive buffer to zero (bbox equals input bbox)', () => {
    useGeofenceStore.getState().generateFromBoundary(SQUARE, -100);
    const inB = polygonBounds(SQUARE);
    const outB = polygonBounds(useGeofenceStore.getState().polygonPoints);
    expect(outB.minLat).toBeCloseTo(inB.minLat, 9);
    expect(outB.maxLat).toBeCloseTo(inB.maxLat, 9);
    expect(outB.minLon).toBeCloseTo(inB.minLon, 9);
    expect(outB.maxLon).toBeCloseTo(inB.maxLon, 9);
  });
});
