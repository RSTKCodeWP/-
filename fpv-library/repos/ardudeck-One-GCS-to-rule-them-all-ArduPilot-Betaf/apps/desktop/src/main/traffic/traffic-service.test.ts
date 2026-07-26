import { describe, it, expect } from 'vitest';
import { TrafficService, type TrafficServiceDeps } from './traffic-service';
import { withinViewport } from './provider';
import { DEFAULT_TRAFFIC_CONFIG, type TrafficBatch, type TrafficContact } from '../../shared/traffic-types';

function contact(id: string, lat: number, lon: number): TrafficContact {
  return { id, source: 'adsb', category: 'powered', lat, lon, lastSeen: Date.now() };
}

function makeService(over: Partial<TrafficServiceDeps> = {}) {
  const pushed: TrafficBatch[] = [];
  // All providers disabled by default -> enabling a source spawns no network I/O.
  const config = structuredClone(DEFAULT_TRAFFIC_CONFIG);
  const deps: TrafficServiceDeps = {
    getConfig: () => config,
    saveConfig: (c) => Object.assign(config, c),
    getSecret: () => null,
    push: (b) => pushed.push(b),
    ...over,
  };
  return { service: new TrafficService(deps), pushed, config };
}

describe('TrafficService', () => {
  it('pushes a clearing empty batch when the last source turns off', () => {
    const { service, pushed } = makeService();
    service.setEnabled('adsb', true);
    expect(pushed).toHaveLength(0); // nothing cleared yet
    service.setEnabled('adsb', false);
    expect(pushed).toHaveLength(1);
    expect(pushed[0]!.contacts).toEqual([]);
  });

  it('ignores redundant enable toggles', () => {
    const { service, pushed } = makeService();
    service.setEnabled('ogn', false); // already off
    expect(pushed).toHaveLength(0);
  });

  it('does not push while no source is active', () => {
    const { service, pushed } = makeService();
    service.start();
    // pushSnapshot is a no-op with no active sources
    service['pushSnapshot']();
    expect(pushed).toHaveLength(0);
    service.dispose();
  });

  it('culls contacts outside the reported viewport before pushing', () => {
    const { service, pushed } = makeService();
    // Drive internals directly so no real providers/network spin up.
    service['activeSources'].add('adsb');
    service['viewport'] = { lat: 50, lon: 8, radiusKm: 50 };
    service['cache'].upsert([
      contact('near', 50.1, 8.1), // ~13 km from centre -> kept
      contact('far', 53, 8), // ~330 km away -> culled
    ]);
    service['pushSnapshot']();
    expect(pushed).toHaveLength(1);
    expect(pushed[0]!.contacts.map((c) => c.id)).toEqual(['near']);
  });
});

describe('withinViewport', () => {
  const v = { lat: 50, lon: 8, radiusKm: 50 };
  it('keeps points inside the radius (plus margin)', () => {
    expect(withinViewport(50.1, 8.1, v)).toBe(true);
  });
  it('rejects points well outside the radius', () => {
    expect(withinViewport(53, 8, v)).toBe(false);
  });
});
