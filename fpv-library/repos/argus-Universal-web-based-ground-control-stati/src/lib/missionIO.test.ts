import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  parseQgcWaypoints,
  parseQgcPlan,
  exportKml,
  parseKmlCoords,
  segDist,
  totalDist,
  pointInPoly,
} from './missionIO';

describe('parseQgcWaypoints', () => {
  it('parses valid waypoints', () => {
    const text = `QGC WPL 110
0\t1\t0\t16\t0\t0\t0\t0\t34.258\t108.942\t100\t1
1\t0\t3\t16\t0\t0\t0\t0\t34.259\t108.943\t50\t1
2\t0\t3\t82\t0\t0\t0\t0\t34.260\t108.944\t60\t1`;
    const wps = parseQgcWaypoints(text);
    expect(wps).toHaveLength(3);
    expect(wps[0].lat).toBeCloseTo(34.258);
    expect(wps[2].type).toBe('spline');
  });

  it('skips header and non-nav commands', () => {
    const text = `QGC WPL 110
0\t1\t0\t16\t0\t0\t0\t0\t0\t0\t0\t1
1\t0\t3\t178\t0\t5\t0\t0\t0\t0\t0\t1`;
    const wps = parseQgcWaypoints(text);
    expect(wps).toHaveLength(0);
  });
});

describe('parseQgcPlan', () => {
  it('parses plan JSON', () => {
    const plan = {
      mission: {
        items: [
          { command: 22, params: [0, 0, 0, 0, 0, 0, 30] },
          { command: 16, params: [0, 0, 0, 0, 34.26, 108.94, 50] },
          { command: 82, params: [0, 0, 0, 0, 34.27, 108.95, 60] },
        ],
      },
    };
    const wps = parseQgcPlan(JSON.stringify(plan));
    expect(wps).toHaveLength(2);
    expect(wps[0].alt).toBe(50);
    expect(wps[1].type).toBe('spline');
  });
});

describe('exportKml', () => {
  it('generates valid KML', () => {
    const wps = [
      { lat: 34.25, lon: 108.94, alt: 50, drop: false, delay: 0, speed: 0, type: 'wp' as const, loiter_param: 0 },
      { lat: 34.26, lon: 108.95, alt: 60, drop: false, delay: 0, speed: 0, type: 'wp' as const, loiter_param: 0 },
    ];
    const kml = exportKml(wps);
    expect(kml).toContain('<?xml');
    expect(kml).toContain('108.94,34.25,50');
    expect(kml).toContain('108.95,34.26,60');
  });
});

