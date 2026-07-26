/**
 * iNav geozone decoders: geofence polygon metadata and vertices.
 *
 * @module protocol/msp/decoders/inav/geozones
 */

import { readU8, readS32 } from "./helpers";
import type { INavGeozone, INavGeozoneVertex } from "./types";

// ── iNav GEOZONE decoder ──────────────────────────────────────

/**
 * MSP2_INAV_GEOZONE (0x2210)
 *
 * U8  number
 * U8  type (0=EXCLUSIVE, 1=INCLUSIVE)
 * U8  shape (0=CIRCULAR, 1=POLYGON)
 * S32 minAlt (cm)
 * S32 maxAlt (cm)
 * U8  fenceAction
 * U8  vertexCount
 * U8  isSeaLevelRef (bool)
 * U8  enabled (bool)
 */
export function decodeMspINavGeozone(dv: DataView): INavGeozone {
  return {
    number: readU8(dv, 0),
    type: dv.byteLength > 1 ? readU8(dv, 1) : 0,
    shape: dv.byteLength > 2 ? readU8(dv, 2) : 0,
    minAlt: dv.byteLength > 6 ? readS32(dv, 3) : 0,
    maxAlt: dv.byteLength > 10 ? readS32(dv, 7) : 0,
    fenceAction: dv.byteLength > 11 ? readU8(dv, 11) : 0,
    vertexCount: dv.byteLength > 12 ? readU8(dv, 12) : 0,
    isSeaLevelRef: dv.byteLength > 13 ? readU8(dv, 13) !== 0 : false,
    enabled: dv.byteLength > 14 ? readU8(dv, 14) !== 0 : false,
  };
}

// ── iNav GEOZONE VERTEX decoder ───────────────────────────────

/**
 * MSP2_INAV_GEOZONE_VERTEX (0x2212)
 *
 * U8  geozoneId
 * U8  vertexIdx
 * S32 lat (degrees x 1e7)
 * S32 lon (degrees x 1e7)
 */
export function decodeMspINavGeozoneVertex(dv: DataView): INavGeozoneVertex {
  return {
    geozoneId: readU8(dv, 0),
    vertexIdx: dv.byteLength > 1 ? readU8(dv, 1) : 0,
    lat: dv.byteLength > 5 ? readS32(dv, 2) / 1e7 : 0,
    lon: dv.byteLength > 9 ? readS32(dv, 6) / 1e7 : 0,
  };
}
