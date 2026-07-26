import { describe, it, expect, beforeEach, vi } from 'vitest';
import { saveFlightRecord, loadFlightRecords, deleteFlightRecord } from './flightDb';
import type { FlightRecord } from './flightDb';

/* ── localStorage mock ── */
function makeStorage(): Storage {
  const store = new Map<string, string>();
  return {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => {
      store.set(k, v);
    },
    removeItem: (k: string) => {
      store.delete(k);
    },
    clear: () => store.clear(),
    get length() {
      return store.size;
    },
    key: (i: number) => [...store.keys()][i] ?? null,
  };
}

beforeEach(() => {
  vi.stubGlobal('localStorage', makeStorage());
});

const SAMPLE: Omit<FlightRecord, 'id'> = {
  date: '2026-05-21',
  duration: 300,
  maxAlt: 100,
  maxSpeed: 15,
  totalDist: 5000,
  batUsed: 2400,
  vtype: 'copter',
  fw: '4.5.7',
  eventCount: 3,
};

describe('flightDb', () => {
  it('starts with an empty record list', () => {
    expect(loadFlightRecords()).toEqual([]);
  });

  it('saves and loads a flight record with auto-incrementing id', () => {
    saveFlightRecord(SAMPLE);
    const records = loadFlightRecords();
    expect(records.length).toBe(1);
    expect(records[0].id).toBe(1);
    expect(records[0].date).toBe('2026-05-21');
    expect(records[0].duration).toBe(300);
  });

  it('assigns incrementing ids across multiple saves', () => {
    saveFlightRecord(SAMPLE);
    saveFlightRecord({ ...SAMPLE, date: '2026-05-22' });
    const records = loadFlightRecords();
    expect(records.length).toBe(2);
    expect(records[0].id).toBe(1);
    expect(records[1].id).toBe(2);
  });

  it('deletes a record by id', () => {
    saveFlightRecord(SAMPLE);
    saveFlightRecord({ ...SAMPLE, date: '2026-05-22' });
    const before = loadFlightRecords();
    deleteFlightRecord(before[0].id);
    const after = loadFlightRecords();
    expect(after.length).toBe(1);
    expect(after[0].date).toBe('2026-05-22');
  });

  it('caps records at 200 entries, dropping oldest', () => {
    for (let i = 0; i < 205; i++) {
      saveFlightRecord({ ...SAMPLE, date: `2026-01-${String(i + 1).padStart(3, '0')}` });
    }
    const records = loadFlightRecords();
    expect(records.length).toBe(200);
    // The first 5 should have been pruned — earliest remaining should be day 006
    expect(records[0].date).toBe('2026-01-006');
  });

  it('preserves all fields through save/load cycle', () => {
    const full: Omit<FlightRecord, 'id'> = {
      date: '2026-03-15',
      duration: 1200,
      maxAlt: 250,
      maxSpeed: 30,
      totalDist: 15000,
      batUsed: 5000,
      vtype: 'plane',
      fw: '4.6.0-dev',
      eventCount: 12,
    };
    saveFlightRecord(full);
    const loaded = loadFlightRecords()[0];
    expect(loaded.date).toBe('2026-03-15');
    expect(loaded.duration).toBe(1200);
    expect(loaded.maxAlt).toBe(250);
    expect(loaded.maxSpeed).toBe(30);
    expect(loaded.totalDist).toBe(15000);
    expect(loaded.batUsed).toBe(5000);
    expect(loaded.vtype).toBe('plane');
    expect(loaded.fw).toBe('4.6.0-dev');
    expect(loaded.eventCount).toBe(12);
  });

  it('delete non-existent id does not affect records', () => {
    saveFlightRecord(SAMPLE);
    deleteFlightRecord(9999);
    expect(loadFlightRecords().length).toBe(1);
  });

  it('handles corrupted localStorage gracefully', () => {
    localStorage.setItem('argus_flights', 'not-valid-json{{{');
    expect(loadFlightRecords()).toEqual([]);
  });

  it('handles non-array JSON in localStorage — returns empty array', () => {
    localStorage.setItem('argus_flights', '{"not": "an array"}');
    expect(loadFlightRecords()).toEqual([]);
  });

  it('saveFlightRecord does not crash when localStorage has non-array JSON', () => {
    localStorage.setItem('argus_flights', '"just a string"');
    expect(() => saveFlightRecord(SAMPLE)).not.toThrow();
    const records = loadFlightRecords();
    expect(records.length).toBe(1);
  });

  it('id auto-increments from max existing id', () => {
    saveFlightRecord(SAMPLE);
    saveFlightRecord(SAMPLE);
    // Delete id=1, then add another — should get id=3 (max of existing is 2)
    deleteFlightRecord(1);
    saveFlightRecord({ ...SAMPLE, date: '2026-06-01' });
    const records = loadFlightRecords();
    const ids = records.map((r) => r.id);
    expect(ids).toContain(2);
    expect(ids).toContain(3);
    expect(ids).not.toContain(1);
  });
});
