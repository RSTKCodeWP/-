import { describe, it, expect } from 'vitest';
import {
  planTerrainSafeAltitudes,
  haversine,
  type PlannerWaypoint,
  type TerrainLookup,
} from './terrain-altitude-planner';

/**
 * Build a terrain lookup from a function. Lets tests describe terrain
 * analytically (e.g. "ridge at the midpoint between A and B").
 */
function terrain(fn: (lat: number, lon: number) => number): TerrainLookup {
  return { elevationAt: (lat, lon) => fn(lat, lon) };
}

describe('planTerrainSafeAltitudes - raise endpoints only', () => {
  const flatGround = terrain(() => 0);

  it('does nothing when raiseEndpoints is false', () => {
    const wps: PlannerWaypoint[] = [
      { seq: 0, latitude: 0, longitude: 0, altitude: 10 },
    ];
    const result = planTerrainSafeAltitudes(wps, terrain(() => 100), {
      safeBuffer: 30,
      raiseEndpoints: false,
      insertIntermediates: false,
    });
    expect(result.raisedAltitudes.size).toBe(0);
  });

  it('raises waypoint below terrain + buffer', () => {
    const wps: PlannerWaypoint[] = [
      { seq: 0, latitude: 0, longitude: 0, altitude: 20 },
    ];
    const result = planTerrainSafeAltitudes(wps, terrain(() => 100), {
      safeBuffer: 30,
      raiseEndpoints: true,
      insertIntermediates: false,
    });
    expect(result.raisedAltitudes.get(0)).toBe(130);
  });

  it('does not lower a waypoint that is already high', () => {
    const wps: PlannerWaypoint[] = [
      { seq: 0, latitude: 0, longitude: 0, altitude: 500 },
    ];
    const result = planTerrainSafeAltitudes(wps, flatGround, {
      safeBuffer: 30,
      raiseEndpoints: true,
      insertIntermediates: false,
    });
    expect(result.raisedAltitudes.has(0)).toBe(false);
  });
});

describe('planTerrainSafeAltitudes - intermediate insertion', () => {
  /**
   * Set up: two waypoints 1km apart, both at altitude 100m.
   * Ground is 0m at the endpoints, but a ridge rises to 200m at the midpoint.
   * Straight-line flight between them drops to 100m absolute at midpoint,
   * which is 100m BELOW the 200m ridge. Collision.
   */
  const ridgeTerrain = terrain((lat, _lon) => {
    // Ridge centered at lat=0.005 (midpoint of 0 → 0.01)
    const ridgeCenter = 0.005;
    const ridgeWidth = 0.002;
    const dist = Math.abs(lat - ridgeCenter);
    if (dist > ridgeWidth) return 0;
    return 200 * (1 - dist / ridgeWidth);
  });

  const endpointsWps: PlannerWaypoint[] = [
    { seq: 0, latitude: 0, longitude: 0, altitude: 100 },
    { seq: 1, latitude: 0.01, longitude: 0, altitude: 100 },
  ];

  it('inserts an intermediate waypoint when line clips terrain', () => {
    const result = planTerrainSafeAltitudes(endpointsWps, ridgeTerrain, {
      safeBuffer: 30,
      raiseEndpoints: true,
      insertIntermediates: true,
      sampleStepMeters: 20,
      minSpacingMeters: 50,
    });

    expect(result.inserts.length).toBeGreaterThan(0);

    // The first insert should be near the ridge peak (lat ~= 0.005)
    const peakInsert = result.inserts[0]!;
    expect(peakInsert.latitude).toBeCloseTo(0.005, 3);
    // Insert altitude must clear the 200m ridge + 30m buffer = 230m
    expect(peakInsert.altitude).toBeGreaterThanOrEqual(230);
    // afterSeq should be 0 (insert goes between seq 0 and seq 1)
    expect(peakInsert.afterSeq).toBe(0);
  });

  it('does not insert when line stays above terrain', () => {
    // Same ridge, but waypoints at 500m altitude — plenty of clearance
    const highWps: PlannerWaypoint[] = [
      { seq: 0, latitude: 0, longitude: 0, altitude: 500 },
      { seq: 1, latitude: 0.01, longitude: 0, altitude: 500 },
    ];
    const result = planTerrainSafeAltitudes(highWps, ridgeTerrain, {
      safeBuffer: 30,
      raiseEndpoints: true,
      insertIntermediates: true,
      sampleStepMeters: 20,
    });
    expect(result.inserts.length).toBe(0);
    expect(result.raisedAltitudes.size).toBe(0);
  });

  it('respects minSpacingMeters to avoid over-insertion', () => {
    // A long run with a wavy terrain that would produce many inserts
    const wavyTerrain = terrain((lat) => {
      return 150 + 100 * Math.sin(lat * 10000);
    });
    const wavyWps: PlannerWaypoint[] = [
      { seq: 0, latitude: 0, longitude: 0, altitude: 150 },
      { seq: 1, latitude: 0.02, longitude: 0, altitude: 150 },
    ];

    const tight = planTerrainSafeAltitudes(wavyWps, wavyTerrain, {
      safeBuffer: 30,
      raiseEndpoints: true,
      insertIntermediates: true,
      sampleStepMeters: 10,
      minSpacingMeters: 20,
    });
    const loose = planTerrainSafeAltitudes(wavyWps, wavyTerrain, {
      safeBuffer: 30,
      raiseEndpoints: true,
      insertIntermediates: true,
      sampleStepMeters: 10,
      minSpacingMeters: 400,
    });

    // Looser spacing => fewer or equal inserts
    expect(loose.inserts.length).toBeLessThanOrEqual(tight.inserts.length);
  });

  it('inserts carry afterSeq pointing to the preceding original waypoint', () => {
    const multiWps: PlannerWaypoint[] = [
      { seq: 0, latitude: 0, longitude: 0, altitude: 100 },
      { seq: 1, latitude: 0.01, longitude: 0, altitude: 100 }, // ridge between 0 and 1
      { seq: 2, latitude: 0.02, longitude: 0, altitude: 100 },
    ];
    const result = planTerrainSafeAltitudes(multiWps, ridgeTerrain, {
      safeBuffer: 30,
      raiseEndpoints: true,
      insertIntermediates: true,
      sampleStepMeters: 20,
    });

    // All inserts between the first pair should have afterSeq=0
    for (const ins of result.inserts) {
      // ridge is only between lat 0 and 0.01, so all inserts go after seq 0
      if (ins.latitude < 0.01) {
        expect(ins.afterSeq).toBe(0);
      }
    }
  });
});

