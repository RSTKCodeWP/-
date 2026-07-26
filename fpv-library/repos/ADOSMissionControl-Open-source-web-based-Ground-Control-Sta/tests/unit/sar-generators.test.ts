import { describe, it, expect } from 'vitest';
import {
  generateExpandingSquare,
  generateSectorSearch,
  generateParallelTrack,
} from '@/lib/patterns/sar-generators';

describe('generateExpandingSquare', () => {
  it('generates expanding pattern with increasing leg lengths', () => {
    const result = generateExpandingSquare({
      center: [12.97, 77.59],
      legSpacing: 50,
      maxLegs: 8,
      altitude: 50,
      speed: 5,
      startBearing: 0,
    });
    // 1 start waypoint + 8 leg endpoints = 9 waypoints
    expect(result.waypoints).toHaveLength(9);
    expect(result.stats.totalDistance).toBeGreaterThan(0);
    expect(result.stats.estimatedTime).toBeGreaterThan(0);
  });

  it('starts at the center datum point', () => {
    const result = generateExpandingSquare({
      center: [12.97, 77.59],
      legSpacing: 50,
      maxLegs: 4,
      altitude: 50,
      speed: 5,
      startBearing: 0,
    });
    expect(result.waypoints[0].lat).toBeCloseTo(12.97, 5);
    expect(result.waypoints[0].lon).toBeCloseTo(77.59, 5);
  });
});

describe('generateSectorSearch', () => {
  it('generates sector pattern with correct number of sweeps', () => {
    const result = generateSectorSearch({
      center: [12.97, 77.59],
      radius: 200,
      sweeps: 3,
      altitude: 50,
      speed: 5,
      startBearing: 0,
    });
    // 1 start + 3 sweeps * 3 waypoints each (outbound, offset, return) = 10
    expect(result.waypoints).toHaveLength(10);
    expect(result.stats.totalDistance).toBeGreaterThan(0);
  });

  it('returns to datum after each sweep', () => {
    const result = generateSectorSearch({
      center: [12.97, 77.59],
      radius: 200,
      sweeps: 2,
      altitude: 50,
      speed: 5,
      startBearing: 0,
    });
    // The last waypoint of each sweep should be the center
    // Sweeps: WPs at index 3 and 6 should be back at center
    expect(result.waypoints[3].lat).toBeCloseTo(12.97, 4);
    expect(result.waypoints[3].lon).toBeCloseTo(77.59, 4);
  });
});

describe('generateParallelTrack', () => {
  it('generates parallel track lines', () => {
    const result = generateParallelTrack({
      startPoint: [12.97, 77.59],
      trackLength: 500,
      trackSpacing: 50,
      trackCount: 5,
      bearing: 0,
      altitude: 50,
      speed: 5,
    });
    // 5 tracks * 2 waypoints each = 10
    expect(result.waypoints).toHaveLength(10);
    expect(result.stats.totalDistance).toBeGreaterThan(0);
    expect(result.stats.estimatedTime).toBeGreaterThan(0);
  });

  it('alternates track direction (boustrophedon)', () => {
    const result = generateParallelTrack({
      startPoint: [12.97, 77.59],
      trackLength: 500,
      trackSpacing: 50,
      trackCount: 4,
      bearing: 0, // north
      altitude: 50,
      speed: 5,
    });
    // Track 0: goes north. Track 1: goes south (reversed).
    // Track 0 start should be south of track 0 end
    expect(result.waypoints[0].lat).toBeLessThan(result.waypoints[1].lat);
    // Track 1 start should be north of track 1 end (reversed)
    expect(result.waypoints[2].lat).toBeGreaterThan(result.waypoints[3].lat);
  });
});
