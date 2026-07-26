/**
 * MSP failsafe config decoder.
 *
 * @module protocol/msp/decoders/config/failsafe
 */

import { readU8, readU16 } from '../../msp-decode-utils';

export interface MspFailsafeConfig {
  delay: number;
  offDelay: number;
  throttle: number;
  switchMode: number;
  throttleLowDelay: number;
  procedure: number;
}

/**
 * MSP_FAILSAFE_CONFIG (75)
 *   U8  delay
 *   U8  offDelay
 *   U16 throttle
 *   U8  switchMode
 *   U16 throttleLowDelay
 *   U8  procedure
 */
export function decodeMspFailsafeConfig(dv: DataView): MspFailsafeConfig {
  return {
    delay: readU8(dv, 0),
    offDelay: readU8(dv, 1),
    throttle: readU16(dv, 2),
    switchMode: readU8(dv, 4),
    throttleLowDelay: readU16(dv, 5),
    procedure: readU8(dv, 7),
  };
}
