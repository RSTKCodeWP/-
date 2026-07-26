/**
 * Tests for gis-area-import. Runs in the default vitest Node environment.
 * DOMParser is polyfilled below using @xmldom/xmldom (already a transitive
 * dependency of the monorepo) so no new packages are required.
 */
import { beforeAll, describe, it, expect } from 'vitest';
import { DOMParser as XmldomParser } from '@xmldom/xmldom';
import { parseGisArea, gisFormatForExtension } from './gis-area-import';

// Polyfill DOMParser for Node test environment.
// @xmldom/xmldom is already installed as a transitive dep of the monorepo.
// We configure it to throw on fatal errors, which lets parseKml surface a
// useful message via the try/catch it already wraps around parseFromString.
beforeAll(() => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (globalThis as any).DOMParser = class ThrowingDOMParser {
    parseFromString(content: string, mimeType: string): Document {
      let parseError: Error | null = null;
      const parser = new XmldomParser({
        errorHandler: {
          warning: () => {
            // ignore warnings
          },
          error: (msg: string) => {
            parseError = new Error(msg);
          },
          fatalError: (msg: string) => {
            parseError = new Error(msg);
          },
        },
      });
      const doc = parser.parseFromString(content, mimeType as 'application/xml');
      if (parseError !== null) {
        throw parseError;
      }
      return doc as unknown as Document;
    }
  };
});

describe('gisFormatForExtension', () => {
  it('maps extensions to formats', () => {
    expect(gisFormatForExtension('kml')).toBe('kml');
    expect(gisFormatForExtension('.kmz')).toBe('kml');
    expect(gisFormatForExtension('GeoJSON')).toBe('geojson');
    expect(gisFormatForExtension('json')).toBe('geojson');
    expect(gisFormatForExtension('csv')).toBeNull();
  });
});

describe('parseGisArea - GeoJSON', () => {
  it('reads a Polygon feature with a hole', () => {
    const gj = JSON.stringify({
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry: {
            type: 'Polygon',
            coordinates: [
              [[10, 0], [11, 0], [11, 1], [10, 1], [10, 0]], // outer (closed)
              [[10.2, 0.2], [10.8, 0.2], [10.8, 0.8], [10.2, 0.2]], // hole
            ],
          },
        },
      ],
    });
    const areas = parseGisArea(gj, 'geojson');
    expect(areas).toHaveLength(1);
    // Closing point dropped -> 4 unique vertices.
    expect(areas[0]!.polygon).toHaveLength(4);
    expect(areas[0]!.polygon[0]).toEqual({ lat: 0, lng: 10 });
    expect(areas[0]!.holes).toHaveLength(1);
  });

  it('reads MultiPolygon as multiple areas', () => {
    const gj = JSON.stringify({
      type: 'Feature',
      geometry: {
        type: 'MultiPolygon',
        coordinates: [
          [[[0, 0], [1, 0], [1, 1]]],
          [[[5, 5], [6, 5], [6, 6]]],
        ],
      },
    });
    const areas = parseGisArea(gj, 'geojson');
    expect(areas).toHaveLength(2);
  });

  it('returns [] on garbage', () => {
    expect(parseGisArea('not json', 'geojson')).toEqual([]);
  });
});

describe('parseGisArea - KML', () => {
  it('reads a Polygon with outer + inner boundary (no namespace)', () => {
    const kml = `<?xml version="1.0"?><kml><Placemark><Polygon>
      <outerBoundaryIs><LinearRing><coordinates>
        10,0,0 11,0,0 11,1,0 10,1,0 10,0,0
      </coordinates></LinearRing></outerBoundaryIs>
      <innerBoundaryIs><LinearRing><coordinates>
        10.2,0.2 10.8,0.2 10.8,0.8 10.2,0.2
      </coordinates></LinearRing></innerBoundaryIs>
    </Polygon></Placemark></kml>`;
    const areas = parseGisArea(kml, 'kml');
    expect(areas).toHaveLength(1);
    expect(areas[0]!.polygon).toHaveLength(4);
    expect(areas[0]!.polygon[0]).toEqual({ lat: 0, lng: 10 });
    expect(areas[0]!.holes).toHaveLength(1);
  });

  it('skips degenerate polygons', () => {
    const kml = `<kml><Polygon><outerBoundaryIs><LinearRing><coordinates>10,0 11,0</coordinates></LinearRing></outerBoundaryIs></Polygon></kml>`;
    expect(parseGisArea(kml, 'kml')).toEqual([]);
  });

  it('reads a namespaced KML with one polygon and two holes', () => {
    const kml = `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Placemark>
    <Polygon>
      <outerBoundaryIs>
        <LinearRing>
          <coordinates>10,0,0 11,0,0 11,1,0 10,1,0 10,0,0</coordinates>
        </LinearRing>
      </outerBoundaryIs>
      <innerBoundaryIs>
        <LinearRing>
          <coordinates>10.1,0.1 10.4,0.1 10.4,0.4 10.1,0.1</coordinates>
        </LinearRing>
      </innerBoundaryIs>
      <innerBoundaryIs>
        <LinearRing>
          <coordinates>10.5,0.5 10.9,0.5 10.9,0.9 10.5,0.5</coordinates>
        </LinearRing>
      </innerBoundaryIs>
    </Polygon>
  </Placemark>
</kml>`;
    const areas = parseGisArea(kml, 'kml');
    expect(areas).toHaveLength(1);
    // outer ring was closed (last == first), so 4 points after dedup
    expect(areas[0]!.polygon).toHaveLength(4);
    expect(areas[0]!.polygon[0]).toEqual({ lat: 0, lng: 10 });
    expect(areas[0]!.holes).toHaveLength(2);
    expect(areas[0]!.holes[0]).toHaveLength(3);
    expect(areas[0]!.holes[1]).toHaveLength(3);
  });

  it('reads a MultiGeometry with two polygons', () => {
    const kml = `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Placemark>
    <MultiGeometry>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>0,0 1,0 1,1 0,0</coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>5,5 6,5 6,6 5,5</coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </MultiGeometry>
  </Placemark>
</kml>`;
    const areas = parseGisArea(kml, 'kml');
    expect(areas).toHaveLength(2);
    expect(areas[0]!.polygon[0]).toEqual({ lat: 0, lng: 0 });
    expect(areas[1]!.polygon[0]).toEqual({ lat: 5, lng: 5 });
  });

  it('deduplicates closed-ring last point', () => {
    // Ring where last point == first; must be stripped to open ring
    const kml = `<?xml version="1.0"?>
<kml>
  <Polygon>
    <outerBoundaryIs>
      <LinearRing>
        <coordinates>20,10,0 21,10,0 21,11,0 20,11,0 20,10,0</coordinates>
      </LinearRing>
    </outerBoundaryIs>
  </Polygon>
</kml>`;
    const areas = parseGisArea(kml, 'kml');
    expect(areas).toHaveLength(1);
    const ring = areas[0]!.polygon;
    // 5 tuples in source; last == first, so 4 after openRing
    expect(ring).toHaveLength(4);
    // first and last must NOT be equal after opening
    expect(ring[0]).not.toEqual(ring[ring.length - 1]);
  });

  it('returns [] on malformed XML', () => {
    // parseGisArea catches the internal throw and returns []
    const bad = `<kml><Polygon><outerBoundaryIs><LinearRing><coordinates>0,0 1,0 1,1</coordinates></WRONG>`;
    expect(parseGisArea(bad, 'kml')).toEqual([]);
  });
});
