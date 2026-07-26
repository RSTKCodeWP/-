import { describe, it, expect } from 'vitest';
import { simplifyPolygon } from './geo-math';
import type { LatLng } from './survey-types';

describe('simplifyPolygon', () => {
  it('collapses dense collinear points on a square to its corners', () => {
    // A square whose edges are densely sampled with intermediate points that
    // carry no shape information.
    const ring: LatLng[] = [];
    const N = 50;
    for (let i = 0; i < N; i++) ring.push({ lat: 0, lng: (i / N) * 0.01 });        // bottom
    for (let i = 0; i < N; i++) ring.push({ lat: (i / N) * 0.01, lng: 0.01 });     // right
    for (let i = 0; i < N; i++) ring.push({ lat: 0.01, lng: 0.01 - (i / N) * 0.01 }); // top
    for (let i = 0; i < N; i++) ring.push({ lat: 0.01 - (i / N) * 0.01, lng: 0 });  // left

    const out = simplifyPolygon(ring, 1.0);

    // 200 input points → ~4 meaningful corners.
    expect(out.length).toBeLessThanOrEqual(6);
    expect(out.length).toBeGreaterThanOrEqual(4);
  });

  it('preserves a genuine corner that exceeds the tolerance', () => {
    // An L-shaped notch ~30 m deep must survive a 2 m tolerance.
    const ring: LatLng[] = [
      { lat: 0, lng: 0 },
      { lat: 0, lng: 0.002 },
      { lat: 0.0003, lng: 0.002 }, // ~33 m notch
      { lat: 0.0003, lng: 0.001 },
      { lat: 0.001, lng: 0.001 },
      { lat: 0.001, lng: 0 },
    ];
    const out = simplifyPolygon(ring, 2.0);
    expect(out.length).toBe(ring.length);
  });

  it('leaves a small simple polygon untouched', () => {
    const tri: LatLng[] = [
      { lat: 0, lng: 0 },
      { lat: 0, lng: 0.001 },
      { lat: 0.001, lng: 0 },
    ];
    expect(simplifyPolygon(tri, 1.0)).toEqual(tri);
  });
});