describe('planTerrainSafeAltitudes - edge cases', () => {
  it('returns empty result for empty input', () => {
    const result = planTerrainSafeAltitudes([], terrain(() => 0), {
      safeBuffer: 30,
      raiseEndpoints: true,
      insertIntermediates: true,
    });
    expect(result.raisedAltitudes.size).toBe(0);
    expect(result.inserts.length).toBe(0);
  });

  it('returns empty inserts for a single waypoint', () => {
    const result = planTerrainSafeAltitudes(
      [{ seq: 0, latitude: 0, longitude: 0, altitude: 100 }],
      terrain(() => 0),
      { safeBuffer: 30, raiseEndpoints: true, insertIntermediates: true },
    );
    expect(result.inserts.length).toBe(0);
  });

  it('skips segments where terrain is unknown', () => {
    const unknownTerrain = terrain(() => NaN); // NaN signals unknown
    const lookup: TerrainLookup = {
      elevationAt: () => null,
    };
    const wps: PlannerWaypoint[] = [
      { seq: 0, latitude: 0, longitude: 0, altitude: 100 },
      { seq: 1, latitude: 0.01, longitude: 0, altitude: 100 },
    ];
    const result = planTerrainSafeAltitudes(wps, lookup, {
      safeBuffer: 30,
      raiseEndpoints: true,
      insertIntermediates: true,
    });
    expect(result.inserts.length).toBe(0);
    expect(result.raisedAltitudes.size).toBe(0);
    // suppress unused var lint
    void unknownTerrain;
  });
});

