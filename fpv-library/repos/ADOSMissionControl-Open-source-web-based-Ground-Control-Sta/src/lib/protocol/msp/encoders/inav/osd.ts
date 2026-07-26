/**
 * iNav OSD encoders: alarms, preferences, custom OSD elements.
 *
 * @module protocol/msp/encoders/inav/osd
 */

import type { INavOsdAlarms, INavOsdPreferences } from '../../msp-decoders-inav';

/**
 * Encode MSP2_INAV_OSD_SET_ALARMS (0x2015) payload.
 *
 * 28 bytes matching decodeMspINavOsdAlarms layout:
 * U8 rssi, U16 flyMinutes, U16 maxAltitude, U16 distance,
 * U16 maxNegAltitude, U16 gforce, S16 gforceAxisMin, S16 gforceAxisMax,
 * U8 current, S16 imuTempMin, S16 imuTempMax,
 * S16 baroTempMin, S16 baroTempMax, S16 adsbDistanceWarning, S16 adsbDistanceAlert
 */
export function encodeMspINavSetOsdAlarms(a: INavOsdAlarms): Uint8Array {
  const buf = new ArrayBuffer(28);
  const dv = new DataView(buf);
  dv.setUint8(0, a.rssi);
  dv.setUint16(1, a.flyMinutes, true);
  dv.setUint16(3, a.maxAltitude, true);
  dv.setUint16(5, a.distance, true);
  dv.setUint16(7, a.maxNegAltitude, true);
  dv.setUint16(9, a.gforce, true);
  dv.setInt16(11, a.gforceAxisMin, true);
  dv.setInt16(13, a.gforceAxisMax, true);
  dv.setUint8(15, a.current);
  dv.setInt16(16, a.imuTempMin, true);
  dv.setInt16(18, a.imuTempMax, true);
  dv.setInt16(20, a.baroTempMin, true);
  dv.setInt16(22, a.baroTempMax, true);
  dv.setInt16(24, a.adsbDistanceWarning, true);
  dv.setInt16(26, a.adsbDistanceAlert, true);
  return new Uint8Array(buf);
}

/**
 * Encode MSP2_INAV_OSD_SET_PREFERENCES (0x2017) payload.
 *
 * 10 bytes matching decodeMspINavOsdPreferences layout.
 */
export function encodeMspINavSetOsdPreferences(p: INavOsdPreferences): Uint8Array {
  return new Uint8Array([
    p.videoSystem,
    p.mainVoltageDecimals,
    p.ahiReverseRoll,
    p.crosshairsStyle,
    p.leftSidebarScroll,
    p.rightSidebarScroll,
    p.sidebarScrollArrows,
    p.units,
    p.statsEnergyUnit,
    p.adsbWarningStyle,
  ]);
}

/**
 * Encode MSP2_INAV_SET_CUSTOM_OSD_ELEMENTS (0x2102) payload for one element.
 *
 * U8  index
 * U8  visible (0/1)
 * 16 bytes ASCII text (null-padded, not null-terminated in strict sense)
 */
export function encodeMspINavSetCustomOsdElement(el: {
  index: number;
  visible: boolean;
  text: string;
}): Uint8Array {
  const TEXT_LEN = 16;
  const buf = new Uint8Array(2 + TEXT_LEN);
  buf[0] = el.index & 0xff;
  buf[1] = el.visible ? 1 : 0;
  const truncated = el.text.slice(0, TEXT_LEN);
  for (let i = 0; i < truncated.length; i++) {
    buf[2 + i] = truncated.charCodeAt(i) & 0x7f;
  }
  return buf;
}
