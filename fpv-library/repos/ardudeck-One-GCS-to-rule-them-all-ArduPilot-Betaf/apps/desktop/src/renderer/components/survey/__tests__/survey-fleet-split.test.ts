import { describe, it, expect } from 'vitest';
import { splitPolygonIntoBands } from '../survey-fleet-split';
import type { LatLng } from '../survey-types';

// A 1km-ish square around the equator-ish for predictable axis sizing.
const square: LatLng[] = [
  { lat: 0, lng: 0 },
  { lat: 0, lng: 0.01 },
  { lat: 0.01, lng: 0.01 },
  { lat: 0.01, lng: 0 },
];

// Shoelace area (in degree^2, fine for relative comparisons).
function area(poly: LatLng[]): number {
  let a = 0;
  for (let i = 0; i < poly.length; i++) {
    const p = poly[i]!;
    const q = poly[(i + 1) % poly.length]!;
    a += p.lng * q.lat - q.lng * p.lat;
  }
  return Math.abs(a) / 2;
}

describe('splitPolygonIntoBands', () => {
  it('returns the polygon unchanged for n <= 1', () => {
    expect(splitPolygonIntoBands(square, 1)).toEqual([square]);
  });

  it('splits into n contiguous bands', () => {
    const bands = splitPolygonIntoBands(square, 3);
    expect(bands).toHaveLength(3);
    for (const b of bands) expect(b.length).toBeGreaterThanOrEqual(3);
  });

  it('bands tile the original area (sum of band areas ~= polygon area)', () => {
    const total = area(square);
    const bands = splitPolygonIntoBands(square, 4);
    const sum = bands.reduce((acc, b) => acc + area(b), 0);
    expect(sum).toBeCloseTo(total, 6);
  });

  it('produces roughly equal-area bands for a square', () => {
    const bands = splitPolygonIntoBands(square, 2);
    const a0 = area(bands[0]!);
    const a1 = area(bands[1]!);
    expect(Math.abs(a0 - a1)).toBeLessThan(total(square) * 0.05);
  });

  it('handles a triangle without throwing and keeps coverage', () => {
    const tri: LatLng[] = [
      { lat: 0, lng: 0 },
      { lat: 0, lng: 0.02 },
      { lat: 0.01, lng: 0.01 },
    ];
    const bands = splitPolygonIntoBands(tri, 3);
    const sum = bands.reduce((acc, b) => acc + area(b), 0);
    expect(sum).toBeCloseTo(area(tri), 6);
  });
});

function total(poly: LatLng[]): number {
  return area(poly);
}
