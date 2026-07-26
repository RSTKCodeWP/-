/**
 * MSP payload encoders for navigation: GPS config and GPS Rescue tuning.
 *
 * @module protocol/msp/encoders/nav
 */

import { makeBuffer, push8, push16 } from "./helpers";

/**
 * MSP_SET_GPS_CONFIG (223)
 *   U8 provider
 *   U8 sbasMode
 *   U8 autoConfig
 *   U8 autoBaud
 *   U8 homePointOnce
 *   U8 ubloxUseGalileo
 */
export function encodeMspSetGpsConfig(config: {
  provider: number;
  sbasMode: number;
  autoConfig: number;
  autoBaud: number;
  homePointOnce: number;
  ubloxUseGalileo: number;
}): Uint8Array {
  const { buf, dv } = makeBuffer(6);
  push8(dv, 0, config.provider);
  push8(dv, 1, config.sbasMode);
  push8(dv, 2, config.autoConfig);
  push8(dv, 3, config.autoBaud);
  push8(dv, 4, config.homePointOnce);
  push8(dv, 5, config.ubloxUseGalileo);
  return buf;
}


/**
 * MSP_SET_GPS_RESCUE (225)
 *
 * From MSPHelper.js crunch:
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
export function encodeMspSetGpsRescue(config: {
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
}): Uint8Array {
  const { buf, dv } = makeBuffer(22);
  push16(dv, 0, config.angle);
  push16(dv, 2, config.initialAltitudeM);
  push16(dv, 4, config.descentDistanceM);
  push16(dv, 6, config.groundSpeed);
  push16(dv, 8, config.throttleMin);
  push16(dv, 10, config.throttleMax);
  push16(dv, 12, config.throttleHover);
  push8(dv, 14, config.sanityChecks);
  push8(dv, 15, config.minSats);
  push16(dv, 16, config.ascendRate);
  push16(dv, 18, config.descendRate);
  push8(dv, 20, config.allowArmingWithoutFix);
  push8(dv, 21, config.altitudeMode);
  return buf;
}

