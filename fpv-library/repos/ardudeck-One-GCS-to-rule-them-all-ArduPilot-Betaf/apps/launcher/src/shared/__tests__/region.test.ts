import { describe, expect, it } from 'vitest';
import { parseRegionManifest, regionDisplayName } from '../region.js';

// A real manifest, straight from godot/assets/terrain/bar/manifest.json.
const BAR = {
  box_utm: {
    min_x: 340284.01736978214,
    max_y: 4667123.107810575,
    max_x: 352080.01736978214,
    min_y: 4656875.107810575,
  },
  meters_per_texel: 12.0,
  size_texels: { w: 983, h: 854 },
  elevation_m: { min: -1.184, max: 1588.283 },
  stadium_utm: { x: 342436.042045377, y: 4661925.11748801 },
  utm_epsg: 32634,
  home_wgs84: { lat: 42.0936, lon: 19.0947 },
  aerial: {
    source: 'Copernicus Sentinel-2 L2A',
    date: '2025-06-29',
    cloud_cover: 0.002687,
    res_m: 10,
    attribution: 'Copernicus Sentinel data 2025',
  },
  canopy: { attribution: 'Canopy height: Meta and World Resources Institute, CC-BY-4.0' },
  built_height: { attribution: 'GHSL, European Commission Joint Research Centre' },
};

describe('parseRegionManifest', () => {
  it('reads a complete manifest with no warnings', () => {
    const parsed = parseRegionManifest(BAR);
    expect(parsed.warnings).toEqual([]);
    expect(parsed.home).toEqual({ lat: 42.0936, lon: 19.0947 });
    expect(parsed.elevationM).toEqual({ min: -1.184, max: 1588.283 });
    expect(parsed.sizeTexels).toEqual({ w: 983, h: 854 });
    expect(parsed.metersPerTexel).toBe(12);
    expect(parsed.utmEpsg).toBe(32634);
    expect(parsed.imagery.date).toBe('2025-06-29');
    expect(parsed.attribution).toHaveLength(3);
  });

  it('derives ground extent from the UTM box', () => {
    const extent = parseRegionManifest(BAR).extentM;
    expect(extent?.width).toBeCloseTo(11796, 0);
    expect(extent?.height).toBeCloseTo(10248, 0);
  });

  it('warns rather than throwing when home_wgs84 is missing', () => {
    const { home_wgs84: _omitted, ...withoutHome } = BAR;
    const parsed = parseRegionManifest(withoutHome);
    expect(parsed.home).toBeNull();
    expect(parsed.warnings.join(' ')).toContain('home_wgs84');
    // Everything else still comes through: one absent field must not lose the region.
    expect(parsed.elevationM).not.toBeNull();
    expect(parsed.extentM).not.toBeNull();
  });

  it('survives a manifest that is not an object', () => {
    const parsed = parseRegionManifest('broken');
    expect(parsed.home).toBeNull();
    expect(parsed.warnings.join(' ')).toContain('not a JSON object');
  });

  it('deduplicates repeated attribution strings', () => {
    const parsed = parseRegionManifest({
      ...BAR,
      canopy: { attribution: 'Copernicus Sentinel data 2025' },
    });
    expect(parsed.attribution).toEqual([
      'Copernicus Sentinel data 2025',
      'GHSL, European Commission Joint Research Centre',
    ]);
  });
});

describe('regionDisplayName', () => {
  it('title-cases a directory name', () => {
    expect(regionDisplayName('bar')).toBe('Bar');
    expect(regionDisplayName('sutomore')).toBe('Sutomore');
    expect(regionDisplayName('bad-tolz')).toBe('Bad Tolz');
    expect(regionDisplayName('san_marino')).toBe('San Marino');
  });
});
