/**
 * @module formats/kmz-handler
 * @description KMZ file handler. KMZ is a ZIP archive containing a doc.kml file.
 * Uses pako (already a project dependency) for decompression.
 * @license GPL-3.0-only
 */

import pako from "pako";
import { parseKML, type KmlParseResult } from "./kml-parser";

/**
 * Parse a KMZ file (ZIP containing doc.kml) into waypoints, polygons, and paths.
 * Falls back to treating the content as plain KML if ZIP parsing fails.
 */
export async function parseKMZ(file: File): Promise<KmlParseResult> {
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer);

  // Check for ZIP magic number (PK\x03\x04)
  if (bytes.length >= 4 && bytes[0] === 0x50 && bytes[1] === 0x4b && bytes[2] === 0x03 && bytes[3] === 0x04) {
    const kmlContent = extractKmlFromZip(bytes);
    if (kmlContent) {
      return parseKML(kmlContent);
    }
  }

  // Fallback: try to parse as plain KML text
  const text = new TextDecoder().decode(bytes);
  return parseKML(text);
}

/**
 * Extract the first .kml file from a ZIP archive.
 * Minimal ZIP parser that reads local file headers to find doc.kml or any .kml file.
 */
function extractKmlFromZip(data: Uint8Array): string | null {
  const view = new DataView(data.buffer, data.byteOffset, data.byteLength);
  let offset = 0;

  while (offset + 30 <= data.length) {
    // Check for local file header signature (PK\x03\x04)
    const sig = view.getUint32(offset, true);
    if (sig !== 0x04034b50) break;

    const compressionMethod = view.getUint16(offset + 8, true);
    const compressedSize = view.getUint32(offset + 18, true);
    const fileNameLength = view.getUint16(offset + 26, true);
    const extraFieldLength = view.getUint16(offset + 28, true);

    const fileNameBytes = data.slice(offset + 30, offset + 30 + fileNameLength);
    const fileName = new TextDecoder().decode(fileNameBytes);

    const dataOffset = offset + 30 + fileNameLength + extraFieldLength;

    if (fileName.toLowerCase().endsWith(".kml")) {
      if (dataOffset + compressedSize > data.length) break;
      const fileData = data.slice(dataOffset, dataOffset + compressedSize);

      if (compressionMethod === 0) {
        // Stored (no compression)
        return new TextDecoder().decode(fileData);
      } else if (compressionMethod === 8) {
        // Deflated
        try {
          const inflated = pako.inflateRaw(fileData);
          return new TextDecoder().decode(inflated);
        } catch {
          // Try regular inflate as fallback
          try {
            const inflated = pako.inflate(fileData);
            return new TextDecoder().decode(inflated);
          } catch {
            return null;
          }
        }
      }
    }

    // Move to next local file header
    offset = dataOffset + compressedSize;
  }

  return null;
}
