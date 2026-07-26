import { describe, it, expect } from 'vitest';
import { createRemoteIdProvider, parseRemoteId } from './remoteid-provider';

describe('createRemoteIdProvider', () => {
  it('builds a poll provider for the remoteid source', () => {
    const p = createRemoteIdProvider({ enabled: true, url: 'http://x/api', shape: 'ardudeck', pollMs: 1000 });
    expect(p.source).toBe('remoteid');
    expect(p.id).toBe('remoteid');
  });
});

describe('parseRemoteId', () => {
  it('parses the normalized ardudeck array shape', () => {
    const json = [
      { id: 'DRONE-1', lat: 52.1, lon: 13.2, alt: 90, track: 270, speed: 12, operatorLat: 52.0, operatorLon: 13.0 },
    ];
    const out = parseRemoteId(json, 'ardudeck', 1000);
    expect(out).toHaveLength(1);
    const c = out[0]!;
    expect(c.source).toBe('remoteid');
    expect(c.category).toBe('uav');
    expect(c.uasId).toBe('DRONE-1');
    expect(c.lat).toBeCloseTo(52.1);
    expect(c.altMeters).toBe(90);
    expect(c.trackDeg).toBe(270);
    expect(c.operatorLat).toBe(52.0);
    expect(c.lastSeen).toBe(1000);
  });

  it('unwraps an envelope and skips records without a position', () => {
    const json = { contacts: [{ id: 'A', lat: 1, lon: 2 }, { id: 'B' /* no pos */ }] };
    const out = parseRemoteId(json, 'ardudeck', 0);
    expect(out.map((c) => c.id)).toEqual(['A']);
  });

  it('flattens the OpenDroneID Basic ID + Location blocks', () => {
    const json = [
      {
        'Basic ID Message': { 'UAS ID': 'SERIAL-42' },
        'Location/Vector Message': { Latitude: 48.5, Longitude: 2.3, 'Geodetic Altitude': 150, Direction: 90 },
      },
    ];
    const out = parseRemoteId(json, 'opendroneid', 5);
    expect(out).toHaveLength(1);
    const c = out[0]!;
    expect(c.uasId).toBe('SERIAL-42');
    expect(c.lat).toBeCloseTo(48.5);
    expect(c.lon).toBeCloseTo(2.3);
    expect(c.altMeters).toBe(150);
    expect(c.trackDeg).toBe(90);
  });

  it('rejects out-of-range coordinates', () => {
    const out = parseRemoteId([{ id: 'X', lat: 999, lon: 0 }], 'ardudeck', 0);
    expect(out).toHaveLength(0);
  });
});
