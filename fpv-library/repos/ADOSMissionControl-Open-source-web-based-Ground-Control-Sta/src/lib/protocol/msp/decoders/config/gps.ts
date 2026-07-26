/**
 * MSP GPS config and GPS rescue decoders.
 *
 * @module protocol/msp/decoders/config/gps
 */

import { readU8, readU16 } from '../../msp-decode-utils';

export interface MspGpsConfig {
  provider: number;
  sbasMode: number;
  autoConfig: number;
  autoBaud: number;
  homePointOnce: number;
  ubloxUseGalileo: number;
}

export interface MspGpsRescue {
  angle: number;
  initialAltitudeM: number;
  descentDistanceM: number;
  groundSpeed: number;
  throttleMin: number;
  throttleMax: number;
  throttleHover: number;
  sanityChecks: number;
  minSats: number;
  ascendRate: number;
  descendRate: number;
  allowArmingWithoutFix: number;
  altitudeMode: number;
}

/**
 * MSP_GPS_CONFIG (132)
 *   U8 provider
 *   U8 sbasMode
 *   U8 autoConfig
 *   U8 autoBaud
 *   U8 homePointOnce
 *   U8 ubloxUseGalileo
 */
export function decodeMspGpsConfig(dv: DataView): MspGpsConfig {
  return {
    provider: readU8(dv, 0),
    sbasMode: readU8(dv, 1),
    autoConfig: readU8(dv, 2),
    autoBaud: readU8(dv, 3),
    homePointOnce: readU8(dv, 4),
    ubloxUseGalileo: readU8(dv, 5),
  };
}

/**
 * MSP_GPS_RESCUE (135)
 *
 *   U16 angle
 *   U16 returnAltitudeM
 *   U16 descentDistanceM
 *   U16 groundSpeed
 *   U16 throttleMin
 *   U16 throttleMax
 *   U16 throttleHover
 *   U8  sanityChecks
 *   U8  minSats
 *   U16 ascendRate
 *   U16 descendRate
 *   U8  allowArmingWithoutFix
 *   U8  altitudeMode
 */
export function decodeMspGpsRescue(dv: DataView): MspGpsRescue {
  return {
    angle: readU16(dv, 0),
    initialAltitudeM: readU16(dv, 2),
    descentDistanceM: readU16(dv, 4),
    groundSpeed: readU16(dv, 6),
    throttleMin: readU16(dv, 8),
    throttleMax: readU16(dv, 10),
    throttleHover: readU16(dv, 12),
    sanityChecks: readU8(dv, 14),
    minSats: readU8(dv, 15),
    ascendRate: readU16(dv, 16),
    descendRate: readU16(dv, 18),
    allowArmingWithoutFix: readU8(dv, 20),
    altitudeMode: readU8(dv, 21),
  };
}
