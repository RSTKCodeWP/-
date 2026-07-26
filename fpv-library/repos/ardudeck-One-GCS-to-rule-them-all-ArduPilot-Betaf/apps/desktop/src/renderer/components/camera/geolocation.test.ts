import { describe, it, expect } from 'vitest';
import { projectPixelToGround, projectFrameCenter, projectFootprint, type CameraPose } from './geolocation';

const base: CameraPose = {
  lat: 47.0,
  lon: 8.0,
  altMslM: 100,
  bearingDeg: 0,
  pitchDownDeg: 90, // straight down
  hfovDeg: 60,
  vfovDeg: 40,
};

describe('projectPixelToGround', () => {
  it('nadir frame-center lands directly under the vehicle', () => {
    const p = projectFrameCenter(base);
    expect(p).not.toBeNull();
    expect(p?.lat).toBeCloseTo(47.0, 5);
    expect(p?.lon).toBeCloseTo(8.0, 5);
    // Straight down: slant range == height.
    expect(p?.slantRangeM).toBeCloseTo(100, 3);
  });

  it('45° depression north projects the point north by ~height metres', () => {
    const pose: CameraPose = { ...base, pitchDownDeg: 45, bearingDeg: 0 };
    const p = projectFrameCenter(pose);
    expect(p).not.toBeNull();
    // groundDist = height / tan(45) = 100 m north. ~0.000898° lat.
    expect(p!.lat).toBeGreaterThan(47.0);
    expect(p!.lat).toBeCloseTo(47.0 + 100 / 6378137 / (Math.PI / 180), 6);
    expect(p!.lon).toBeCloseTo(8.0, 6);
  });

  it('east bearing moves longitude positive', () => {
    const pose: CameraPose = { ...base, pitchDownDeg: 45, bearingDeg: 90 };
    const p = projectFrameCenter(pose);
    expect(p!.lon).toBeGreaterThan(8.0);
    expect(p!.lat).toBeCloseTo(47.0, 6);
  });

  it('returns null when the ray points at or above the horizon', () => {
    const pose: CameraPose = { ...base, pitchDownDeg: 0 };
    expect(projectPixelToGround(pose, 0, 0)).toBeNull();
  });

  it('returns null when the vehicle is at or below ground', () => {
    const pose: CameraPose = { ...base, altMslM: 0 };
    expect(projectFrameCenter(pose, 0)).toBeNull();
  });

  it('terrain elevation reduces the height above ground', () => {
    const high = projectFrameCenter({ ...base, pitchDownDeg: 45 }, 0);
    const low = projectFrameCenter({ ...base, pitchDownDeg: 45 }, 50); // 50m terrain
    // Less height above ground -> closer target -> smaller northward offset.
    expect(low!.lat - 47.0).toBeLessThan(high!.lat - 47.0);
  });
});

describe('projectFootprint', () => {
  it('nadir footprint yields four ground corners around the vehicle', () => {
    const corners = projectFootprint(base);
    expect(corners).toHaveLength(4);
    // All corners near the vehicle for a downward-looking camera.
    for (const c of corners) {
      expect(Math.abs(c.lat - 47.0)).toBeLessThan(0.01);
      expect(Math.abs(c.lon - 8.0)).toBeLessThan(0.01);
    }
  });

  it('a steeply-forward camera drops the above-horizon corners', () => {
    // Boresight 10° down, vfov 40 -> top edge points 10° above horizon.
    const corners = projectFootprint({ ...base, pitchDownDeg: 10 });
    expect(corners.length).toBeLessThan(4);
  });
});