describe('parseKmlCoords', () => {
  beforeEach(() => {
    // Mock DOMParser for node environment
    const mockDOMParser = class {
      parseFromString(text: string, _type: string) {
        // Minimal XML parser for test KML docs
        const coordsMatches = [...text.matchAll(/<coordinates>([\s\S]*?)<\/coordinates>/g)];
        const elements: { textContent: string }[] = coordsMatches.map((m) => ({
          textContent: m[1],
        }));
        return {
          getElementsByTagName: (tag: string) => {
            if (tag === 'coordinates') return elements;
            return [];
          },
        };
      }
    };
    vi.stubGlobal('DOMParser', mockDOMParser);
  });

  it('parses KML with valid coordinates', () => {
    const kml = `<?xml version="1.0"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
<Placemark><LineString><coordinates>108.942,34.258,50
108.943,34.259,60</coordinates></LineString></Placemark>
</Document></kml>`;
    const wps = parseKmlCoords(kml, 30);
    expect(wps).toHaveLength(2);
    expect(wps[0].lat).toBeCloseTo(34.258);
    expect(wps[0].lon).toBeCloseTo(108.942);
    expect(wps[0].alt).toBe(50);
    expect(wps[1].alt).toBe(60);
    expect(wps[0].type).toBe('wp');
  });

  it('uses defaultAlt when altitude is missing', () => {
    const kml = `<kml><Document><Placemark><LineString>
<coordinates>108.942,34.258</coordinates>
</LineString></Placemark></Document></kml>`;
    const wps = parseKmlCoords(kml, 75);
    expect(wps).toHaveLength(1);
    expect(wps[0].alt).toBe(75);
  });

  it('skips coordinates near zero lat/lon', () => {
    const kml = `<kml><Document><Placemark><LineString>
<coordinates>0.0001,0.0001,50
108.943,34.259,60</coordinates>
</LineString></Placemark></Document></kml>`;
    const wps = parseKmlCoords(kml, 30);
    expect(wps).toHaveLength(1);
    expect(wps[0].lat).toBeCloseTo(34.259);
  });

  it('removes duplicate closing point in closed polygon', () => {
    const kml = `<kml><Document><Placemark><LineString>
<coordinates>108.942,34.258,50
108.943,34.259,50
108.944,34.260,50
108.942,34.258,50</coordinates>
</LineString></Placemark></Document></kml>`;
    const wps = parseKmlCoords(kml, 30);
    expect(wps).toHaveLength(3); // last point removed (duplicate of first)
  });

  it('returns empty for KML with no coordinates element', () => {
    const kml = `<kml><Document><Placemark><name>Test</name></Placemark></Document></kml>`;
    const wps = parseKmlCoords(kml, 30);
    expect(wps).toHaveLength(0);
  });

  it('handles multiple coordinate elements', () => {
    const kml = `<kml><Document>
<Placemark><LineString><coordinates>108.942,34.258,50</coordinates></LineString></Placemark>
<Placemark><LineString><coordinates>108.943,34.259,60</coordinates></LineString></Placemark>
</Document></kml>`;
    const wps = parseKmlCoords(kml, 30);
    expect(wps).toHaveLength(2);
  });

  it('skips entries with fewer than 2 comma-separated values', () => {
    const kml = `<kml><Document><Placemark><LineString>
<coordinates>108.942
108.943,34.259,60</coordinates>
</LineString></Placemark></Document></kml>`;
    const wps = parseKmlCoords(kml, 30);
    expect(wps).toHaveLength(1);
    expect(wps[0].lon).toBeCloseTo(108.943);
  });
});

describe('segDist', () => {
  it('computes distance between two points', () => {
    const d = segDist({ lat: 0, lon: 0 }, { lat: 0, lon: 1 });
    expect(d).toBeGreaterThan(100000);
    expect(d).toBeLessThan(120000);
  });

  it('returns 0 for same point', () => {
    expect(segDist({ lat: 34, lon: 108 }, { lat: 34, lon: 108 })).toBe(0);
  });
});

describe('totalDist', () => {
  it('formats distance in meters', () => {
    const wps = [
      { lat: 34.258, lon: 108.942, alt: 50, drop: false, delay: 0, speed: 0, type: 'wp' as const, loiter_param: 0 },
      { lat: 34.259, lon: 108.942, alt: 50, drop: false, delay: 0, speed: 0, type: 'wp' as const, loiter_param: 0 },
    ];
    const d = totalDist(wps);
    expect(d).toMatch(/^\d+m$/);
  });

  it('formats distance in km for long routes', () => {
    const wps = [
      { lat: 34.0, lon: 108.0, alt: 50, drop: false, delay: 0, speed: 0, type: 'wp' as const, loiter_param: 0 },
      { lat: 35.0, lon: 109.0, alt: 50, drop: false, delay: 0, speed: 0, type: 'wp' as const, loiter_param: 0 },
    ];
    const d = totalDist(wps);
    expect(d).toMatch(/km$/);
  });
});

describe('pointInPoly', () => {
  const square = [
    { lat: 0, lon: 0 },
    { lat: 0, lon: 10 },
    { lat: 10, lon: 10 },
    { lat: 10, lon: 0 },
  ];

  it('returns true for point inside', () => {
    expect(pointInPoly(5, 5, square)).toBe(true);
  });

  it('returns false for point outside', () => {
    expect(pointInPoly(15, 5, square)).toBe(false);
  });

  it('returns false for empty polygon', () => {
    expect(pointInPoly(5, 5, [])).toBe(false);
  });
});
