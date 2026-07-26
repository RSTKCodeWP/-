import { describe, it, expect } from 'vitest';
import { generateSurveyGrid, generateCrosshatch, generateSpiral, generateOrbit, polygonArea } from './survey';

const SQUARE = [
  { lat: 34.258, lon: 108.942 },
  { lat: 34.259, lon: 108.942 },
  { lat: 34.259, lon: 108.943 },
  { lat: 34.258, lon: 108.943 },
];

describe('generateSurveyGrid', () => {
  it('generates waypoints for a valid polygon', () => {
    const wps = generateSurveyGrid(SQUARE, { angle: 0, spacing: 20, alt: 50, overshoot: 5 });
    expect(wps.length).toBeGreaterThan(0);
    for (const wp of wps) {
      expect(wp.alt).toBe(50);
      expect(wp.type).toBe('wp');
      expect(wp.drop).toBe(false);
    }
  });

  it('returns empty for less than 3 vertices', () => {
    expect(generateSurveyGrid([], { angle: 0, spacing: 20, alt: 50, overshoot: 0 })).toEqual([]);
    expect(generateSurveyGrid([SQUARE[0], SQUARE[1]], { angle: 0, spacing: 20, alt: 50, overshoot: 0 })).toEqual([]);
  });

  it('spacing affects waypoint count', () => {
    const dense = generateSurveyGrid(SQUARE, { angle: 0, spacing: 10, alt: 30, overshoot: 0 });
    const sparse = generateSurveyGrid(SQUARE, { angle: 0, spacing: 50, alt: 30, overshoot: 0 });
    expect(dense.length).toBeGreaterThan(sparse.length);
  });

  it('produces serpentine pattern', () => {
    const wps = generateSurveyGrid(SQUARE, { angle: 0, spacing: 30, alt: 40, overshoot: 0 });
    if (wps.length >= 4) {
      const first2 = wps[1].lon - wps[0].lon;
      const next2 = wps[3].lon - wps[2].lon;
      expect(Math.sign(first2)).toBe(-Math.sign(next2));
    }
  });

  it('angle rotates grid pattern', () => {
    const a0 = generateSurveyGrid(SQUARE, { angle: 0, spacing: 20, alt: 30, overshoot: 0 });
    const a45 = generateSurveyGrid(SQUARE, { angle: 45, spacing: 20, alt: 30, overshoot: 0 });
    expect(a0.length).not.toBe(a45.length);
  });
});

describe('polygonArea', () => {
  it('computes area for a ~100m square', () => {
    const side = 100;
    const sq = [
      { lat: 34.258, lon: 108.942 },
      { lat: 34.258 + side / 111320, lon: 108.942 },
      { lat: 34.258 + side / 111320, lon: 108.942 + side / (111320 * Math.cos((34.258 * Math.PI) / 180)) },
      { lat: 34.258, lon: 108.942 + side / (111320 * Math.cos((34.258 * Math.PI) / 180)) },
    ];
    const area = polygonArea(sq);
    expect(area).toBeGreaterThan(9000);
    expect(area).toBeLessThan(11000);
  });

  it('returns 0 for fewer than 3 points', () => {
    expect(polygonArea([])).toBe(0);
    expect(polygonArea([{ lat: 0, lon: 0 }])).toBe(0);
  });
});

describe('generateCrosshatch', () => {
  it('produces waypoints from two perpendicular passes', () => {
    const wps = generateCrosshatch(SQUARE, { angle: 0, spacing: 30, alt: 60, overshoot: 0 });
    expect(wps.length).toBeGreaterThan(0);
    for (const wp of wps) {
      expect(wp.alt).toBe(60);
      expect(wp.type).toBe('wp');
    }
  });

  it('generates more waypoints than a single grid pass', () => {
    const single = generateSurveyGrid(SQUARE, { angle: 0, spacing: 30, alt: 50, overshoot: 0 });
    const cross = generateCrosshatch(SQUARE, { angle: 0, spacing: 30, alt: 50, overshoot: 0 });
    expect(cross.length).toBeGreaterThan(single.length);
  });

  it('returns empty for polygon with fewer than 3 vertices', () => {
    expect(generateCrosshatch([], { angle: 0, spacing: 20, alt: 50, overshoot: 0 })).toEqual([]);
    expect(generateCrosshatch([SQUARE[0]], { angle: 0, spacing: 20, alt: 50, overshoot: 0 })).toEqual([]);
  });

  it('second pass is offset by 90 degrees from the first', () => {
    const config = { angle: 45, spacing: 30, alt: 50, overshoot: 0 };
    const pass1 = generateSurveyGrid(SQUARE, config);
    const pass2 = generateSurveyGrid(SQUARE, { ...config, angle: 135 });
    const cross = generateCrosshatch(SQUARE, config);
    expect(cross.length).toBe(pass1.length + pass2.length);
  });
});

