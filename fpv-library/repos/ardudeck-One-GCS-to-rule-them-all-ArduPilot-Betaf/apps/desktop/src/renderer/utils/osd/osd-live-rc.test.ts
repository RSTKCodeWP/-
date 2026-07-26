import { describe, it, expect } from 'vitest';
import { buildLiveRcRows, rssiPercent } from './osd-live-rc';

describe('buildLiveRcRows', () => {
  it('labels the first four channels AETR and the rest CH5+', () => {
    const rows = buildLiveRcRows({ channels: [1500, 1510, 1100, 1490, 1000, 2000], chancount: 6, rssi: 0 });
    expect(rows.map((r) => r.label)).toEqual(['Roll', 'Pitch', 'Thr', 'Yaw', 'CH5', 'CH6']);
    expect(rows.map((r) => r.value)).toEqual([1500, 1510, 1100, 1490, 1000, 2000]);
  });

  it('marks channel 3 as throttle', () => {
    const rows = buildLiveRcRows({ channels: [1500, 1500, 1200, 1500], chancount: 4, rssi: 0 });
    expect(rows.filter((r) => r.isThrottle)).toHaveLength(1);
    expect(rows[2]!.isThrottle).toBe(true);
  });

  it('honours chancount over the raw array length', () => {
    const rows = buildLiveRcRows({ channels: [1500, 1500, 1000, 1500, 0, 0, 0, 0], chancount: 4, rssi: 0 });
    expect(rows).toHaveLength(4);
  });

  it('falls back to the array length when chancount is zero', () => {
    const rows = buildLiveRcRows({ channels: [1500, 1500, 1000], chancount: 0, rssi: 0 });
    expect(rows).toHaveLength(3);
  });

  it('returns no rows when there is no RC data', () => {
    expect(buildLiveRcRows({ channels: [], chancount: 0, rssi: 0 })).toEqual([]);
  });
});

describe('rssiPercent', () => {
  it('scales 0..254 to 0..100', () => {
    expect(rssiPercent(0)).toBe(0);
    expect(rssiPercent(254)).toBe(100);
    expect(rssiPercent(127)).toBe(50);
  });

  it('returns null for the invalid/unknown sentinel 255', () => {
    expect(rssiPercent(255)).toBeNull();
  });
});