describe('planTerrainSafeAltitudes - altitude reference frames (issue #106)', () => {
  it('keeps a relative-frame waypoint in its own frame when raising (no ASL explosion)', () => {
    // Site is high: home at 1080m ASL, terrain under the waypoint at 1100m.
    // A 10m relative-to-home waypoint sits at 1090m ASL - only -10m over terrain.
    const wps: PlannerWaypoint[] = [
      { seq: 0, latitude: 0, longitude: 0, altitude: 10, frame: 'relative' },
    ];
    const result = planTerrainSafeAltitudes(wps, terrain(() => 1100), {
      safeBuffer: 30,
      raiseEndpoints: true,
      insertIntermediates: false,
      homeElevationMeters: 1080,
    });
    // Needs ASL >= 1100 + 30 = 1130 -> relative >= 1130 - 1080 = 50.
    // It must stay a small relative number, NOT jump to ~1130.
    expect(result.raisedAltitudes.get(0)).toBe(50);
  });

  it('does not raise a relative-frame waypoint that already clears terrain', () => {
    const wps: PlannerWaypoint[] = [
      { seq: 0, latitude: 0, longitude: 0, altitude: 60, frame: 'relative' },
    ];
    const result = planTerrainSafeAltitudes(wps, terrain(() => 1080), {
      safeBuffer: 30,
      raiseEndpoints: true,
      insertIntermediates: false,
      homeElevationMeters: 1080,
    });
    // 60m relative over flat 1080m ground = 60m AGL, already clears -> untouched.
    expect(result.raisedAltitudes.has(0)).toBe(false);
  });

  it('raises a terrain-frame waypoint to the buffer, independent of ground elevation', () => {
    const wps: PlannerWaypoint[] = [
      { seq: 0, latitude: 0, longitude: 0, altitude: 10, frame: 'terrain' },
    ];
    const result = planTerrainSafeAltitudes(wps, terrain(() => 500), {
      safeBuffer: 30,
      raiseEndpoints: true,
      insertIntermediates: false,
    });
    // terrain-frame altitude IS height-above-ground -> raise 10 to the 30 buffer.
    expect(result.raisedAltitudes.get(0)).toBe(30);
  });

  it('treats asl-frame waypoints as absolute (legacy behavior preserved)', () => {
    const wps: PlannerWaypoint[] = [
      { seq: 0, latitude: 0, longitude: 0, altitude: 20, frame: 'asl' },
    ];
    const result = planTerrainSafeAltitudes(wps, terrain(() => 100), {
      safeBuffer: 30,
      raiseEndpoints: true,
      insertIntermediates: false,
    });
    expect(result.raisedAltitudes.get(0)).toBe(130);
  });

  it('preserves the user-set height as terrain clearance for a relative waypoint over a hill', () => {
    // User asked for 100m relative-to-home. Home is 1000m ASL, an 80m hill
    // (1080m) sits under the waypoint. Auto-adjust must keep the drone 100m over
    // the terrain (its set height), i.e. 180m relative - not drop it to the buffer.
    const wps: PlannerWaypoint[] = [
      { seq: 0, latitude: 0, longitude: 0, altitude: 100, frame: 'relative' },
    ];
    const result = planTerrainSafeAltitudes(wps, terrain(() => 1080), {
      safeBuffer: 30,
      raiseEndpoints: true,
      insertIntermediates: false,
      homeElevationMeters: 1000,
    });
    expect(result.raisedAltitudes.get(0)).toBe(180);
  });

  it('inserts intermediate waypoints in the segment frame, not ASL (relative)', () => {
    // Home 1000m ASL. Two relative-100m waypoints 1km apart over 1000m ground,
    // with a 1200m ridge at the midpoint that the straight path clips.
    const ridge = terrain((lat) => (Math.abs(lat - 0.0045) < 0.002 ? 1200 : 1000));
    const wps: PlannerWaypoint[] = [
      { seq: 0, latitude: 0, longitude: 0, altitude: 100, frame: 'relative' },
      { seq: 1, latitude: 0.009, longitude: 0, altitude: 100, frame: 'relative' },
    ];
    const result = planTerrainSafeAltitudes(wps, ridge, {
      safeBuffer: 30,
      raiseEndpoints: true,
      insertIntermediates: true,
      homeElevationMeters: 1000,
    });
    expect(result.inserts.length).toBeGreaterThan(0);
    const ins = result.inserts[0]!;
    expect(ins.frame).toBe('relative');
    // ASL would be ~1230; relative-to-1000m-home must be ~230, never four digits.
    expect(ins.altitude).toBeGreaterThanOrEqual(230);
    expect(ins.altitude).toBeLessThan(400);
  });
});

describe('haversine', () => {
  it('returns 0 for identical points', () => {
    expect(haversine(0, 0, 0, 0)).toBe(0);
  });

  it('computes reasonable distances', () => {
    // 1 degree latitude ~= 111km
    const d = haversine(0, 0, 1, 0);
    expect(d).toBeGreaterThan(110000);
    expect(d).toBeLessThan(112000);
  });
});
