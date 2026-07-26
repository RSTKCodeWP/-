import { describe, it, expect } from 'vitest';
import { classifyProximity, haversineMeters, bearingDeg } from './proximity';
import type { TrafficContact } from '../../../../shared/traffic-types';

function contact(p: Partial<TrafficContact>): TrafficContact {
  return { id: 'x', source: 'adsb', category: 'powered', lat: 0, lon: 0, lastSeen: 0, ...p };
}

const thresholds = { rangeMeters: 2000, verticalMeters: 300 };
const own = { lat: 45, lon: -75, altMeters: 1000 };

describe('haversineMeters / bearingDeg', () => {
  it('measures ~111km per degree of latitude', () => {
    expect(haversineMeters(0, 0, 1, 0)).toBeGreaterThan(110_000);
    expect(haversineMeters(0, 0, 1, 0)).toBeLessThan(112_000);
  });
  it('points north and east correctly', () => {
    expect(bearingDeg(0, 0, 1, 0)).toBeCloseTo(0, 0);
    expect(bearingDeg(0, 0, 0, 1)).toBeCloseTo(90, 0);
  });
});

describe('classifyProximity', () => {
  it('returns null without own position', () => {
    expect(classifyProximity(contact({}), null, thresholds)).toBeNull();
  });

  it('flags warning when inside both range and vertical', () => {
    const c = contact({ lat: 45.005, lon: -75, altMeters: 1100 }); // ~550m, 100m below
    const r = classifyProximity(c, own, thresholds)!;
    expect(r.tier).toBe('warning');
    expect(r.distanceMeters).toBeLessThan(2000);
  });

  it('drops to caution when within 2x but outside 1x vertical', () => {
    const c = contact({ lat: 45.005, lon: -75, altMeters: 1450 }); // close horizontally, 450m above
    expect(classifyProximity(c, own, thresholds)!.tier).toBe('caution');
  });

  it('is none when far away', () => {
    const c = contact({ lat: 45.1, lon: -75, altMeters: 1000 }); // ~11km
    expect(classifyProximity(c, own, thresholds)!.tier).toBe('none');
  });

  it('treats unknown contact altitude as co-altitude (fail safe)', () => {
    const c = contact({ lat: 45.005, lon: -75, altMeters: undefined });
    expect(classifyProximity(c, own, thresholds)!.tier).toBe('warning');
    expect(classifyProximity(c, own, thresholds)!.verticalMeters).toBeUndefined();
  });
});
