/**
 * MSP2 common settings encoders (name-based settings system).
 *
 * @module protocol/msp/encoders/inav/settings
 */

import { writeCString } from './_helpers';

/**
 * Encode MSP2_COMMON_SETTING request payload.
 * Payload is the setting name as a null-terminated ASCII string.
 */
export function encodeCommonSetting(name: string): Uint8Array {
  const buf = new Uint8Array(name.length + 1);
  writeCString(buf, 0, name);
  return buf;
}

/**
 * Encode MSP2_COMMON_SET_SETTING payload.
 * Layout: name (null-terminated string) followed immediately by rawValue bytes.
 */
export function encodeCommonSetSetting(name: string, rawValue: Uint8Array): Uint8Array {
  const nameLen = name.length + 1; // +1 for null terminator
  const buf = new Uint8Array(nameLen + rawValue.length);
  writeCString(buf, 0, name);
  buf.set(rawValue, nameLen);
  return buf;
}

/**
 * Encode MSP2_COMMON_SETTING_INFO request payload.
 * Payload is the setting name as a null-terminated ASCII string.
 */
export function encodeCommonSettingInfo(name: string): Uint8Array {
  const buf = new Uint8Array(name.length + 1);
  writeCString(buf, 0, name);
  return buf;
}

/**
 * Encode MSP2_COMMON_SETTING_INFO request payload BY INDEX.
 * The firmware treats a leading 0x00 byte as "by index" mode, followed by the
 * little-endian uint16 setting index (vs a non-empty null-terminated name).
 */
export function encodeCommonSettingInfoByIndex(index: number): Uint8Array {
  const buf = new Uint8Array(3);
  buf[0] = 0;
  new DataView(buf.buffer).setUint16(1, index & 0xffff, true);
  return buf;
}
