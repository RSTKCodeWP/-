import { describe, it, expect } from 'vitest';
import {
  calculateGSD,
  calculateAltitudeForGSD,
  estimateBatteryCount,
  estimateDataSizeGb,
} from './survey-stats';

// DJI Mavic 3E mapping payload (the default camera).
const CAM = { sensorWidth: 17.3, focalLength: 12.3, imageWidth: 5280 };

describe('GSD <-> altitude round-trip', () => {
  it('calculateAltitudeForGSD inverts calculateGSD', () => {
    const altitude = 80;
    const gsd = calculateGSD(CAM.sensorWidth, CAM.focalLength, CAM.imageWidth, altitude);
    const back = calculateAltitudeForGSD(CAM.sensorWidth, CAM.focalLength, CAM.imageWidth, gsd);
    expect(back).toBeCloseTo(altitude, 6);
  });

  it('higher target GSD means higher altitude', () => {
    const low = calculateAltitudeForGSD(CAM.sensorWidth, CAM.focalLength, CAM.imageWidth, 1);
    const high = calculateAltitudeForGSD(CAM.sensorWidth, CAM.focalLength, CAM.imageWidth, 3);
    expect(high).toBeGreaterThan(low);
  });

  it('returns 0 for an invalid sensor width', () => {
    expect(calculateAltitudeForGSD(0, CAM.focalLength, CAM.imageWidth, 2)).toBe(0);
  });
});

describe('estimateBatteryCount', () => {
  it('rounds up partial batteries', () => {
    // 25 min of flight on 20-min batteries needs 2.
    expect(estimateBatteryCount(25 * 60, 20)).toBe(2);
  });

  it('is 1 when the flight fits one battery', () => {
    expect(estimateBatteryCount(15 * 60, 20)).toBe(1);
  });

  it('returns 0 for unusable inputs', () => {
    expect(estimateBatteryCount(0, 20)).toBe(0);
    expect(estimateBatteryCount(600, 0)).toBe(0);
  });
});

describe('estimateDataSizeGb', () => {
  it('scales with photo count and resolution', () => {
    const small = estimateDataSizeGb(100, 4000, 3000);
    const big = estimateDataSizeGb(200, 4000, 3000);
    expect(big).toBeCloseTo(small * 2, 6);
  });

  it('is zero with no photos', () => {
    expect(estimateDataSizeGb(0, 5280, 3956)).toBe(0);
  });
});
