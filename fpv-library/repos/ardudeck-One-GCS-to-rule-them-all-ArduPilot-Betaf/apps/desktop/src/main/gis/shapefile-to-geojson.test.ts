import { describe, it, expect } from 'vitest';
import { shapefileToGeoJson, reprojectionFromPrj } from './shapefile-to-geojson';

/**
 * Build a minimal single-record Polygon shapefile in memory. `points` is the
 * exterior ring (closed, [x,y]); ESRI outer rings are clockwise.
 */
function buildPolygonShp(points: Array<[number, number]>): Uint8Array {
  const numPoints = points.length;
  const numParts = 1;
  // content: shapeType(4) + box(32) + numParts(4) + numPoints(4) + parts(4*1) + points(16*N)
  const contentBytes = 4 + 32 + 4 + 4 + 4 * numParts + 16 * numPoints;
  const total = 100 + 8 + contentBytes;
  const buf = new ArrayBuffer(total);
  const v = new DataView(buf);

  v.setInt32(0, 9994, false);          // file code (BE)
  v.setInt32(24, total / 2, false);    // file length in 16-bit words (BE)
  v.setInt32(28, 1000, true);          // version (LE)
  v.setInt32(32, 5, true);             // shape type Polygon (LE)

  // record header
  v.setInt32(100, 1, false);           // record number (BE)
  v.setInt32(104, contentBytes / 2, false); // content length words (BE)

  let p = 108;
  v.setInt32(p, 5, true); p += 4;      // shape type
  p += 32;                              // skip box
  v.setInt32(p, numParts, true); p += 4;
  v.setInt32(p, numPoints, true); p += 4;
  v.setInt32(p, 0, true); p += 4;      // part 0 starts at point 0
  for (const [x, y] of points) {
    v.setFloat64(p, x, true); p += 8;
    v.setFloat64(p, y, true); p += 8;
  }
  return new Uint8Array(buf);
}

describe('shapefileToGeoJson', () => {
  it('parses a clockwise polygon into a GeoJSON Polygon feature', () => {
    // Clockwise unit square (closed ring): signed area < 0 -> outer ring.
    const ring: Array<[number, number]> = [[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]];
    const { geojson, featureCount } = shapefileToGeoJson(buildPolygonShp(ring));
    expect(featureCount).toBe(1);
    const feat = geojson.features[0]!;
    expect(feat.geometry.type).toBe('Polygon');
    const coords = feat.geometry.coordinates as number[][][];
    expect(coords).toHaveLength(1);          // one ring, no holes
    expect(coords[0]).toHaveLength(5);       // ring preserved as stored
    expect(coords[0]![0]).toEqual([0, 0]);   // [lon, lat] passthrough for geographic
  });

  it('rejects a buffer that is not a shapefile', () => {
    expect(() => shapefileToGeoJson(new Uint8Array(8))).toThrow();
  });
});

describe('reprojectionFromPrj', () => {
  it('passes coordinates through for a geographic CRS', () => {
    const geog = 'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]]]';
    const reproject = reprojectionFromPrj(geog);
    expect(reproject(12.5, 41.9)).toEqual([12.5, 41.9]);
  });

  it('inverts UTM (Transverse Mercator) easting/northing to lon/lat', () => {
    // UTM zone 33N: central meridian 15E, false easting 500000, k0 0.9996.
    // A point at (500000, 0) sits on the central meridian at the equator.
    const utm33n =
      'PROJCS["WGS_1984_UTM_Zone_33N",GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",' +
      'SPHEROID["WGS_1984",6378137.0,298.257223563]],PRIMEM["Greenwich",0.0],' +
      'UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],' +
      'PARAMETER["false_easting",500000.0],PARAMETER["false_northing",0.0],' +
      'PARAMETER["central_meridian",15.0],PARAMETER["scale_factor",0.9996],' +
      'PARAMETER["latitude_of_origin",0.0],UNIT["Meter",1.0]]';
    const reproject = reprojectionFromPrj(utm33n);
    const [lon, lat] = reproject(500000, 0);
    expect(lon).toBeCloseTo(15, 4);
    expect(lat).toBeCloseTo(0, 4);
  });

  it('inverts Web Mercator to lon/lat', () => {
    const webMerc = 'PROJCS["WGS_1984_Web_Mercator_Auxiliary_Sphere",PROJECTION["Mercator_Auxiliary_Sphere"]]';
    const reproject = reprojectionFromPrj(webMerc);
    const [lon, lat] = reproject(0, 0);
    expect(lon).toBeCloseTo(0, 6);
    expect(lat).toBeCloseTo(0, 6);
  });
});
