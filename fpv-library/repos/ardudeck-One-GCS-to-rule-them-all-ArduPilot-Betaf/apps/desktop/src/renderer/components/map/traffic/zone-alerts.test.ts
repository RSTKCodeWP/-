import { describe, it, expect } from 'vitest';
import { pointInPolygon, contactInZone, evaluateZones, intrusionKey } from './zone-alerts';
import type { AlertZone, TrafficContact } from '../../../../shared/traffic-types';

function contact(over: Partial<TrafficContact>): TrafficContact {
  return { id: 'c1', source: 'remoteid', category: 'uav', lat: 0, lon: 0, lastSeen: 0, ...over };
}

describe('pointInPolygon', () => {
  const square = [
    { lat: 0, lon: 0 },
    { lat: 0, lon: 1 },
    { lat: 1, lon: 1 },
    { lat: 1, lon: 0 },
  ];
  it('detects an interior point', () => {
    expect(pointInPolygon(0.5, 0.5, square)).toBe(true);
  });
  it('rejects an exterior point', () => {
    expect(pointInPolygon(2, 2, square)).toBe(false);
  });
});

describe('contactInZone', () => {
  const circle: AlertZone = {
    id: 'z1', name: 'Pad', enabled: true, shape: 'circle',
    center: { lat: 52.0, lon: 13.0 }, radiusMeters: 1000,
  };

  it('flags a contact inside the circle', () => {
    // ~300 m north of centre (0.0027 deg lat).
    expect(contactInZone(contact({ lat: 52.0027, lon: 13.0 }), circle)).toBe(true);
  });

  it('rejects a contact outside the radius', () => {
    // ~3 km north.
    expect(contactInZone(contact({ lat: 52.027, lon: 13.0 }), circle)).toBe(false);
  });

  it('respects the altitude gate', () => {
    const gated: AlertZone = { ...circle, maxAltMeters: 120 };
    expect(contactInZone(contact({ lat: 52.0, lon: 13.0, altMeters: 80 }), gated)).toBe(true);
    expect(contactInZone(contact({ lat: 52.0, lon: 13.0, altMeters: 400 }), gated)).toBe(false);
  });

  it('ignores a disabled zone', () => {
    expect(contactInZone(contact({ lat: 52.0, lon: 13.0 }), { ...circle, enabled: false })).toBe(false);
  });
});

describe('evaluateZones', () => {
  it('reports intrusions per zone and a flat current set', () => {
    const zone: AlertZone = {
      id: 'z1', name: 'Pad', enabled: true, shape: 'circle',
      center: { lat: 0, lon: 0 }, radiusMeters: 1000,
    };
    const inside = contact({ id: 'in', lat: 0.001, lon: 0 });
    const outside = contact({ id: 'out', lat: 1, lon: 1 });
    const { current, byZone } = evaluateZones([inside, outside], [zone]);
    expect(current.has(intrusionKey('z1', 'in'))).toBe(true);
    expect(current.has(intrusionKey('z1', 'out'))).toBe(false);
    expect(byZone.get('z1')?.has('in')).toBe(true);
  });
});
