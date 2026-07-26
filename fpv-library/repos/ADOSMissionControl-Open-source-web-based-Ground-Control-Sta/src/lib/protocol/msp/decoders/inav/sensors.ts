/**
 * iNav sensor decoders: air speed, temperature sensor config, raw
 * temperatures, and the ADS-B vehicle list.
 *
 * @module protocol/msp/decoders/inav/sensors
 */

import { readU8, readU16, readU32, readS16, readS32, readCString } from "./helpers";
import type {
  INavAirSpeed,
  INavTempSensorConfigEntry,
  INavAdsbVehicle,
} from "./types";

// ── iNav AIR SPEED decoder ───────────────────────────────────

/**
 * MSP2_INAV_AIR_SPEED (0x2009)
 *
 * U32 airspeed (cm/s)
 */
export function decodeMspINavAirSpeed(dv: DataView): INavAirSpeed {
  return {
    airSpeedCmS: readU32(dv, 0),
  };
}

// ── iNav TEMP SENSOR CONFIG decoder ──────────────────────────

/**
 * MSP2_INAV_TEMP_SENSOR_CONFIG (0x201c)
 *
 * Repeated for each sensor:
 *   U8   type
 *   U8[8] address
 *   S16  alarmMin (tenths of degree C)
 *   S16  alarmMax (tenths of degree C)
 *   char[4] label (null-padded, not null-terminated)
 */
export function decodeMspINavTempSensorConfig(dv: DataView): INavTempSensorConfigEntry[] {
  const ENTRY_SIZE = 16; // 1 + 8 + 2 + 2 + 4 (but label may be 4 chars fixed)
  const result: INavTempSensorConfigEntry[] = [];
  let offset = 0;
  while (offset + ENTRY_SIZE <= dv.byteLength) {
    const type = readU8(dv, offset);
    const address: number[] = [];
    for (let i = 0; i < 8; i++) address.push(readU8(dv, offset + 1 + i));
    const alarmMin = readS16(dv, offset + 9);
    const alarmMax = readS16(dv, offset + 11);
    // 4-byte null-padded label
    let label = '';
    for (let i = 0; i < 4; i++) {
      const ch = readU8(dv, offset + 13 + i);
      if (ch !== 0) label += String.fromCharCode(ch);
    }
    result.push({ type, address, alarmMin, alarmMax, label });
    offset += ENTRY_SIZE;
  }
  return result;
}

// ── iNav TEMPERATURES decoder ────────────────────────────────

/**
 * MSP2_INAV_TEMPERATURES (0x201e)
 *
 * S16[8] temperatures (tenths of degree C; 0x8000 = sensor not present)
 */
export function decodeMspINavTemperatures(dv: DataView): number[] {
  const result: number[] = [];
  for (let i = 0; i < 8; i++) {
    result.push(dv.byteLength >= (i + 1) * 2 ? readS16(dv, i * 2) : 0x8000);
  }
  return result;
}

// ── MSP2 ADSB VEHICLE LIST decoder ───────────────────────────

/**
 * MSP2_ADSB_VEHICLE_LIST (0x2090)
 *
 * Repeated per vehicle:
 *   char[9] callsign (null-terminated, max 8 chars + null)
 *   U32     icao
 *   S32     lat (degrees x 1e7)
 *   S32     lon (degrees x 1e7)
 *   S32     alt (cm)
 *   U16     heading (degrees x 10)
 *   U32     lastSeenMs
 *   U8      emitterType
 *   U8      ttlSec
 */
export function decodeMspAdsbVehicleList(dv: DataView): INavAdsbVehicle[] {
  const result: INavAdsbVehicle[] = [];
  let offset = 0;
  while (offset + 9 < dv.byteLength) {
    const [callsign, csLen] = readCString(dv, offset);
    offset += csLen;
    if (offset + 24 > dv.byteLength) break;
    result.push({
      callsign,
      icao: readU32(dv, offset),
      lat: readS32(dv, offset + 4) / 1e7,
      lon: readS32(dv, offset + 8) / 1e7,
      alt: readS32(dv, offset + 12),
      heading: readU16(dv, offset + 16) / 10,
      lastSeenMs: readU32(dv, offset + 18),
      emitterType: readU8(dv, offset + 22),
      ttlSec: readU8(dv, offset + 23),
    });
    offset += 24;
  }
  return result;
}
