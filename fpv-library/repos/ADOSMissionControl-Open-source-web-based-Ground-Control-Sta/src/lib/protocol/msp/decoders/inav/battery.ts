/**
 * iNav battery/power decoders: analog telemetry and battery config.
 *
 * @module protocol/msp/decoders/inav/battery
 */

import { readU8, readU16, readU32 } from "./helpers";
import type { INavAnalog, INavBatteryConfig } from "./types";

// ── iNav ANALOG decoder ──────────────────────────────────────

/**
 * MSP2_INAV_ANALOG (0x2002)
 *
 * U8  flags
 * U16 voltage (mV, divide by 1000 for volts)
 * U32 mAhDrawn
 * U16 rssiPct (0-100)
 * U32 amperage (mA, divide by 1000 for amps)
 * U32 powerMw
 * U32 mWhDrawn
 * U8  batteryPercent (0-100)
 */
export function decodeMspINavAnalog(dv: DataView): INavAnalog {
  return {
    flags: readU8(dv, 0),
    voltage: (dv.byteLength > 2 ? readU16(dv, 1) : 0) / 1000,
    mAhDrawn: dv.byteLength > 6 ? readU32(dv, 3) : 0,
    rssiPct: dv.byteLength > 8 ? readU16(dv, 7) : 0,
    amperage: (dv.byteLength > 12 ? readU32(dv, 9) : 0) / 1000,
    powerMw: dv.byteLength > 16 ? readU32(dv, 13) : 0,
    mWhDrawn: dv.byteLength > 20 ? readU32(dv, 17) : 0,
    batteryPercent: dv.byteLength > 21 ? readU8(dv, 21) : 0,
  };
}

// ── iNav BATTERY CONFIG decoder ──────────────────────────────

/**
 * MSP2_INAV_BATTERY_CONFIG (0x2005)
 *
 * U32 capacityMah
 * U32 capacityWarningMah
 * U32 capacityCriticalMah
 * U8  capacityUnit
 * U8  voltageSource
 * U8  cells
 * U8  cellDetect
 * U16 cellMin (mV)
 * U16 cellMax (mV)
 * U16 cellWarning (mV)
 * U16 currentScale
 * U16 currentOffset
 */
export function decodeMspINavBatteryConfig(dv: DataView): INavBatteryConfig {
  return {
    capacityMah: readU32(dv, 0),
    capacityWarningMah: dv.byteLength > 7 ? readU32(dv, 4) : 0,
    capacityCriticalMah: dv.byteLength > 11 ? readU32(dv, 8) : 0,
    capacityUnit: dv.byteLength > 12 ? readU8(dv, 12) : 0,
    voltageSource: dv.byteLength > 13 ? readU8(dv, 13) : 0,
    cells: dv.byteLength > 14 ? readU8(dv, 14) : 0,
    cellDetect: dv.byteLength > 15 ? readU8(dv, 15) : 0,
    cellMin: dv.byteLength > 17 ? readU16(dv, 16) : 0,
    cellMax: dv.byteLength > 19 ? readU16(dv, 18) : 0,
    cellWarning: dv.byteLength > 21 ? readU16(dv, 20) : 0,
    currentScale: dv.byteLength > 23 ? readU16(dv, 22) : 0,
    currentOffset: dv.byteLength > 25 ? readU16(dv, 24) : 0,
  };
}
