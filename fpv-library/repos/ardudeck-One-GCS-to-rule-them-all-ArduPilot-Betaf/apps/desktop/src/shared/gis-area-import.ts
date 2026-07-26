/**
 * GIS area import - parse survey boundaries out of the files surveyors already
 * have (KML and GeoJSON) so they don't hand-trace polygons on the map.
 *
 * Both formats reduce to the same shape: an outer ring plus optional inner
 * rings (no-fly holes). Coordinates are normalized to {lat, lng}. KMZ is a zip
 * around a KML document; the main process unzips it and hands us the KML text,
 * so this module stays pure (no Node) and unit-testable.
 */

export interface ImportedArea {
  /** Exterior boundary, normalized to {lat, lng}, ring NOT closed (no repeated last point). */
  polygon: Array<{ lat: number; lng: number }>;
  /** Inner rings (no-fly holes), same normalization. */
  holes: Array<Array<{ lat: number; lng: number }>>;
}

export type GisFormat = 'kml' | 'geojson';

/** Detect format from a file extension (lower-cased, no dot needed). */
export function gisFormatForExtension(ext: string): GisFormat | null {
  const e = ext.replace(/^\./, '').toLowerCase();
  if (e === 'kml' || e === 'kmz') return 'kml';
  if (e === 'geojson' || e === 'json') return 'geojson';
  return null;
}

/** Drop a trailing point that duplicates the first (closed rings) so editing behaves. */
function openRing(ring: Array<{ lat: number; lng: number }>): Array<{ lat: number; lng: number }> {
  if (ring.length > 1) {
    const a = ring[0]!;
    const b = ring[ring.length - 1]!;
    if (a.lat === b.lat && a.lng === b.lng) return ring.slice(0, -1);
  }
  return ring;
}

function isValidLatLng(lat: number, lng: number): boolean {
  return Number.isFinite(lat) && Number.isFinite(lng) && Math.abs(lat) <= 90 && Math.abs(lng) <= 180;
}

// ── GeoJSON ──────────────────────────────────────────────────────────────────

function geoJsonRing(coords: unknown): Array<{ lat: number; lng: number }> {
  if (!Array.isArray(coords)) return [];
  const out: Array<{ lat: number; lng: number }> = [];
  for (const pt of coords) {
    if (!Array.isArray(pt) || pt.length < 2) continue;
    const lng = Number(pt[0]);
    const lat = Number(pt[1]);
    if (isValidLatLng(lat, lng)) out.push({ lat, lng });
  }
  return openRing(out);
}

/** Collect every Polygon (as [outer, ...holes][]) from any GeoJSON geometry. */
function geoJsonPolygons(geometry: unknown): unknown[][] {
  if (!geometry || typeof geometry !== 'object') return [];
  const g = geometry as { type?: string; coordinates?: unknown; geometries?: unknown };
  if (g.type === 'Polygon' && Array.isArray(g.coordinates)) return [g.coordinates];
  if (g.type === 'MultiPolygon' && Array.isArray(g.coordinates)) return g.coordinates as unknown[][];
  if (g.type === 'GeometryCollection' && Array.isArray(g.geometries)) {
    return g.geometries.flatMap((sub) => geoJsonPolygons(sub));
  }
  return [];
}

function parseGeoJson(content: string): ImportedArea[] {
  const root = JSON.parse(content) as unknown;
  const geometries: unknown[] = [];
  const r = root as { type?: string; features?: unknown; geometry?: unknown };
  if (r.type === 'FeatureCollection' && Array.isArray(r.features)) {
    for (const f of r.features) {
      const geom = (f as { geometry?: unknown }).geometry;
      if (geom) geometries.push(geom);
    }
  } else if (r.type === 'Feature' && r.geometry) {
    geometries.push(r.geometry);
  } else {
    geometries.push(root);
  }

  const areas: ImportedArea[] = [];
  for (const geom of geometries) {
    for (const polygon of geoJsonPolygons(geom)) {
      if (!Array.isArray(polygon) || polygon.length === 0) continue;
      const outer = geoJsonRing(polygon[0]);
      if (outer.length < 3) continue;
      const holes = polygon.slice(1).map(geoJsonRing).filter((h) => h.length >= 3);
      areas.push({ polygon: outer, holes });
    }
  }
  return areas;
}

// ── KML ──────────────────────────────────────────────────────────────────────

/** Parse a KML <coordinates> blob: whitespace-separated "lng,lat[,alt]" tuples. */
function kmlCoordinates(blob: string): Array<{ lat: number; lng: number }> {
  const out: Array<{ lat: number; lng: number }> = [];
  for (const tuple of blob.trim().split(/\s+/)) {
    if (!tuple) continue;
    const parts = tuple.split(',');
    if (parts.length < 2) continue;
    const lng = Number(parts[0]);
    const lat = Number(parts[1]);
    if (isValidLatLng(lat, lng)) out.push({ lat, lng });
  }
  return openRing(out);
}

