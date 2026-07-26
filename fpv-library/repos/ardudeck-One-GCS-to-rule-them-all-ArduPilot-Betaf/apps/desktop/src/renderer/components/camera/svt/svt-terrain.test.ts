import { describe, it, expect } from 'vitest';
import * as THREE from 'three';
import {
  metersPerDegLon,
  approxDistanceM,
  lonLatToLocal,
  buildTerrainGeometry,
  sampleElevation,
  M_PER_DEG_LAT,
  type ElevationGrid,
} from './svt-terrain';

/** A 3×3 grid centred at (0,0) spanning ±1000 m, elevations ramping N→S. */
function ramps(): ElevationGrid {
  return {
    centerLat: 0,
    centerLon: 0,
    halfSizeM: 1000,
    res: 3,
    // Row 0 = north edge (high), row 2 = south edge (low).
    elev: Float32Array.from([100, 100, 100, 50, 50, 50, 0, 0, 0]),
    mPerDegLon: metersPerDegLon(0),
  };
}

function flat(value: number, res = 4): ElevationGrid {
  return {
    centerLat: 0,
    centerLon: 0,
    halfSizeM: 1000,
    res,
    elev: Float32Array.from({ length: res * res }, () => value),
    mPerDegLon: metersPerDegLon(0),
  };
}

describe('metersPerDegLon', () => {
  it('is ~111 km at the equator and halves near 60°', () => {
    expect(metersPerDegLon(0)).toBeCloseTo(M_PER_DEG_LAT, 0);
    expect(metersPerDegLon(60)).toBeCloseTo(M_PER_DEG_LAT * 0.5, 0);
  });
});

describe('approxDistanceM', () => {
  it('measures a one-degree latitude step as ~111 km', () => {
    expect(approxDistanceM(0, 0, 1, 0)).toBeCloseTo(M_PER_DEG_LAT, -2);
  });
  it('is zero for identical points', () => {
    expect(approxDistanceM(12.3, 45.6, 12.3, 45.6)).toBe(0);
  });
});

describe('lonLatToLocal', () => {
  const grid = ramps();
  it('puts the centre at the origin', () => {
    const c = lonLatToLocal(grid, 0, 0);
    expect(c.x).toBeCloseTo(0, 9);
    expect(c.z).toBeCloseTo(0, 9);
  });
  it('maps east to +x and north to -z', () => {
    const east = lonLatToLocal(grid, 0, 0.001);
    expect(east.x).toBeGreaterThan(0);
    expect(east.z).toBeCloseTo(0, 6);
    const north = lonLatToLocal(grid, 0.001, 0);
    expect(north.z).toBeLessThan(0);
    expect(north.x).toBeCloseTo(0, 6);
  });
});

describe('sampleElevation', () => {
  const grid = ramps();
  it('returns the centre vertex elevation at the centre', () => {
    expect(sampleElevation(grid, 0, 0)).toBeCloseTo(50, 6);
  });
  it('bilinearly interpolates between rows', () => {
    // 500 m north of centre = halfway between the 100 m and 50 m rows → 75 m.
    const lat = 500 / M_PER_DEG_LAT;
    expect(sampleElevation(grid, lat, 0)).toBeCloseTo(75, 4);
  });
  it('clamps to the nearest edge sample outside the grid extent', () => {
    // Far north of the patch → clamps to the north edge (100 m), not 0.
    const farNorth = 5000 / M_PER_DEG_LAT;
    expect(sampleElevation(grid, farNorth, 0)).toBeCloseTo(100, 4);
    // Far south → clamps to the south edge (0 m).
    const farSouth = -5000 / M_PER_DEG_LAT;
    expect(sampleElevation(grid, farSouth, 0)).toBeCloseTo(0, 4);
  });
});

describe('buildTerrainGeometry', () => {
  it('produces res*res vertices and (res-1)^2*6 indices', () => {
    const grid = flat(10, 4);
    const geo = buildTerrainGeometry(grid);
    const pos = geo.getAttribute('position');
    expect(pos.count).toBe(16);
    expect(geo.getIndex()!.count).toBe(3 * 3 * 6);
    expect(geo.getAttribute('color').count).toBe(16);
    geo.dispose();
  });

  it('places vertex height at its elevation', () => {
    const grid = ramps();
    const geo = buildTerrainGeometry(grid);
    const pos = geo.getAttribute('position') as THREE.BufferAttribute;
    // Vertex k=0 is the NW corner with elevation 100.
    expect(pos.getY(0)).toBeCloseTo(100, 4);
    // Vertex k=8 is the SE corner with elevation 0.
    expect(pos.getY(8)).toBeCloseTo(0, 4);
    geo.dispose();
  });

  it('computes upward normals for a flat grid', () => {
    const geo = buildTerrainGeometry(flat(25, 4));
    const normals = geo.getAttribute('normal') as THREE.BufferAttribute;
    for (let i = 0; i < normals.count; i++) {
      expect(normals.getY(i)).toBeGreaterThan(0.99);
    }
    geo.dispose();
  });
});
