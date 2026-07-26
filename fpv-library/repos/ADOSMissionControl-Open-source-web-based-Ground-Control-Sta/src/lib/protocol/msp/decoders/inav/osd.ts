/**
 * iNav OSD decoders: layouts header, field alarms, and preferences.
 *
 * @module protocol/msp/decoders/inav/osd
 */

import { readU8, readU16, readS16 } from "./helpers";
import type { INavOsdLayoutsHeader, INavOsdAlarms, INavOsdPreferences } from "./types";

// ── iNav OSD decoders ────────────────────────────────────────

/**
 * MSP2_INAV_OSD_LAYOUTS (0x2012) - header only.
 *
 * U8  layoutCount
 * U8  itemCount
 * U8  variant
 */
export function decodeMspINavOsdLayoutsHeader(dv: DataView): INavOsdLayoutsHeader {
  return {
    layoutCount: readU8(dv, 0),
    itemCount: dv.byteLength > 1 ? readU8(dv, 1) : 0,
    variant: dv.byteLength > 2 ? readU8(dv, 2) : 0,
  };
}

/**
 * MSP2_INAV_OSD_ALARMS (0x2014)
 *
 * 26 bytes total:
 * U8  rssi, U16 flyMinutes, U16 maxAltitude, U16 distance,
 * U16 maxNegAltitude, U16 gforce, S16 gforceAxisMin, S16 gforceAxisMax,
 * U8  current, S16 imuTempMin, S16 imuTempMax,
 * S16 baroTempMin, S16 baroTempMax, S16 adsbDistanceWarning, S16 adsbDistanceAlert
 */
export function decodeMspINavOsdAlarms(dv: DataView): INavOsdAlarms {
  if (dv.byteLength < 26) {
    return {
      rssi: 0, flyMinutes: 0, maxAltitude: 0, distance: 0,
      maxNegAltitude: 0, gforce: 0, gforceAxisMin: 0, gforceAxisMax: 0,
      current: 0, imuTempMin: 0, imuTempMax: 0,
      baroTempMin: 0, baroTempMax: 0, adsbDistanceWarning: 0, adsbDistanceAlert: 0,
    };
  }
  return {
    rssi:                readU8(dv, 0),
    flyMinutes:          readU16(dv, 1),
    maxAltitude:         readU16(dv, 3),
    distance:            readU16(dv, 5),
    maxNegAltitude:      readU16(dv, 7),
    gforce:              readU16(dv, 9),
    gforceAxisMin:       readS16(dv, 11),
    gforceAxisMax:       readS16(dv, 13),
    current:             readU8(dv, 15),
    imuTempMin:          readS16(dv, 16),
    imuTempMax:          readS16(dv, 18),
    baroTempMin:         readS16(dv, 20),
    baroTempMax:         readS16(dv, 22),
    adsbDistanceWarning: readS16(dv, 24),
    adsbDistanceAlert:   dv.byteLength >= 28 ? readS16(dv, 26) : 0,
  };
}

/**
 * MSP2_INAV_OSD_PREFERENCES (0x2016)
 *
 * 10 bytes: videoSystem, mainVoltageDecimals, ahiReverseRoll,
 * crosshairsStyle, leftSidebarScroll, rightSidebarScroll,
 * sidebarScrollArrows, units, statsEnergyUnit, adsbWarningStyle
 */
export function decodeMspINavOsdPreferences(dv: DataView): INavOsdPreferences {
  const u = (o: number) => dv.byteLength > o ? readU8(dv, o) : 0;
  return {
    videoSystem:          u(0),
    mainVoltageDecimals:  u(1),
    ahiReverseRoll:       u(2),
    crosshairsStyle:      u(3),
    leftSidebarScroll:    u(4),
    rightSidebarScroll:   u(5),
    sidebarScrollArrows:  u(6),
    units:                u(7),
    statsEnergyUnit:      u(8),
    adsbWarningStyle:     u(9),
  };
}
