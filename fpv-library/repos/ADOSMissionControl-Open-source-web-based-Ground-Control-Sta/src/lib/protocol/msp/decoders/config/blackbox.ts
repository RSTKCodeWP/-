/**
 * MSP blackbox and dataflash decoders.
 *
 * @module protocol/msp/decoders/config/blackbox
 */

import { readU8, readU16, readU32 } from '../../msp-decode-utils';

export interface MspBlackboxConfig {
  supported: boolean;
  device: number;
  rateNum: number;
  rateDenom: number;
  pDenom: number;
  sampleRate: number;
}

export interface MspDataflashSummary {
  ready: boolean;
  supported: boolean;
  sectors: number;
  totalSize: number;
  usedSize: number;
}

/**
 * MSP_BLACKBOX_CONFIG (80)
 *
 *   U8  supported (bit 0)
 *   U8  device
 *   U8  rateNum
 *   U8  rateDenom
 *   U16 pDenom
 *   U8  sampleRate
 */
export function decodeMspBlackboxConfig(dv: DataView): MspBlackboxConfig {
  return {
    supported: (readU8(dv, 0) & 1) !== 0,
    device: readU8(dv, 1),
    rateNum: readU8(dv, 2),
    rateDenom: readU8(dv, 3),
    pDenom: readU16(dv, 4),
    sampleRate: readU8(dv, 6),
  };
}

/**
 * MSP_DATAFLASH_SUMMARY (70)
 *
 *   U8  flags (bit0=ready, bit1=supported)
 *   U32 sectors
 *   U32 totalSize
 *   U32 usedSize
 */
export function decodeMspDataflashSummary(dv: DataView): MspDataflashSummary {
  if (dv.byteLength < 13) {
    return { ready: false, supported: false, sectors: 0, totalSize: 0, usedSize: 0 };
  }
  const flags = readU8(dv, 0);
  return {
    ready: (flags & 1) !== 0,
    supported: (flags & 2) !== 0,
    sectors: readU32(dv, 1),
    totalSize: readU32(dv, 5),
    usedSize: readU32(dv, 9),
  };
}
