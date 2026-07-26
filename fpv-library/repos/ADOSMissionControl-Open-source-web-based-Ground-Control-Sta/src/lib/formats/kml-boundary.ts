/**
 * @module formats/kml-boundary
 * @description Extract boundary polygon rings from KML text, delegating to the
 * shared KML parser which already handles namespaces, the lon,lat -> lat,lon
 * swap, and the closing-vertex trim.
 *
 * CRITICAL: KML coordinate order is lon,lat. {@link parseKML} performs the swap,
 * so the rings returned here are already in our lat,lon convention.
 *
 * @license GPL-3.0-only
 */

import { parseKML } from "./kml-parser";

/**
 * Parse KML text and return its polygon boundary rings as `[lat, lon]` pairs.
 *
 * The shared {@link parseKML} already swaps KML's lon,lat coordinates to our
 * lat,lon convention and removes the duplicate closing vertex, so this is a thin
 * boundary-focused view over its polygon output. Returns an empty array when the
 * document carries no polygon — never a fabricated shape.
 *
 * @param text Raw KML XML string (also works on the doc.kml extracted from a KMZ).
 * @returns Outer boundary rings, `[lat, lon][]` each; empty when none found.
 */
export function parseKmlBoundary(text: string): [number, number][][] {
  return parseKML(text).polygons;
}
