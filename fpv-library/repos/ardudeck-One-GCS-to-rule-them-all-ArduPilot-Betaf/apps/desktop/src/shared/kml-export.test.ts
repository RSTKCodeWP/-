import { describe, it, expect } from 'vitest';
import { DOMParser } from '@xmldom/xmldom';
import { areasToKml, type ExportArea } from './kml-export.js';

function parseKml(kmlString: string): Document {
  const parser = new DOMParser();
  const doc = parser.parseFromString(kmlString, 'application/xml');
  // @xmldom/xmldom surfaces parse errors as a document with a parseerror element
  const parseError = doc.getElementsByTagName('parsererror')[0];
  if (parseError) {
    throw new Error(`KML parse error: ${parseError.textContent}`);
  }
  return doc;
}

describe('areasToKml', () => {
  it('produces a well-formed KML 2.2 document with XML declaration', () => {
    const areas: ExportArea[] = [
      { polygon: [{ lat: 1, lng: 2 }, { lat: 3, lng: 4 }, { lat: 5, lng: 6 }] },
    ];
    const kml = areasToKml(areas);

    expect(kml).toMatch(/^<\?xml version="1\.0" encoding="UTF-8"\?>/);

    const doc = parseKml(kml);
    const root = doc.documentElement;
    expect(root.tagName).toBe('kml');
    expect(root.getAttribute('xmlns')).toBe('http://www.opengis.net/kml/2.2');
    expect(doc.getElementsByTagName('Document')[0]).toBeDefined();
  });

  it('produces one Placemark per area with correct name default', () => {
    const areas: ExportArea[] = [
      { polygon: [{ lat: 1, lng: 2 }, { lat: 3, lng: 4 }, { lat: 5, lng: 6 }] },
      { name: 'My Zone', polygon: [{ lat: 10, lng: 20 }, { lat: 30, lng: 40 }, { lat: 50, lng: 60 }] },
    ];
    const kml = areasToKml(areas);
    const doc = parseKml(kml);

    const placemarks = doc.getElementsByTagName('Placemark');
    expect(placemarks.length).toBe(2);

    const names = Array.from({ length: placemarks.length }, (_, i) =>
      placemarks[i]!.getElementsByTagName('name')[0]?.textContent
    );
    expect(names[0]).toBe('Area 1');
    expect(names[1]).toBe('My Zone');
  });

  it('emits coordinates in lng,lat,0 order (KML convention) and closes the ring', () => {
    const polygon = [
      { lat: 10, lng: 20 },
      { lat: 30, lng: 40 },
      { lat: 50, lng: 60 },
    ];
    const areas: ExportArea[] = [{ polygon }];
    const kml = areasToKml(areas);
    const doc = parseKml(kml);

    const outerBoundary = doc.getElementsByTagName('outerBoundaryIs')[0];
    expect(outerBoundary).toBeDefined();
    const coordsEl = outerBoundary!.getElementsByTagName('coordinates')[0];
    expect(coordsEl).toBeDefined();
    const coordsText = coordsEl!.textContent?.trim() ?? '';

    const tuples = coordsText.split(/\s+/).filter(Boolean);
    // Ring must be closed: last tuple == first tuple
    expect(tuples.length).toBe(4);
    expect(tuples[0]).toBe('20,10,0');
    expect(tuples[1]).toBe('40,30,0');
    expect(tuples[2]).toBe('60,50,0');
    expect(tuples[3]).toBe('20,10,0'); // closed
  });

  it('emits one innerBoundaryIs per hole', () => {
    const areas: ExportArea[] = [
      {
        polygon: [
          { lat: 0, lng: 0 },
          { lat: 10, lng: 0 },
          { lat: 10, lng: 10 },
          { lat: 0, lng: 10 },
        ],
        holes: [
          [{ lat: 2, lng: 2 }, { lat: 4, lng: 2 }, { lat: 4, lng: 4 }],
          [{ lat: 6, lng: 6 }, { lat: 8, lng: 6 }, { lat: 8, lng: 8 }],
        ],
      },
    ];
    const kml = areasToKml(areas);
    const doc = parseKml(kml);

    const polygonEl = doc.getElementsByTagName('Polygon')[0];
    expect(polygonEl).toBeDefined();
    const innerBoundaries = polygonEl!.getElementsByTagName('innerBoundaryIs');
    expect(innerBoundaries.length).toBe(2);

    // Verify each hole's ring is closed
    Array.from({ length: innerBoundaries.length }, (_, i) => innerBoundaries[i]!).forEach((ib) => {
      const coordsEl = ib.getElementsByTagName('coordinates')[0];
      expect(coordsEl).toBeDefined();
      const coords = coordsEl!.textContent?.trim() ?? '';
      const tuples = coords.split(/\s+/).filter(Boolean);
      // 3 original points + 1 closing = 4
      expect(tuples.length).toBe(4);
      expect(tuples[0]).toBe(tuples[3]);
    });
  });

  it('escapes XML special characters in names', () => {
    const areas: ExportArea[] = [
      {
        name: 'Area & <Zone> "Alpha" \'Beta\'',
        polygon: [{ lat: 1, lng: 2 }, { lat: 3, lng: 4 }, { lat: 5, lng: 6 }],
      },
    ];
    const kml = areasToKml(areas);

    // The raw string must contain properly escaped entities
    expect(kml).toContain('Area &amp; &lt;Zone&gt; &quot;Alpha&quot; &apos;Beta&apos;');

    // The document should still be parseable and decode back to the original
    const doc = parseKml(kml);
    const name = doc.getElementsByTagName('Placemark')[0]?.getElementsByTagName('name')[0]?.textContent;
    expect(name).toBe('Area & <Zone> "Alpha" \'Beta\'');
  });

  it('skips areas with fewer than 3 polygon points', () => {
    const areas: ExportArea[] = [
      { polygon: [{ lat: 1, lng: 2 }, { lat: 3, lng: 4 }] }, // only 2 pts - skip
      { polygon: [{ lat: 10, lng: 20 }, { lat: 30, lng: 40 }, { lat: 50, lng: 60 }] }, // valid
    ];
    const kml = areasToKml(areas);
    const doc = parseKml(kml);

    const placemarks = doc.getElementsByTagName('Placemark');
    expect(placemarks.length).toBe(1);

    // Area 2 is the surviving one (index-based naming preserves position)
    const name = placemarks[0]!.getElementsByTagName('name')[0]?.textContent;
    expect(name).toBe('Area 2');
  });
});
