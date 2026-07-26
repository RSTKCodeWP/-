import { describe, it, expect } from 'vitest';
import { buildGrid, speedDirToUV, parseWindResponse, type GridSpec } from './open-meteo-wind';
import type { WindBBox } from '../../shared/wind-types';

const BBOX: WindBBox = { south: 42, north: 43, west: 19, east: 20 };

describe('buildGrid', () => {
  it('produces a grid bounded by the bbox, south-up and west-first', () => {
    const g = buildGrid(BBOX);
    expect(g.width).toBeGreaterThanOrEqual(6);
    expect(g.height).toBeGreaterThanOrEqual(6);
    expect(g.lats[0]).toBeCloseTo(42); // row 0 = south
    expect(g.lats[g.lats.length - 1]).toBeCloseTo(43); // last row = north
    expect(g.lons[0]).toBeCloseTo(19); // col 0 = west
    expect(g.lons[g.lons.length - 1]).toBeCloseTo(20);
  });

  it('caps the axis count for huge bboxes', () => {
    const g = buildGrid({ south: -50, north: 50, west: -100, east: 100 });
    expect(g.width).toBeLessThanOrEqual(22);
    expect(g.height).toBeLessThanOrEqual(22);
  });
});

describe('speedDirToUV', () => {
  it('wind from the north blows southward (v negative, u ~0)', () => {
    const { u, v } = speedDirToUV(10, 0);
    expect(u).toBeCloseTo(0, 6);
    expect(v).toBeCloseTo(-10, 6);
  });

  it('wind from the east blows westward (u negative, v ~0)', () => {
    const { u, v } = speedDirToUV(10, 90);
    expect(u).toBeCloseTo(-10, 6);
    expect(v).toBeCloseTo(0, 6);
  });

  it('wind from the west blows eastward (u positive)', () => {
    const { u } = speedDirToUV(7, 270);
    expect(u).toBeCloseTo(7, 6);
  });
});

describe('parseWindResponse', () => {
  const grid: GridSpec = { width: 2, height: 1, lats: [42], lons: [19, 20] };

  it('stacks hourly frames and tracks the max speed', () => {
    const locations = [
      { hourly: { time: ['t0', 't1'], wind_speed_120m: [10, 0], wind_direction_120m: [0, 0] } },
      { hourly: { time: ['t0', 't1'], wind_speed_120m: [5, 20], wind_direction_120m: [90, 90] } },
    ];
    const { frames, speedMax } = parseWindResponse(locations, grid, 120);
    expect(frames).toHaveLength(2);
    // cell 0, frame 0: from north @10 -> v=-10
    expect(frames[0]!.v[0]).toBeCloseTo(-10, 4);
    // cell 1, frame 0: from east @5 -> u=-5
    expect(frames[0]!.u[1]).toBeCloseTo(-5, 4);
    expect(speedMax).toBeCloseTo(20, 4);
    expect(frames[0]!.time).toBe('t0');
  });

  it('fills zero for missing/non-finite samples', () => {
    const locations = [
      { hourly: { time: ['t0'], wind_speed_120m: [Number.NaN], wind_direction_120m: [0] } },
      { hourly: { time: ['t0'] } },
    ];
    const { frames } = parseWindResponse(locations, grid, 120);
    expect(frames[0]!.u[0]).toBe(0);
    expect(frames[0]!.v[0]).toBe(0);
    expect(frames[0]!.u[1]).toBe(0);
  });
});
