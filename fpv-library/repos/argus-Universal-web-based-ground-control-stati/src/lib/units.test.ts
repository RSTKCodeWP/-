import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  fmtAlt,
  fmtSpeed,
  fmtDist,
  fmtVs,
  setUnitSystem,
  getUnitSystem,
  loadUnitSystem,
  altUnit,
  speedUnit,
  distUnit,
  vsUnit,
} from './units';

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

describe('units — metric', () => {
  beforeEach(() => setUnitSystem('metric'));

  it('fmtAlt returns meters with one decimal', () => {
    expect(fmtAlt(100)).toBe('100.0');
    expect(fmtAlt(0)).toBe('0.0');
    expect(fmtAlt(12.345)).toBe('12.3');
  });

  it('fmtSpeed returns m/s with one decimal', () => {
    expect(fmtSpeed(15)).toBe('15.0');
    expect(fmtSpeed(0)).toBe('0.0');
  });

  it('fmtDist returns meters for short distances', () => {
    expect(fmtDist(500)).toBe('500 m');
    expect(fmtDist(999)).toBe('999 m');
  });

  it('fmtDist returns km for long distances', () => {
    expect(fmtDist(1500)).toBe('1.5 km');
    expect(fmtDist(10000)).toBe('10.0 km');
  });

  it('fmtVs returns m/s with one decimal', () => {
    expect(fmtVs(2.5)).toBe('2.5');
    expect(fmtVs(-1.2)).toBe('-1.2');
  });

  it('unit labels are metric', () => {
    expect(altUnit()).toBe('m');
    expect(speedUnit()).toBe('m/s');
    expect(distUnit()).toBe('km');
    expect(vsUnit()).toBe('m/s');
  });
});

describe('units — imperial', () => {
  beforeEach(() => setUnitSystem('imperial'));

  it('fmtAlt converts to feet', () => {
    // 100m * 3.28084 = 328 ft
    expect(fmtAlt(100)).toBe('328');
    expect(fmtAlt(0)).toBe('0');
  });

  it('fmtSpeed converts to mph', () => {
    // 10 m/s * 2.23694 = 22.4 mph
    expect(fmtSpeed(10)).toBe('22.4');
  });

  it('fmtDist returns feet for short distances', () => {
    // 100m = 328 ft, mi = 0.062 < 0.1 → feet
    expect(fmtDist(100)).toContain('ft');
  });

  it('fmtDist returns miles for long distances', () => {
    // 5000m = 3.1 mi
    expect(fmtDist(5000)).toContain('mi');
  });

  it('fmtVs converts to ft/min', () => {
    // 1 m/s * 196.85 = 197 ft/min
    expect(fmtVs(1)).toBe('197');
  });

  it('unit labels are imperial', () => {
    expect(altUnit()).toBe('ft');
    expect(speedUnit()).toBe('mph');
    expect(distUnit()).toBe('mi');
    expect(vsUnit()).toBe('ft/min');
  });
});

describe('units — negative and edge values', () => {
  beforeEach(() => setUnitSystem('metric'));

  it('fmtAlt handles negative altitude', () => {
    expect(fmtAlt(-5)).toBe('-5.0');
  });

  it('fmtSpeed handles very small speed', () => {
    expect(fmtSpeed(0.01)).toBe('0.0');
  });

  it('fmtDist at exact boundary 1000m', () => {
    expect(fmtDist(1000)).toBe('1.0 km');
  });

  it('fmtDist at 999.9m stays in meters', () => {
    expect(fmtDist(999.9)).toBe('1000 m');
  });

  it('fmtVs handles zero', () => {
    expect(fmtVs(0)).toBe('0.0');
  });

  it('fmtVs handles negative descent rate', () => {
    setUnitSystem('imperial');
    // -2 m/s * 196.85 = -394 ft/min
    expect(fmtVs(-2)).toBe('-394');
  });
});

describe('units — imperial distance boundary', () => {
  beforeEach(() => setUnitSystem('imperial'));

  it('fmtDist at boundary between feet and miles', () => {
    // 0.1 mi = 160.9m, so at 160m should be feet (0.099 mi < 0.1)
    const result = fmtDist(160);
    expect(result).toContain('ft');
    // At 165m, 0.103 mi >= 0.1 → miles
    const result2 = fmtDist(165);
    expect(result2).toContain('mi');
  });

  it('fmtDist at zero', () => {
    const result = fmtDist(0);
    expect(result).toContain('ft');
    expect(result).toBe('0 ft');
  });
});

describe('getUnitSystem / setUnitSystem', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', makeStorage());
  });

  it('getUnitSystem returns current system', () => {
    setUnitSystem('metric');
    expect(getUnitSystem()).toBe('metric');
    setUnitSystem('imperial');
    expect(getUnitSystem()).toBe('imperial');
  });

  it('setUnitSystem persists to localStorage', () => {
    setUnitSystem('imperial');
    expect(localStorage.getItem('argus_units')).toBe('imperial');
    setUnitSystem('metric');
    expect(localStorage.getItem('argus_units')).toBe('metric');
  });
});

describe('loadUnitSystem', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', makeStorage());
    setUnitSystem('metric');
  });

  it('loads imperial from localStorage', () => {
    localStorage.setItem('argus_units', 'imperial');
    loadUnitSystem();
    expect(getUnitSystem()).toBe('imperial');
  });

  it('stays metric when localStorage has no value', () => {
    loadUnitSystem();
    expect(getUnitSystem()).toBe('metric');
  });

  it('stays metric when localStorage has unknown value', () => {
    localStorage.setItem('argus_units', 'nautical');
    loadUnitSystem();
    expect(getUnitSystem()).toBe('metric');
  });
});
