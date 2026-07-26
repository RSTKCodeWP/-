import { describe, it, expect } from 'vitest';
import { ContactCache } from './contact-cache';
import type { TrafficContact } from '../../shared/traffic-types';

function contact(p: Partial<TrafficContact> & { id: string; lastSeen: number }): TrafficContact {
  return { source: 'adsb', category: 'powered', lat: 0, lon: 0, ...p };
}

describe('ContactCache', () => {
  it('dedupes by id, keeping the newer report', () => {
    const c = new ContactCache();
    c.upsert([contact({ id: 'a', lastSeen: 100, lat: 1 })]);
    c.upsert([contact({ id: 'a', lastSeen: 200, lat: 2 })]);
    c.upsert([contact({ id: 'a', lastSeen: 150, lat: 9 })]); // stale, ignored
    const snap = c.snapshot(200);
    expect(snap).toHaveLength(1);
    expect(snap[0]!.lat).toBe(2);
  });

  it('expires contacts past their source TTL', () => {
    const c = new ContactCache();
    c.upsert([
      contact({ id: 'adsb1', source: 'adsb', lastSeen: 0 }),
      contact({ id: 'ogn1', source: 'ogn', lastSeen: 0 }),
    ]);
    // 30s later: ADS-B (15s TTL) gone, OGN (60s TTL) survives.
    const snap = c.snapshot(30_000);
    expect(snap.map((x) => x.id)).toEqual(['ogn1']);
    // 90s: both gone.
    expect(c.snapshot(90_000)).toHaveLength(0);
  });

  it('drops a whole source on demand', () => {
    const c = new ContactCache();
    c.upsert([
      contact({ id: 'a', source: 'adsb', lastSeen: 0 }),
      contact({ id: 'g', source: 'ogn', lastSeen: 0 }),
    ]);
    c.dropSource('adsb');
    expect(c.snapshot(0).map((x) => x.id)).toEqual(['g']);
  });
});