/**
 * Get the text content of the first child element matching a local name,
 * searched within a parent element. Namespace-agnostic: compares localName
 * so "kml:coordinates" and "coordinates" both match "coordinates".
 */
function firstChildText(parent: Element, localName: string): string | null {
  const nodes = parent.getElementsByTagName(localName);
  // getElementsByTagName with an unqualified name matches across all namespaces
  // in both the browser and @xmldom/xmldom.
  if (nodes.length > 0 && nodes[0] != null) {
    return nodes[0].textContent ?? null;
  }
  // Fallback: iterate children by localName for edge cases where prefixed tags
  // might not be matched by the unqualified name.
  const stack: Element[] = [parent];
  while (stack.length > 0) {
    const el = stack.pop()!;
    for (let i = 0; i < el.childNodes.length; i++) {
      const child = el.childNodes[i];
      if (child && child.nodeType === 1 /* ELEMENT_NODE */) {
        const elem = child as Element;
        if (elem.localName === localName) return elem.textContent ?? null;
        stack.push(elem);
      }
    }
  }
  return null;
}

/**
 * Extract an outer ring from a Polygon element's outerBoundaryIs > LinearRing > coordinates.
 * Returns null if not found or fewer than 3 points.
 */
function extractOuterRing(polygon: Element): Array<{ lat: number; lng: number }> | null {
  // getElementsByTagName is namespace-agnostic in both browser and xmldom -
  // it matches on the local part of the tag name, ignoring any prefix.
  const outerEls = polygon.getElementsByTagName('outerBoundaryIs');
  if (outerEls.length === 0 || outerEls[0] == null) return null;
  const coordText = firstChildText(outerEls[0], 'coordinates');
  if (!coordText) return null;
  const ring = kmlCoordinates(coordText);
  return ring.length >= 3 ? ring : null;
}

/** Extract all inner (hole) rings from a Polygon element. */
function extractHoles(polygon: Element): Array<Array<{ lat: number; lng: number }>> {
  const holes: Array<Array<{ lat: number; lng: number }>> = [];
  const innerEls = polygon.getElementsByTagName('innerBoundaryIs');
  for (let i = 0; i < innerEls.length; i++) {
    const inner = innerEls[i];
    if (!inner) continue;
    const coordText = firstChildText(inner, 'coordinates');
    if (!coordText) continue;
    const ring = kmlCoordinates(coordText);
    if (ring.length >= 3) holes.push(ring);
  }
  return holes;
}

function parseKml(content: string): ImportedArea[] {
  // Use DOMParser to parse XML. In the browser renderer this is the native
  // global. In the test environment, a compatible DOMParser is set as a global
  // by the test setup (using @xmldom/xmldom which is already installed).
  const parser = new DOMParser();
  let doc: Document;
  try {
    doc = parser.parseFromString(content, 'application/xml');
  } catch (e) {
    // Some DOMParser implementations (e.g. @xmldom/xmldom with errorHandler)
    // throw on fatal parse errors instead of embedding a <parsererror> element.
    throw new Error(`Invalid KML: could not parse XML (${(e as Error).message ?? e})`);
  }

  // In the browser, a parse failure produces a document whose root is
  // <parsererror> rather than the expected element. Detect and reject it.
  const parseErrors = doc.getElementsByTagName('parsererror');
  if (parseErrors.length > 0) {
    throw new Error('Invalid KML: could not parse XML');
  }

  // Collect all <Polygon> elements anywhere in the document, including inside
  // <MultiGeometry>, <Placemark>, <Folder>, etc. getElementsByTagName with an
  // unqualified name matches regardless of namespace prefix (both browser and
  // @xmldom/xmldom), so "kml:Polygon" is also matched.
  const polygonEls = doc.getElementsByTagName('Polygon');
  const areas: ImportedArea[] = [];

  for (let i = 0; i < polygonEls.length; i++) {
    const polygon = polygonEls[i];
    if (!polygon) continue;
    const outer = extractOuterRing(polygon);
    if (!outer) continue;
    const holes = extractHoles(polygon);
    areas.push({ polygon: outer, holes });
  }

  return areas;
}

/**
 * Parse a GIS boundary file into one or more areas. Returns [] when nothing
 * usable is found (callers should surface a friendly error rather than crash).
 */
export function parseGisArea(content: string, format: GisFormat): ImportedArea[] {
  try {
    return format === 'geojson' ? parseGeoJson(content) : parseKml(content);
  } catch {
    return [];
  }
}
