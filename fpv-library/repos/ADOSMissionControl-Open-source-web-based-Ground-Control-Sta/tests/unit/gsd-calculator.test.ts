import { describe, it, expect } from 'vitest';
import {
  computeGSD,
  computeFootprint,
  computeLineSpacing,
  computeTriggerDistance,
  CAMERA_PROFILES,
} from '@/lib/patterns/gsd-calculator';

describe('computeGSD()', () => {
  it('at known altitude with known camera', () => {
    // GSD = (sensorWidth * altitude) / (focalLength * imageWidth)
    // Using GoPro Hero 12: sensorWidth=6.17, focalLength=2.7, imageWidth=5312
    // At 100m: GSD = (6.17 * 100) / (2.7 * 5312) = 617 / 14342.4 ~ 0.043 m/px
    const gsd = computeGSD(100, 2.7, 6.17, 5312);
    expect(gsd).toBeCloseTo(0.043, 2);
  });

  it('returns 0 for invalid inputs', () => {
    expect(computeGSD(-10, 2.7, 6.17, 5312)).toBe(0); // negative altitude
    expect(computeGSD(100, 0, 6.17, 5312)).toBe(0);    // zero focal length
    expect(computeGSD(100, 2.7, 0, 5312)).toBe(0);     // zero sensor width
    expect(computeGSD(100, 2.7, 6.17, 0)).toBe(0);     // zero image width
  });
});

describe('computeFootprint()', () => {
  it('width and height scale with altitude', () => {
    const cam = CAMERA_PROFILES[0]; // GoPro Hero 12
    const fp50 = computeFootprint(50, cam);
    const fp100 = computeFootprint(100, cam);

    // At double the altitude, footprint should be double
    expect(fp100.width).toBeCloseTo(fp50.width * 2, 1);
    expect(fp100.height).toBeCloseTo(fp50.height * 2, 1);
  });
});

describe('computeLineSpacing()', () => {
  it('decreases with more sidelap', () => {
    const cam = CAMERA_PROFILES[0];
    const spacing60 = computeLineSpacing(100, cam, 0.6);
    const spacing80 = computeLineSpacing(100, cam, 0.8);

    expect(spacing80).toBeLessThan(spacing60);
  });
});

describe('computeTriggerDistance()', () => {
  it('decreases with more frontlap', () => {
    const cam = CAMERA_PROFILES[0];
    const trigger60 = computeTriggerDistance(100, cam, 0.6);
    const trigger80 = computeTriggerDistance(100, cam, 0.8);

    expect(trigger80).toBeLessThan(trigger60);
  });
});

describe('CAMERA_PROFILES', () => {
  it('has at least 5 entries', () => {
    expect(CAMERA_PROFILES.length).toBeGreaterThanOrEqual(5);
  });
});

describe('computeGSD with first camera profile', () => {
  it('matches manual calculation', () => {
    const cam = CAMERA_PROFILES[0]; // GoPro Hero 12
    const altitude = 50;
    const expectedGsd = (cam.sensorWidth * altitude) / (cam.focalLength * cam.imageWidth);
    const actual = computeGSD(altitude, cam.focalLength, cam.sensorWidth, cam.imageWidth);
    expect(actual).toBeCloseTo(expectedGsd, 8);
  });
});
