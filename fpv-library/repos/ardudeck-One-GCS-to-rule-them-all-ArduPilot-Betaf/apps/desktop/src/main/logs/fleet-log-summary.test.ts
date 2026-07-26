import { describe, it, expect } from 'vitest';
import { extractFlightSummary, type LogLike, type HealthLike } from './fleet-log-summary';

function makeLog(over: Partial<LogLike> = {}): LogLike {
  return {
    metadata: { vehicleType: 'copter', firmwareVersion: '4.5.0', boardType: 'Pixhawk6C' },
    timeRange: { startUs: 0, endUs: 120_000_000 }, // 120 s
    messages: new Map(),
    ...over,
  };
}

describe('extractFlightSummary', () => {
  it('derives vehicle identity from board type + SYSID_THISMAV', () => {
    const messages = new Map<string, Array<{ fields: Record<string, number | string> }>>([
      ['PARM', [{ fields: { Name: 'SYSID_THISMAV', Value: 7 } }]],
    ]);
    const s = extractFlightSummary({
      log: makeLog({ messages }),
      health: [],
      path: '/logs/a.bin',
      fileName: 'a.bin',
      fileMtimeMs: 1_700_000_000_000,
      flightId: 'f1',
    });
    expect(s.sysid).toBe(7);
    expect(s.vehicleKey).toBe('Pixhawk6C#7');
    expect(s.vehicleLabel).toBe('copter sys7 (Pixhawk6C)');
    expect(s.durationSec).toBe(120);
  });

  it('computes max altitude, speed, distance, battery and vibration', () => {
    const messages = new Map<string, Array<{ fields: Record<string, number | string> }>>([
      ['GPS', [
        { fields: { Alt: 10, Spd: 5, Lat: 52.0, Lng: 13.0 } },
        { fields: { Alt: 95, Spd: 14, Lat: 52.001, Lng: 13.0 } },
      ]],
      ['BAT', [
        { fields: { Volt: 25.2, CurrTot: 100 } },
        { fields: { Volt: 22.1, CurrTot: 2500 } },
      ]],
      ['VIBE', [
        { fields: { VibeX: 12, VibeY: 18, VibeZ: 9 } },
        { fields: { VibeX: 40, VibeY: 10, VibeZ: 5 } },
      ]],
    ]);
    const s = extractFlightSummary({
      log: makeLog({ messages }),
      health: [],
      path: '/logs/b.bin',
      fileName: 'b.bin',
      fileMtimeMs: 0,
      flightId: 'f2',
    });
    expect(s.maxAltM).toBe(95);
    expect(s.maxGroundSpeedMps).toBe(14);
    expect(s.distanceM).toBeGreaterThan(100); // ~111 m for 0.001 deg lat
    expect(s.batteryMah).toBe(2500);
    expect(s.minBatteryV).toBe(22.1);
    expect(s.maxVibe).toBe(40);
  });

  it('falls back to file mtime when there is no GPS time', () => {
    const s = extractFlightSummary({
      log: makeLog(),
      health: [],
      path: '/logs/c.bin',
      fileName: 'c.bin',
      fileMtimeMs: 1_650_000_000_000,
      flightId: 'f3',
    });
    expect(s.startedAt).toBe(1_650_000_000_000);
    expect(s.sysid).toBeNull();
    expect(s.vehicleKey).toBe('Pixhawk6C#?');
  });

  it('passes through health flags compactly', () => {
    const health: HealthLike[] = [
      { id: 'gps', name: 'GPS', status: 'warn', summary: 'HDop high' },
      { id: 'vibration', name: 'Vibration', status: 'pass', summary: 'OK' },
    ];
    const s = extractFlightSummary({
      log: makeLog(),
      health,
      path: '/logs/d.bin',
      fileName: 'd.bin',
      fileMtimeMs: 0,
      flightId: 'f4',
    });
    expect(s.health).toEqual([
      { id: 'gps', name: 'GPS', status: 'warn', summary: 'HDop high' },
      { id: 'vibration', name: 'Vibration', status: 'pass', summary: 'OK' },
    ]);
  });
});
