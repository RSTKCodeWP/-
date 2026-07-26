import { describe, it, expect, vi, beforeEach } from 'vitest';
import { app, loadDownloadedMission, addWaypoint } from './stores.svelte';
import type { Waypoint } from './types';

// --- Helpers ---

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
  vi.stubGlobal('requestAnimationFrame', (cb: () => void) => cb());
  app.waypoints = [];
  app.undoStack = [];
});

// ============================================================
// KML Generation from Waypoints
// ============================================================

describe('KML generation from waypoints', () => {
  function generateKml(waypoints: Waypoint[]): string {
    const coords = waypoints.map((w) => `${w.lon},${w.lat},${w.alt}`).join('\n');
    return `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Argus Mission</name>
<Placemark><name>Route</name><LineString><coordinates>${coords}</coordinates></LineString></Placemark>
</Document></kml>`;
  }

  it('generates valid XML structure', () => {
    const wps: Waypoint[] = [
      { lat: 30, lon: 120, alt: 50, drop: false, delay: 0, speed: 0, type: 'wp', loiter_param: 0 },
    ];
    const kml = generateKml(wps);
    expect(kml).toContain('<?xml version="1.0"');
    expect(kml).toContain('<kml xmlns="http://www.opengis.net/kml/2.2"');
    expect(kml).toContain('</kml>');
  });

  it('contains coordinates in lon,lat,alt order', () => {
    const wps: Waypoint[] = [
      { lat: 30.5, lon: 120.3, alt: 75, drop: false, delay: 0, speed: 0, type: 'wp', loiter_param: 0 },
    ];
    const kml = generateKml(wps);
    expect(kml).toContain('120.3,30.5,75');
  });

  it('generates multi-point coordinates separated by newlines', () => {
    const wps: Waypoint[] = [
      { lat: 30, lon: 120, alt: 50, drop: false, delay: 0, speed: 0, type: 'wp', loiter_param: 0 },
      { lat: 31, lon: 121, alt: 60, drop: false, delay: 0, speed: 0, type: 'wp', loiter_param: 0 },
      { lat: 32, lon: 122, alt: 70, drop: false, delay: 0, speed: 0, type: 'wp', loiter_param: 0 },
    ];
    const kml = generateKml(wps);
    expect(kml).toContain('120,30,50\n121,31,60\n122,32,70');
  });

  it('produces empty coordinates for empty waypoint list', () => {
    const kml = generateKml([]);
    expect(kml).toContain('<coordinates></coordinates>');
  });
});

// ============================================================
// Mission JSON Serialization / Deserialization
// ============================================================

describe('Mission JSON serialization', () => {
  function serializeMission(waypoints: Waypoint[], alt: number): string {
    return JSON.stringify({ waypoints, alt }, null, 2);
  }

  function deserializeMission(text: string): { waypoints: Waypoint[]; alt?: number } {
    return JSON.parse(text);
  }

  it('serializes waypoints with all fields', () => {
    const wps: Waypoint[] = [
      { lat: 30, lon: 120, alt: 50, drop: true, delay: 5, speed: 3, type: 'spline', loiter_param: 2 },
    ];
    const json = serializeMission(wps, 50);
    const parsed = deserializeMission(json);
    expect(parsed.waypoints[0].lat).toBe(30);
    expect(parsed.waypoints[0].lon).toBe(120);
    expect(parsed.waypoints[0].alt).toBe(50);
    expect(parsed.waypoints[0].drop).toBe(true);
    expect(parsed.waypoints[0].delay).toBe(5);
    expect(parsed.waypoints[0].speed).toBe(3);
    expect(parsed.waypoints[0].type).toBe('spline');
    expect(parsed.waypoints[0].loiter_param).toBe(2);
  });

  it('includes default alt in export', () => {
    const json = serializeMission([], 100);
    const parsed = deserializeMission(json);
    expect(parsed.alt).toBe(100);
  });

  it('roundtrips multiple waypoints correctly', () => {
    const wps: Waypoint[] = [
      { lat: 30, lon: 120, alt: 50, drop: false, delay: 0, speed: 0, type: 'wp', loiter_param: 0 },
      { lat: 31, lon: 121, alt: 60, drop: false, delay: 0, speed: 0, type: 'wp', loiter_param: 0 },
      { lat: 32, lon: 122, alt: 70, drop: true, delay: 3, speed: 5, type: 'loiter_turns', loiter_param: 4 },
    ];
    const json = serializeMission(wps, 50);
    const parsed = deserializeMission(json);
    expect(parsed.waypoints.length).toBe(3);
    expect(parsed.waypoints[2].type).toBe('loiter_turns');
    expect(parsed.waypoints[2].loiter_param).toBe(4);
  });
});

