import { describe, it, expect } from 'vitest';
import {
  EXTRA_CAMERA_PROFILES,
  findCameraByName,
  validateCameraProfile,
} from '@/lib/patterns/camera-library';
import { computeGSD, CAMERA_PROFILES, type CameraProfile } from '@/lib/patterns/gsd-calculator';

describe('EXTRA_CAMERA_PROFILES', () => {
  it('contains a useful number of profiles', () => {
    expect(EXTRA_CAMERA_PROFILES.length).toBeGreaterThanOrEqual(8);
    expect(EXTRA_CAMERA_PROFILES.length).toBeLessThanOrEqual(12);
  });

  it('every profile has valid physical specs', () => {
    for (const cam of EXTRA_CAMERA_PROFILES) {
      expect(validateCameraProfile(cam).valid).toBe(true);
    }
  });

  it('every profile has a non-empty unique name', () => {
    const names = EXTRA_CAMERA_PROFILES.map((c) => c.name);
    for (const n of names) expect(n.trim().length).toBeGreaterThan(0);
    expect(new Set(names).size).toBe(names.length);
  });

  it('does not duplicate the built-in profile names', () => {
    const builtIn = new Set(CAMERA_PROFILES.map((c) => c.name));
    for (const cam of EXTRA_CAMERA_PROFILES) {
      expect(builtIn.has(cam.name)).toBe(false);
    }
  });

  it('profiles feed a plausible GSD', () => {
    // DJI Zenmuse P1 (35mm) at 100m ~= (35.9 * 100) / (35 * 8192) ~ 0.0125 m/px
    const p1 = findCameraByName('DJI Zenmuse P1');
    expect(p1).toBeDefined();
    const gsd = computeGSD(100, p1!.focalLength, p1!.sensorWidth, p1!.imageWidth);
    expect(gsd).toBeGreaterThan(0);
    expect(gsd).toBeCloseTo(0.0125, 3);
  });
});

describe('findCameraByName()', () => {
  it('finds an exact match', () => {
    const cam = findCameraByName('Sony A7 III');
    expect(cam?.name).toBe('Sony A7 III');
  });

  it('is case-insensitive and trims whitespace', () => {
    expect(findCameraByName('  dji air 2s ')?.name).toBe('DJI Air 2S');
  });

  it('returns undefined for an unknown name', () => {
    expect(findCameraByName('Nonexistent Cam 9000')).toBeUndefined();
  });

  it('returns undefined for empty or blank input', () => {
    expect(findCameraByName('')).toBeUndefined();
    expect(findCameraByName('   ')).toBeUndefined();
  });

  it('searches a caller-supplied merged list', () => {
    const merged: CameraProfile[] = [...CAMERA_PROFILES, ...EXTRA_CAMERA_PROFILES];
    expect(findCameraByName('DJI Mavic 3', merged)?.name).toBe('DJI Mavic 3');
    expect(findCameraByName('Phase One iXM-100', merged)?.name).toBe('Phase One iXM-100');
    // Not present when searching only the default extras list.
    expect(findCameraByName('DJI Mavic 3')).toBeUndefined();
  });
});

describe('validateCameraProfile()', () => {
  const good: CameraProfile = {
    name: 'Test Cam',
    sensorWidth: 13.2,
    sensorHeight: 8.8,
    focalLength: 8.8,
    imageWidth: 5472,
    imageHeight: 3648,
  };

  it('accepts a well-formed profile', () => {
    const res = validateCameraProfile(good);
    expect(res.valid).toBe(true);
    expect(res.errors).toEqual([]);
  });

  it('rejects non-object input', () => {
    expect(validateCameraProfile(null).valid).toBe(false);
    expect(validateCameraProfile('camera').valid).toBe(false);
    expect(validateCameraProfile(42).valid).toBe(false);
  });

  it('rejects an empty name', () => {
    const res = validateCameraProfile({ ...good, name: '   ' });
    expect(res.valid).toBe(false);
    expect(res.errors.some((e) => e.toLowerCase().includes('name'))).toBe(true);
  });

  it('rejects non-positive or non-finite sensor / focal values', () => {
    expect(validateCameraProfile({ ...good, sensorWidth: 0 }).valid).toBe(false);
    expect(validateCameraProfile({ ...good, sensorHeight: -1 }).valid).toBe(false);
    expect(validateCameraProfile({ ...good, focalLength: Number.NaN }).valid).toBe(false);
    expect(validateCameraProfile({ ...good, focalLength: Infinity }).valid).toBe(false);
  });

  it('rejects non-integer pixel dimensions', () => {
    expect(validateCameraProfile({ ...good, imageWidth: 5472.5 }).valid).toBe(false);
    expect(validateCameraProfile({ ...good, imageHeight: 0 }).valid).toBe(false);
  });

  it('rejects out-of-range values', () => {
    expect(validateCameraProfile({ ...good, sensorWidth: 500 }).valid).toBe(false);
    expect(validateCameraProfile({ ...good, focalLength: 5000 }).valid).toBe(false);
    expect(validateCameraProfile({ ...good, imageWidth: 200000 }).valid).toBe(false);
  });

  it('collects multiple errors at once', () => {
    const res = validateCameraProfile({ name: '', sensorWidth: -1, imageWidth: 1.5 });
    expect(res.valid).toBe(false);
    expect(res.errors.length).toBeGreaterThan(1);
  });
});
