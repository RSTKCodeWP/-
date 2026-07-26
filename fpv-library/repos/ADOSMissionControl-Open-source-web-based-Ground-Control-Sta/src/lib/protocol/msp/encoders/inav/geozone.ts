/**
 * iNav geozone and vertex encoders.
 *
 * @module protocol/msp/encoders/inav/geozone
 */

import type { INavGeozone, INavGeozoneVertex } from '../../msp-decoders-inav';
import { writeU8, writeS32 } from './_helpers';

/**
 * Encode MSP2_INAV_SET_GEOZONE (0x2203) payload.
 *
 * U8  number (geozone index)
 * U8  type   (0=EXCLUSIVE, 1=INCLUSIVE)
 * U8  shape  (0=CIRCULAR, 1=POLYGON)
 * S32 minAlt (cm)
 * S32 maxAlt (cm)
 * U8  fenceAction
 * U8  vertexCount
 * U8  isSeaLevelRef (bool)
 * U8  enabled (bool)
 */
export function encodeMspINavSetGeozone(g: INavGeozone): Uint8Array {
  const buf = new Uint8Array(14);
  const dv = new DataView(buf.buffer);

  writeU8(dv, 0, g.number);
  writeU8(dv, 1, g.type);
  writeU8(dv, 2, g.shape);
  writeS32(dv, 3, g.minAlt);
  writeS32(dv, 7, g.maxAlt);
  writeU8(dv, 11, g.fenceAction);
  writeU8(dv, 12, g.vertexCount);
  writeU8(dv, 13, g.isSeaLevelRef ? 1 : 0);
  // enabled is not part of the SET payload (controlled by vertex presence)

  return buf;
}

/**
 * Encode MSP2_INAV_SET_GEOZONE_VERTEX (0x2205) payload.
 *
 * U8  geozoneId
 * U8  vertexIdx
 * S32 lat (degrees x 1e7)
 * S32 lon (degrees x 1e7)
 */
export function encodeMspINavSetGeozoneVertex(v: INavGeozoneVertex): Uint8Array {
  const buf = new Uint8Array(10);
  const dv = new DataView(buf.buffer);

  writeU8(dv, 0, v.geozoneId);
  writeU8(dv, 1, v.vertexIdx);
  writeS32(dv, 2, Math.round(v.lat * 1e7));
  writeS32(dv, 6, Math.round(v.lon * 1e7));

  return buf;
}
