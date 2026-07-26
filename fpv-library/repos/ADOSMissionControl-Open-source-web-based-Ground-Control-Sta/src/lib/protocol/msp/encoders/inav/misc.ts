/**
 * iNav misc config encoder.
 *
 * @module protocol/msp/encoders/inav/misc
 */

import type { INavMisc } from '../../msp-decoders-inav';
import { writeU8, writeU16 } from './_helpers';

/**
 * Encode MSP2_INAV_SET_MISC (0x2004) payload.
 *
 * U16 midrc
 * U16 minthrottle
 * U16 maxthrottle
 * U16 mincommand
 * U16 failsafeThrottle
 * U8  gpsProvider
 * U8  gpsBaudrateIdx
 * U8  gpsUbxSbas
 * U8  multiwiiCurrentOutput
 * U8  rssiChannel
 * U8  placeholder
 * S16 magDeclination (degrees x 10)
 * U8  voltageScale
 * U8  cellMin (x 10)
 * U8  cellMax (x 10)
 * U8  cellWarning (x 10)
 */
export function encodeMspINavSetMisc(misc: INavMisc): Uint8Array {
  const buf = new Uint8Array(22);
  const dv = new DataView(buf.buffer);

  writeU16(dv, 0, misc.midrc);
  writeU16(dv, 2, misc.minthrottle);
  writeU16(dv, 4, misc.maxthrottle);
  writeU16(dv, 6, misc.mincommand);
  writeU16(dv, 8, misc.failsafeThrottle);
  writeU8(dv, 10, misc.gpsProvider);
  writeU8(dv, 11, misc.gpsBaudrateIdx);
  writeU8(dv, 12, misc.gpsUbxSbas);
  writeU8(dv, 13, misc.multiwiiCurrentOutput);
  writeU8(dv, 14, misc.rssiChannel);
  writeU8(dv, 15, misc.placeholder);
  writeU16(dv, 16, misc.magDeclination);
  writeU8(dv, 18, misc.voltageScale);
  writeU8(dv, 19, misc.cellMin);
  writeU8(dv, 20, misc.cellMax);
  writeU8(dv, 21, misc.cellWarning);

  return buf;
}
