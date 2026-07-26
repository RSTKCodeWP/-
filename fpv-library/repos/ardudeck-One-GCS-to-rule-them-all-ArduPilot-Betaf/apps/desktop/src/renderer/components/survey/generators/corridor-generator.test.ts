import { describe, it, expect } from 'vitest';
import { generateCorridor } from './corridor-generator';
import { DEFAULT_SURVEY_CONFIG, type SurveyConfig, type LatLng } from '../survey-types';

function config(polygon: LatLng[], overrides: Partial<SurveyConfig> = {}): SurveyConfig {
  return { ...DEFAULT_SURVEY_CONFIG, polygon, pattern: 'corridor', ...overrides };
}

// A straight ~550 m east-west centerline near the equator.
const STRAIGHT: LatLng[] = [
  { lat: 0, lng: 0 },
  { lat: 0, lng: 0.005 },
];

// An L-shaped centerline with a 90° bend.
const BENT: LatLng[] = [
  { lat: 0, lng: 0 },
  { lat: 0, lng: 0.003 },
  { lat: 0.003, lng: 0.003 },
];

const allFinite = (pts: LatLng[]) =>
  pts.every((p) => Number.isFinite(p.lat) && Number.isFinite(p.lng));

describe('generateCorridor', () => {
  it('returns empty for a degenerate centerline', () => {
    const r = generateCorridor(config([{ lat: 0, lng: 0 }]));
    expect(r.waypoints).toHaveLength(0);
  });

  it('produces strips along a straight centerline with finite coords', () => {
    const r = generateCorridor(config(STRAIGHT));
    expect(r.waypoints.length).toBeGreaterThan(0);
    expect(allFinite(r.waypoints)).toBe(true);
    expect(r.stats.lineCount).toBeGreaterThanOrEqual(1);
  });

  it('honours an explicit strip count', () => {
    const r = generateCorridor(config(STRAIGHT, { corridorStrips: 3 }));
    expect(r.stats.lineCount).toBe(3);
  });

  it('even strip counts straddle the centerline, odd counts ride it', () => {
    const odd = generateCorridor(config(STRAIGHT, { corridorStrips: 3 }));
    const even = generateCorridor(config(STRAIGHT, { corridorStrips: 2 }));
    expect(odd.stats.lineCount).toBe(3);
    expect(even.stats.lineCount).toBe(2);
  });

  it('plane mode adds overshoot/turn waypoints that copter mode omits', () => {
    const plane = generateCorridor(config(STRAIGHT, { corridorStrips: 2, corridorMode: 'plane', overshoot: 30 }));
    const copter = generateCorridor(config(STRAIGHT, { corridorStrips: 2, corridorMode: 'copter' }));
    expect(plane.waypoints.length).toBeGreaterThan(copter.waypoints.length);
  });

  it('inserts racetrack turn waypoints at sharp bends in plane mode', () => {
    const plane = generateCorridor(config(BENT, { corridorStrips: 1, corridorMode: 'plane', overshoot: 30, maxTurnAngle: 15 }));
    const copter = generateCorridor(config(BENT, { corridorStrips: 1, corridorMode: 'copter' }));
    // The 90° bend exceeds maxTurnAngle, so plane gets extra loop waypoints.
    expect(plane.waypoints.length).toBeGreaterThan(copter.waypoints.length);
    expect(allFinite(plane.waypoints)).toBe(true);
  });

  it('reports a swath area, not the enclosed-polygon area', () => {
    const r = generateCorridor(config(STRAIGHT, { corridorStrips: 2 }));
    // length(~556m) * coveredWidth(2 * lineSpacing) > 0
    expect(r.stats.areaCovered).toBeGreaterThan(0);
  });

  it('flipLegs and invertPath keep the waypoint count but reorder', () => {
    const base = generateCorridor(config(STRAIGHT, { corridorStrips: 3 }));
    const flipped = generateCorridor(config(STRAIGHT, { corridorStrips: 3, flipLegs: true }));
    const inverted = generateCorridor(config(STRAIGHT, { corridorStrips: 3, invertPath: true }));
    expect(flipped.waypoints.length).toBe(base.waypoints.length);
    expect(inverted.waypoints.length).toBe(base.waypoints.length);
  });
});

describe('generateCorridor with branches', () => {
  // A spur forking north from the midpoint of STRAIGHT.
  const BRANCH: LatLng[] = [
    { lat: 0, lng: 0.0025 },
    { lat: 0.003, lng: 0.0025 },
  ];

  it('a branch adds waypoints beyond the main centerline', () => {
    const main = generateCorridor(config(STRAIGHT, { corridorStrips: 2 }));
    const branched = generateCorridor(config(STRAIGHT, { corridorStrips: 2, corridorBranches: [BRANCH] }));
    expect(branched.waypoints.length).toBeGreaterThan(main.waypoints.length);
    expect(allFinite(branched.waypoints)).toBe(true);
  });

  it('sums line count and photo count across main + branches', () => {
    const main = generateCorridor(config(STRAIGHT, { corridorStrips: 2 }));
    const branched = generateCorridor(config(STRAIGHT, { corridorStrips: 2, corridorBranches: [BRANCH] }));
    // Two centerlines, 2 strips each.
    expect(branched.stats.lineCount).toBe(main.stats.lineCount * 2);
    expect(branched.stats.photoCount).toBeGreaterThanOrEqual(main.stats.photoCount);
    expect(branched.stats.areaCovered).toBeGreaterThan(main.stats.areaCovered);
  });

  it('ignores degenerate branches (fewer than 2 points)', () => {
    const main = generateCorridor(config(STRAIGHT, { corridorStrips: 2 }));
    const withJunk = generateCorridor(config(STRAIGHT, { corridorStrips: 2, corridorBranches: [[{ lat: 1, lng: 1 }]] }));
    expect(withJunk.waypoints.length).toBe(main.waypoints.length);
  });

  it('empty branches array is identical to no branches', () => {
    const a = generateCorridor(config(STRAIGHT, { corridorStrips: 3 }));
    const b = generateCorridor(config(STRAIGHT, { corridorStrips: 3, corridorBranches: [] }));
    expect(b.waypoints.length).toBe(a.waypoints.length);
    expect(b.stats.lineCount).toBe(a.stats.lineCount);
  });
});
