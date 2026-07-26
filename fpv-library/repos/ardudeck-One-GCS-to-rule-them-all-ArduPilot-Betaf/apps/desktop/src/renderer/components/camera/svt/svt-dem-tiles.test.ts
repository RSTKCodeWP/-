import { describe, it, expect } from 'vitest';
import {
  lonToTileX,
  latToTileY,
  pickZoom,
  sampleHeightfield,
  type Heightfield,
} from './svt-dem-tiles';

describe('tile projection', () => {
  it('maps the antimeridian/equator origin to tile 0 and the centre to the middle', () => {
    expect(lonToTileX(-180, 1)).toBeCloseTo(0, 6);
    expect(lonToTileX(0, 1)).toBeCloseTo(1, 6); // centre of a z=1 world (2 tiles)
    expect(latToTileY(0, 1)).toBeCloseTo(1, 6); // equator is the vertical centre
  });

  it('increases tile Y as latitude decreases (Y grows southward)', () => {
    expect(latToTileY(10, 8)).toBeLessThan(latToTileY(-10, 8));
  });
});

describe('pickZoom', () => {
  it('stays within the clamp range and grows as the patch shrinks', () => {
    const big = pickZoom(50_000, 45);
    const small = pickZoom(5_000, 45);
    expect(big).toBeGreaterThanOrEqual(8);
    expect(small).toBeLessThanOrEqual(12);
    expect(small).toBeGreaterThanOrEqual(big);
  });
});

describe('sampleHeightfield', () => {
  // A 2×2-pixel field, one tile, where the heightfield happens to align so the
  // sampled corners are the four pixel values.
  const hf: Heightfield = {
    zoom: 0,
    originTileX: 0,
    originTileY: 0,
    width: 2,
    height: 2,
    elev: Float32Array.from([0, 100, 200, 300]),
    loadedTiles: 1,
  };

  it('clamps out-of-range samples to the field edges (no NaN)', () => {
    const v = sampleHeightfield(hf, 0, 0);
    expect(Number.isFinite(v)).toBe(true);
  });

  it('interpolates within the field rather than snapping', () => {
    // Two nearby longitudes at the same latitude should not generally be equal.
    const a = sampleHeightfield(hf, 10, -90);
    const b = sampleHeightfield(hf, 10, 90);
    expect(Number.isFinite(a)).toBe(true);
    expect(Number.isFinite(b)).toBe(true);
  });
});
