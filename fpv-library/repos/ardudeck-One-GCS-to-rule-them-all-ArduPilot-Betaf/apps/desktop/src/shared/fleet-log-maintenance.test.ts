import { describe, it, expect } from 'vitest';
import { deriveMaintenanceFlags } from './fleet-log-maintenance';
import type { FlightSummary, VehicleFlightHistory } from './fleet-log-types';

function flight(over: Partial<FlightSummary>): FlightSummary {
  return {
    flightId: Math.random().toString(36).slice(2),
    vehicleKey: 'BoardX#1',
    vehicleLabel: 'copter sys1 (BoardX)',
    boardType: 'BoardX',
    vehicleType: 'copter',
    firmwareVersion: '4.5.0',
    sysid: 1,
    fileName: 'f.bin',
    path: `/logs/${Math.random()}.bin`,
    startedAt: 0,
    durationSec: 600,
    maxAltM: 100,
    maxGroundSpeedMps: 12,
    distanceM: 1000,
    batteryMah: 3000,
    minBatteryV: 22,
    maxVibe: 15,
    health: [],
    ...over,
  };
}

function history(flights: FlightSummary[]): VehicleFlightHistory {
  return { vehicleKey: 'BoardX#1', vehicleLabel: 'copter sys1 (BoardX)', flights };
}

describe('deriveMaintenanceFlags', () => {
  it('returns nothing for a healthy, stable history', () => {
    const flights = Array.from({ length: 6 }, () => flight({ maxVibe: 15, minBatteryV: 22 }));
    expect(deriveMaintenanceFlags(history(flights))).toEqual([]);
  });

  it('flags rising vibration (recent 3 vs prior 3)', () => {
    // newest first: recent high, older low.
    const flights = [
      flight({ maxVibe: 55 }), flight({ maxVibe: 50 }), flight({ maxVibe: 52 }),
      flight({ maxVibe: 20 }), flight({ maxVibe: 22 }), flight({ maxVibe: 18 }),
    ];
    const flags = deriveMaintenanceFlags(history(flights));
    expect(flags.some((f) => f.title === 'Vibration trending up')).toBe(true);
  });

  it('flags a recurring GPS issue across recent flights', () => {
    const bad = { health: [{ id: 'gps', name: 'GPS', status: 'fail' as const, summary: 'no fix' }] };
    const flights = [flight(bad), flight(bad), flight(bad), flight({}), flight({})];
    const flags = deriveMaintenanceFlags(history(flights));
    const gps = flags.find((f) => f.title === 'Recurring GPS issue');
    expect(gps).toBeDefined();
    expect(gps?.severity).toBe('fail');
  });

  it('flags increasing battery sag', () => {
    // newest first: recent low voltage, older high.
    const flights = [
      flight({ minBatteryV: 21.0 }), flight({ minBatteryV: 21.1 }),
      flight({ minBatteryV: 22.0 }), flight({ minBatteryV: 22.2 }),
    ];
    const flags = deriveMaintenanceFlags(history(flights));
    expect(flags.some((f) => f.title === 'Battery sag increasing')).toBe(true);
  });
});