// ============================================================
// loadDownloadedMission Behavior
// ============================================================

describe('loadDownloadedMission handles various input formats', () => {
  it('loads waypoints with all fields', () => {
    const wps: Waypoint[] = [
      { lat: 30, lon: 120, alt: 50, drop: true, delay: 5, speed: 3, type: 'spline', loiter_param: 2 },
    ];
    loadDownloadedMission(wps);
    expect(app.waypoints.length).toBe(1);
    expect(app.waypoints[0].lat).toBe(30);
    expect(app.waypoints[0].drop).toBe(true);
    expect(app.waypoints[0].type).toBe('spline');
  });

  it('defaults missing optional fields', () => {
    // Simulate incomplete waypoint data from backend
    const wps = [{ lat: 30, lon: 120, alt: 50 } as any];
    loadDownloadedMission(wps);
    expect(app.waypoints[0].drop).toBe(false);
    expect(app.waypoints[0].delay).toBe(0);
    expect(app.waypoints[0].speed).toBe(0);
    expect(app.waypoints[0].type).toBe('wp');
    expect(app.waypoints[0].loiter_param).toBe(0);
  });

  it('replaces existing waypoints', () => {
    addWaypoint({ lat: 1, lon: 1, alt: 1, drop: false, delay: 0, speed: 0, type: 'wp', loiter_param: 0 });
    addWaypoint({ lat: 2, lon: 2, alt: 2, drop: false, delay: 0, speed: 0, type: 'wp', loiter_param: 0 });
    loadDownloadedMission([
      { lat: 30, lon: 120, alt: 50, drop: false, delay: 0, speed: 0, type: 'wp', loiter_param: 0 },
    ]);
    expect(app.waypoints.length).toBe(1);
    expect(app.waypoints[0].lat).toBe(30);
  });

  it('creates undo point before replacing', () => {
    addWaypoint({ lat: 10, lon: 10, alt: 10, drop: false, delay: 0, speed: 0, type: 'wp', loiter_param: 0 });
    const undoBefore = app.undoStack.length;
    loadDownloadedMission([
      { lat: 30, lon: 120, alt: 50, drop: false, delay: 0, speed: 0, type: 'wp', loiter_param: 0 },
    ]);
    expect(app.undoStack.length).toBeGreaterThan(undoBefore);
  });

  it('handles empty waypoint array', () => {
    addWaypoint({ lat: 10, lon: 10, alt: 10, drop: false, delay: 0, speed: 0, type: 'wp', loiter_param: 0 });
    loadDownloadedMission([]);
    expect(app.waypoints.length).toBe(0);
  });
});

// ============================================================
// Parameter File Parsing (Frontend Logic)
// ============================================================

describe('Parameter file parsing', () => {
  function parseParamFile(text: string): Map<string, number> {
    const map = new Map<string, number>();
    for (const line of text.split('\n')) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#')) continue;
      const parts = trimmed.split(/[\t,\s]+/);
      if (parts.length >= 2) {
        const name = parts[0],
          val = parseFloat(parts[1]);
        if (!isNaN(val)) map.set(name, val);
      }
    }
    return map;
  }

  it('parses tab-separated param file', () => {
    const text = 'BATT_CAPACITY\t5000\nARMING_CHECK\t1';
    const params = parseParamFile(text);
    expect(params.get('BATT_CAPACITY')).toBe(5000);
    expect(params.get('ARMING_CHECK')).toBe(1);
  });

  it('parses comma-separated param file', () => {
    const text = 'BATT_CAPACITY,5000\nARMING_CHECK,1';
    const params = parseParamFile(text);
    expect(params.get('BATT_CAPACITY')).toBe(5000);
  });

  it('skips comment lines starting with #', () => {
    const text = '# comment\nBATT_CAPACITY\t5000\n# another\nARMING_CHECK\t1';
    const params = parseParamFile(text);
    expect(params.size).toBe(2);
  });

  it('skips lines with non-numeric values', () => {
    const text = 'BATT_CAPACITY\tabc\nARMING_CHECK\t1';
    const params = parseParamFile(text);
    expect(params.has('BATT_CAPACITY')).toBe(false);
    expect(params.get('ARMING_CHECK')).toBe(1);
  });

  it('skips single-column lines (no value)', () => {
    const text = 'BATT_CAPACITY\nARMING_CHECK\t1';
    const params = parseParamFile(text);
    expect(params.has('BATT_CAPACITY')).toBe(false);
    expect(params.get('ARMING_CHECK')).toBe(1);
  });

  it('handles inline comments after value (tab-separated extra fields)', () => {
    const text = 'BATT_CAPACITY\t5000\t# default=4000';
    const params = parseParamFile(text);
    expect(params.get('BATT_CAPACITY')).toBe(5000);
  });
});
