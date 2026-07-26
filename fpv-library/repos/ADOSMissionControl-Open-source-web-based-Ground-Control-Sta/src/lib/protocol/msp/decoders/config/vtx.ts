/**
 * MSP VTX config decoder.
 *
 * @module protocol/msp/decoders/config/vtx
 */

import { readU8, readU16 } from '../../msp-decode-utils';

export interface MspVtxConfig {
  type: number;
  band: number;
  channel: number;
  power: number;
  pitMode: boolean;
  frequency: number;
  deviceReady: boolean;
  lowPowerDisarm: number;
  pitModeFrequency: number;
  vtxTableAvailable: boolean;
  vtxTableBands: number;
  vtxTableChannels: number;
  vtxTablePowerLevels: number;
}

/**
 * MSP_VTX_CONFIG (88)
 *
 *   U8  type
 *   U8  band
 *   U8  channel
 *   U8  power
 *   U8  pitMode (bool)
 *   U16 frequency
 *   U8  deviceReady (bool)
 *   U8  lowPowerDisarm
 *   U16 pitModeFrequency
 *   U8  vtxTableAvailable (bool)
 *   U8  vtxTableBands
 *   U8  vtxTableChannels
 *   U8  vtxTablePowerLevels
 */
export function decodeMspVtxConfig(dv: DataView): MspVtxConfig {
  return {
    type: readU8(dv, 0),
    band: readU8(dv, 1),
    channel: readU8(dv, 2),
    power: readU8(dv, 3),
    pitMode: readU8(dv, 4) !== 0,
    frequency: readU16(dv, 5),
    deviceReady: readU8(dv, 7) !== 0,
    lowPowerDisarm: readU8(dv, 8),
    pitModeFrequency: readU16(dv, 9),
    vtxTableAvailable: readU8(dv, 11) !== 0,
    vtxTableBands: readU8(dv, 12),
    vtxTableChannels: readU8(dv, 13),
    vtxTablePowerLevels: readU8(dv, 14),
  };
}
