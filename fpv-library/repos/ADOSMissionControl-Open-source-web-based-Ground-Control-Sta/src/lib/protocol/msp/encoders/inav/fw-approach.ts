/**
 * iNav fixed-wing approach encoder.
 *
 * @module protocol/msp/encoders/inav/fw-approach
 */

import type { INavFwApproach } from '../../msp-decoders-inav';
import { writeU8, writeS32 } from './_helpers';

/**
 * Encode MSP2_INAV_SET_FW_APPROACH (0x204b) payload.
 *
 * Per approach slot (15 bytes each):
 *   U8  number
 *   S32 approachAlt (cm)
 *   S32 landAlt (cm)
 *   U8  approachDirection
 *   S16 landHeading1
 *   S16 landHeading2
 *   U8  isSeaLevelRef (0/1)
 */
export function encodeMspINavSetFwApproach(a: INavFwApproach): Uint8Array {
  const buf = new Uint8Array(15);
  const dv = new DataView(buf.buffer);
  writeU8(dv, 0, a.number & 0xff);
  writeS32(dv, 1, a.approachAlt);
  writeS32(dv, 5, a.landAlt);
  writeU8(dv, 9, a.approachDirection & 0xff);
  dv.setInt16(10, a.landHeading1, true);
  dv.setInt16(12, a.landHeading2, true);
  writeU8(dv, 14, a.isSeaLevelRef ? 1 : 0);
  return buf;
}
