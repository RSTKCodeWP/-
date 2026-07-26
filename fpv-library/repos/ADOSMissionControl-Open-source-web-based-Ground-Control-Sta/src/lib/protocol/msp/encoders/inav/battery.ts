/**
 * iNav battery config encoder.
 *
 * @module protocol/msp/encoders/inav/battery
 */

import type { INavBatteryConfig } from '../../msp-decoders-inav';
import { writeU8, writeU16, writeU32 } from './_helpers';

/**
 * Encode MSP2_INAV_SET_BATTERY_CONFIG (0x200F) payload.
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
export function encodeMspINavSetBatteryConfig(cfg: INavBatteryConfig): Uint8Array {
  const buf = new Uint8Array(26);
  const dv = new DataView(buf.buffer);

  writeU32(dv, 0, cfg.capacityMah);
  writeU32(dv, 4, cfg.capacityWarningMah);
  writeU32(dv, 8, cfg.capacityCriticalMah);
  writeU8(dv, 12, cfg.capacityUnit);
  writeU8(dv, 13, cfg.voltageSource);
  writeU8(dv, 14, cfg.cells);
  writeU8(dv, 15, cfg.cellDetect);
  writeU16(dv, 16, cfg.cellMin);
  writeU16(dv, 18, cfg.cellMax);
  writeU16(dv, 20, cfg.cellWarning);
  writeU16(dv, 22, cfg.currentScale);
  writeU16(dv, 24, cfg.currentOffset);

  return buf;
}
