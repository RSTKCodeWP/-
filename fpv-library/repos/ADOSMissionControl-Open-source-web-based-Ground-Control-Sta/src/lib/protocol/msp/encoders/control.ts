/**
 * MSP payload encoders for vehicle control: raw RC channels, reboot,
 * and blackbox logging config.
 *
 * @module protocol/msp/encoders/control
 */

import { makeBuffer, push8, push16 } from "./helpers";

/**
 * MSP_SET_RAW_RC (200)
 * U16 per channel
 */
export function encodeMspSetRawRc(channels: number[]): Uint8Array {
  const { buf, dv } = makeBuffer(channels.length * 2);
  for (let i = 0; i < channels.length; i++) {
    push16(dv, i * 2, channels[i]);
  }
  return buf;
}


/**
 * MSP_SET_REBOOT (68)
 * U8: 0=firmware, 1=bootloader, 2=MSC, 3=MSC_UTC, 4=bootloader_flash
 */
export function encodeMspSetReboot(type: number): Uint8Array {
  const { buf, dv } = makeBuffer(1);
  push8(dv, 0, type);
  return buf;
}


/**
 * MSP_SET_BLACKBOX_CONFIG (81)
 *
 * From MSPHelper.js crunch:
 *   U8  device
 *   U8  rateNum
 *   U8  rateDenom
 *   U16 pDenom
 *   U8  sampleRate
 */
export function encodeMspSetBlackboxConfig(config: {
  device: number;
  rateNum: number;
  rateDenom: number;
  pDenom: number;
  sampleRate: number;
}): Uint8Array {
  const { buf, dv } = makeBuffer(6);
  push8(dv, 0, config.device);
  push8(dv, 1, config.rateNum);
  push8(dv, 2, config.rateDenom);
  push16(dv, 3, config.pDenom);
  push8(dv, 5, config.sampleRate);
  return buf;
}
