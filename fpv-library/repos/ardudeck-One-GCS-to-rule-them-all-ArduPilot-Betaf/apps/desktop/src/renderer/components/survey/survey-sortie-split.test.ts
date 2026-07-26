import { describe, it, expect } from 'vitest';
import { splitIntoSorties } from './survey-sortie-split';
import type { LatLng } from './survey-types';

// A line of points spaced ~111 m apart in latitude (0.001 deg).
function line(n: number): LatLng[] {
  return Array.from({ length: n }, (_, i) => ({ lat: i * 0.001, lng: 0 }));
}

describe('splitIntoSorties', () => {
  it('returns [] for no waypoints', () => {
    expect(splitIntoSorties([], 5, 20)).toEqual([]);
  });

  it('keeps a short survey as a single sortie', () => {
    const wps = line(5); // ~444 m, trivial time
    const sorties = splitIntoSorties(wps, 5, 20);
    expect(sorties).toHaveLength(1);
    expect(sorties[0]).toHaveLength(5);
  });

  it('splits when flight time exceeds endurance', () => {
    // 100 points * ~111 m = ~11.1 km. At 5 m/s that is ~37 min. With a 10-min
    // battery that needs at least 3 sorties.
    const wps = line(100);
    const sorties = splitIntoSorties(wps, 5, 10);
    expect(sorties.length).toBeGreaterThanOrEqual(3);
    // No waypoint is lost and order is preserved (contiguous slices).
    expect(sorties.flat()).toHaveLength(100);
    expect(sorties.flat().map((p) => p.lat)).toEqual(wps.map((p) => p.lat));
  });

  it('respects a maxWaypoints cap', () => {
    const wps = line(50);
    const sorties = splitIntoSorties(wps, 50, 999, { maxWaypoints: 10 });
    expect(sorties.every((s) => s.length <= 10)).toBe(true);
    expect(sorties.flat()).toHaveLength(50);
  });

  it('never orphans a lone waypoint on an over-budget leg', () => {
    const wps = line(4);
    const sorties = splitIntoSorties(wps, 1, 0.0001); // absurdly tiny budget
    // Each sortie still has at least 2 points where possible (no singletons mid-list).
    for (let i = 0; i < sorties.length - 1; i++) {
      expect(sorties[i]!.length).toBeGreaterThanOrEqual(2);
    }
  });
});
