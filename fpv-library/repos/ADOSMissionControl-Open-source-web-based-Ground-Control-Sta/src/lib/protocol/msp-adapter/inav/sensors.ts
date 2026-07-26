/**
 * iNav sensor adapter functions: temperature sensor config readout.
 *
 * @module protocol/msp-adapter/inav/sensors
 */

import type { MspSerialQueue } from '../../msp/msp-serial-queue'
import {
  INAV_MSP,
  decodeMspINavTempSensorConfig,
  type INavTempSensorConfigEntry,
} from '../../msp/msp-decoders-inav'
import { dv } from './helpers'

export async function inavGetTempSensorConfigs(queue: MspSerialQueue | null): Promise<INavTempSensorConfigEntry[]> {
  if (!queue) return []
  try {
    const frame = await queue.send(INAV_MSP.MSP2_INAV_TEMP_SENSOR_CONFIG)
    return decodeMspINavTempSensorConfig(dv(frame.payload))
  } catch { return [] }
}

// ── MC braking ───────────────────────────────────────────────