describe('generateSpiral', () => {
  const center = { lat: 34.258, lon: 108.942 };

  it('generates waypoints spiraling outward from center', () => {
    const wps = generateSpiral(center, 100, 20, 40);
    expect(wps.length).toBeGreaterThan(0);
    for (const wp of wps) {
      expect(wp.alt).toBe(40);
      expect(wp.type).toBe('wp');
      expect(wp.drop).toBe(false);
    }
  });

  it('first waypoint is near center', () => {
    const wps = generateSpiral(center, 200, 25, 50);
    expect(Math.abs(wps[0].lat - center.lat)).toBeLessThan(0.0001);
    expect(Math.abs(wps[0].lon - center.lon)).toBeLessThan(0.0001);
  });

  it('last waypoint is near maxRadius from center', () => {
    const maxRadius = 100;
    const wps = generateSpiral(center, maxRadius, 20, 50);
    const last = wps[wps.length - 1];
    const dlat = (last.lat - center.lat) * 111320;
    const dlon = (last.lon - center.lon) * 111320 * Math.cos((center.lat * Math.PI) / 180);
    const dist = Math.sqrt(dlat * dlat + dlon * dlon);
    expect(dist).toBeGreaterThan(maxRadius * 0.8);
    expect(dist).toBeLessThan(maxRadius * 1.2);
  });

  it('smaller spacing produces more waypoints', () => {
    const dense = generateSpiral(center, 100, 10, 50);
    const sparse = generateSpiral(center, 100, 50, 50);
    expect(dense.length).toBeGreaterThan(sparse.length);
  });

  it('larger maxRadius produces more waypoints', () => {
    const small = generateSpiral(center, 50, 20, 50);
    const large = generateSpiral(center, 200, 20, 50);
    expect(large.length).toBeGreaterThan(small.length);
  });
});

describe('generateOrbit', () => {
  const center = { lat: 34.258, lon: 108.942 };

  it('generates the requested number of waypoints', () => {
    const wps = generateOrbit(center, 50, 12, 30);
    expect(wps).toHaveLength(12);
  });

  it('all waypoints are loiter_turns type', () => {
    const wps = generateOrbit(center, 50, 8, 40);
    for (const wp of wps) {
      expect(wp.type).toBe('loiter_turns');
      expect(wp.alt).toBe(40);
      expect(wp.drop).toBe(false);
    }
  });

  it('waypoints are approximately at the specified radius', () => {
    const radius = 100;
    const wps = generateOrbit(center, radius, 16, 50);
    for (const wp of wps) {
      const dlat = (wp.lat - center.lat) * 111320;
      const dlon = (wp.lon - center.lon) * 111320 * Math.cos((center.lat * Math.PI) / 180);
      const dist = Math.sqrt(dlat * dlat + dlon * dlon);
      expect(dist).toBeGreaterThan(radius * 0.9);
      expect(dist).toBeLessThan(radius * 1.1);
    }
  });

  it('waypoints form a circle (evenly distributed angles)', () => {
    const wps = generateOrbit(center, 50, 4, 30);
    // 4 points should be N, E, S, W relative to center
    // Point 0 should be roughly north (higher lat, same lon)
    expect(wps[0].lat).toBeGreaterThan(center.lat);
    expect(Math.abs(wps[0].lon - center.lon)).toBeLessThan(0.0001);
  });

  it('returns empty array for count of 0', () => {
    const wps = generateOrbit(center, 50, 0, 30);
    expect(wps).toHaveLength(0);
  });
});
