import { describe, it, expect } from 'vitest';
import { altitudeRelevance, relevanceStyle, isAltitudeRelevant } from './contact-style';
import type { TrafficContact } from '../../../../shared/traffic-types';

const band = { floorMeters: 0, ceilingMeters: 1500 };

function ac(over: Partial<TrafficContact>): TrafficContact {
  return { id: 'x', source: 'adsb', category: 'powered', lat: 0, lon: 0, lastSeen: 0, ...over };
}

describe('altitudeRelevance', () => {
  it('is full inside the band', () => {
    expect(altitudeRelevance(0, band)).toBe(1);
    expect(altitudeRelevance(800, band)).toBe(1);
    expect(altitudeRelevance(1500, band)).toBe(1);
  });

  it('falls off above the ceiling and clamps to a minimum', () => {
    expect(altitudeRelevance(2500, band)).toBeCloseTo(0.75, 2); // 1000m over
    expect(altitudeRelevance(20000, band)).toBe(0.25); // jet at FL400 -> tiny
  });

  it('falls off below the floor', () => {
    expect(altitudeRelevance(-2000, { floorMeters: 0, ceilingMeters: 1500 })).toBeCloseTo(0.5, 2);
  });

  it('treats unknown altitude as relevant', () => {
    expect(altitudeRelevance(undefined, band)).toBe(1);
  });
});

describe('isAltitudeRelevant', () => {
  const flying = { floorMeters: 50, ceilingMeters: 1000 };

  it('hides ground vehicles when a positive floor is set', () => {
    expect(isAltitudeRelevant(ac({ onGround: true }), flying)).toBe(false);
    expect(isAltitudeRelevant(ac({ onGround: true, altMeters: 0 }), flying)).toBe(false);
  });

  it('keeps ground vehicles when the floor is zero (default)', () => {
    expect(isAltitudeRelevant(ac({ onGround: true }), band)).toBe(true);
  });

  it('hard-culls anything below the floor', () => {
    expect(isAltitudeRelevant(ac({ altMeters: 30 }), flying)).toBe(false);
    expect(isAltitudeRelevant(ac({ altMeters: 60 }), flying)).toBe(true);
  });

  it('soft-culls far above the ceiling but keeps near-band', () => {
    expect(isAltitudeRelevant(ac({ altMeters: 2000 }), flying)).toBe(true); // 1000m over -> faded, kept
    expect(isAltitudeRelevant(ac({ altMeters: 12000 }), flying)).toBe(false); // airliner -> gone
  });

  it('hard-cuts everything above the ceiling when hardCeiling is set', () => {
    const hard = { ...flying, hardCeiling: true };
    expect(isAltitudeRelevant(ac({ altMeters: 1001 }), hard)).toBe(false); // just over -> hidden
    expect(isAltitudeRelevant(ac({ altMeters: 1000 }), hard)).toBe(true); // at ceiling -> kept
  });

  it('keeps unknown-altitude contacts (fail safe)', () => {
    expect(isAltitudeRelevant(ac({ altMeters: undefined }), flying)).toBe(true);
  });
});

describe('relevanceStyle', () => {
  it('maps relevance to a larger/brighter icon when relevant', () => {
    const near = relevanceStyle(1);
    const far = relevanceStyle(0.25);
    expect(near.scale).toBeGreaterThan(far.scale);
    expect(near.opacity).toBeGreaterThan(far.opacity);
    expect(far.opacity).toBeGreaterThanOrEqual(0.4);
  });
});
