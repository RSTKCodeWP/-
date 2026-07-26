import { describe, it, expect } from 'vitest';
import { generateCorridor } from '@/lib/patterns/corridor-generator';
import type { CorridorConfig } from '@/lib/patterns/types';

function makeConfig(overrides?: Partial<CorridorConfig>): CorridorConfig {
  return {
    pathPoints: [
      [12.970, 77.590],
      [12.980, 77.590],
    ],
    corridorWidth: 100,
    lineSpacing: 50,
    altitude: 50,
    speed: 5,
    ...overrides,
  };
}

// Simple haversine for checking distances
function distM(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371000;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

describe('generateCorridor', () => {
  it('generates perpendicular transects along a path', () => {
    const result = generateCorridor(makeConfig());
    expect(result.waypoints.length).toBeGreaterThan(0);
    expect(result.stats.transectCount).toBeGreaterThan(0);
    // Each transect produces 2 waypoints
    expect(result.waypoints.length).toBe(result.stats.transectCount * 2);
  });

  it('transect width matches corridor width', () => {
    const config = makeConfig({ corridorWidth: 200 });
    const result = generateCorridor(config);
    // Each transect is a pair of waypoints. Check their distance is close to corridorWidth.
    for (let i = 0; i < result.waypoints.length; i += 2) {
      const a = result.waypoints[i];
      const b = result.waypoints[i + 1];
      const d = distM(a.lat, a.lon, b.lat, b.lon);
      // Allow 10% tolerance due to geodetic approximations
      expect(d).toBeGreaterThan(200 * 0.85);
      expect(d).toBeLessThan(200 * 1.15);
    }
  });

  it('returns empty for single-point path', () => {
    const result = generateCorridor(makeConfig({
      pathPoints: [[12.97, 77.59]],
    }));
    expect(result.waypoints).toHaveLength(0);
  });
});
