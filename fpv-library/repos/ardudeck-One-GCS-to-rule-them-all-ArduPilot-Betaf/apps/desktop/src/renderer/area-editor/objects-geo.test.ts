/**
 * Tests for objects-geo.ts — pure GeoJSON builders for the object renderer.
 */

import { describe, it, expect } from 'vitest';
import type { LatLng } from '../components/survey/survey-types';
import { makeRectangle, makeFromWorldRing } from './area-object';
import {
  buildObjectsData,
  buildTransformHandles,
  buildVertexHandles,
  buildDraftData,
  colorForIndex,
} from './objects-geo';

const CENTER: LatLng = { lat: 42, lng: 19 };

describe('buildObjectsData', () => {
  it('emits a colored, selected polygon per visible object', () => {
    const a = makeRectangle(CENTER, 100, 60, 'A');
    const b = makeRectangle(CENTER, 50, 50, 'B');
    const fc = buildObjectsData([a, b], b.id);
    expect(fc.features).toHaveLength(2);
    const fa = fc.features[0]!;
    const fb = fc.features[1]!;
    expect(fa.properties!['color']).toBe(colorForIndex(0));
    expect(fa.properties!['selected']).toBe(false);
    expect(fb.properties!['selected']).toBe(true);
    expect(fa.geometry.type).toBe('Polygon');
  });

  it('skips hidden objects', () => {
    const a = { ...makeRectangle(CENTER, 100, 60, 'A'), visible: false };
    expect(buildObjectsData([a], null).features).toHaveLength(0);
  });

  it('a corridor emits a swath polygon + a centerline', () => {
    const c = makeFromWorldRing('corridor', [
      { lat: 42, lng: 19 }, { lat: 42.002, lng: 19.002 },
    ], 'C', { corridorWidthM: 60 });
    const fc = buildObjectsData([c], c.id);
    const types = fc.features.map((f) => f.geometry.type).sort();
    expect(types).toEqual(['LineString', 'Polygon']);
  });
});

describe('buildTransformHandles', () => {
  it('produces a bbox, 8 scale handles, a rotate handle and its stalk', () => {
    const r = makeRectangle(CENTER, 100, 100, 'R');
    const fc = buildTransformHandles(r);
    const roles = fc.features.map((f) => f.properties!['role']);
    expect(roles.filter((x) => x === 'scale')).toHaveLength(8);
    expect(roles.filter((x) => x === 'bbox')).toHaveLength(1);
    expect(roles.filter((x) => x === 'rotate')).toHaveLength(1);
    expect(roles.filter((x) => x === 'rotate-stalk')).toHaveLength(1);
  });

  it('corner scale handles anchor on the opposite corner', () => {
    const r = makeRectangle(CENTER, 100, 100, 'R'); // corners +/-50
    const fc = buildTransformHandles(r);
    const corner = fc.features.find(
      (f) => f.properties!['role'] === 'scale' && f.properties!['axis'] === 'xy',
    )!;
    // first corner is (-50,-50) anchored at (50,50)
    expect(corner.properties!['hx']).toBe(-50);
    expect(corner.properties!['ax']).toBe(50);
  });
});

describe('buildVertexHandles', () => {
  it('one handle per ring vertex, flagging the selected one', () => {
    const poly = makeFromWorldRing('polygon', [
      { lat: 42, lng: 19 }, { lat: 42, lng: 19.001 }, { lat: 42.001, lng: 19.001 }, { lat: 42.001, lng: 19 },
    ], 'P');
    const fc = buildVertexHandles(poly, 2);
    expect(fc.features).toHaveLength(4);
    expect(fc.features[2]!.properties!['selected']).toBe(true);
    expect(fc.features[0]!.properties!['selected']).toBe(false);
  });

  it('emits a handle per hole vertex, tagged with the hole index', () => {
    const poly = makeFromWorldRing('polygon', [
      { lat: 42, lng: 19 }, { lat: 42, lng: 19.002 }, { lat: 42.002, lng: 19.002 }, { lat: 42.002, lng: 19 },
    ], 'P', {
      holes: [[
        { lat: 42.0005, lng: 19.0005 }, { lat: 42.0005, lng: 19.0015 }, { lat: 42.0015, lng: 19.001 },
      ]],
    });
    const fc = buildVertexHandles(poly, null);
    expect(fc.features).toHaveLength(7); // 4 outer + 3 hole
    const holeHandles = fc.features.filter((f) => f.properties!['hole'] === 0);
    expect(holeHandles).toHaveLength(3);
    expect(holeHandles.every((f) => f.properties!['branch'] === -1)).toBe(true);
  });
});

describe('buildDraftData', () => {
  it('draws a rubber-band to the cursor and a point per placed vertex', () => {
    const pts: LatLng[] = [{ lat: 42, lng: 19 }, { lat: 42.001, lng: 19 }];
    const fc = buildDraftData(pts, { lat: 42.002, lng: 19 });
    const line = fc.features.find((f) => f.geometry.type === 'LineString')!;
    expect((line.geometry as GeoJSON.LineString).coordinates).toHaveLength(3); // 2 + cursor
    expect(fc.features.filter((f) => f.geometry.type === 'Point')).toHaveLength(2);
  });
});
