/**
 * iNav battery adapter functions: config read/write + profile selection.
 *
 * @module protocol/msp-adapter/inav/battery
 */

import type { CommandResult } from '../../types'
import type { MspSerialQueue } from '../../msp/msp-serial-queue'
import { formatErrorMessage } from '@/lib/utils'
import {
  INAV_MSP,
  decodeMspINavBatteryConfig,
  type INavBatteryConfig,
} from '../../msp/msp-decoders-inav'
import {
  encodeMspINavSetBatteryConfig,
  encodeMspINavSelectBatteryProfile,
} from '../../msp/msp-encoders-inav'
import { NOT_CONNECTED, dv } from './helpers'

export async function inavGetBatteryConfig(queue: MspSerialQueue | null): Promise<INavBatteryConfig> {
  if (!queue) throw new Error('Not connected')
  const frame = await queue.send(INAV_MSP.MSP2_INAV_BATTERY_CONFIG)
  return decodeMspINavBatteryConfig(dv(frame.payload))
}

export async function inavSetBatteryConfig(queue: MspSerialQueue | null, cfg: INavBatteryConfig): Promise<CommandResult> {
  if (!queue) return NOT_CONNECTED
  try {
    await queue.send(INAV_MSP.MSP2_INAV_SET_BATTERY_CONFIG, encodeMspINavSetBatteryConfig(cfg))
    return { success: true, resultCode: 0, message: 'Battery config saved' }
  } catch (err) {
    return { success: false, resultCode: -1, message: formatErrorMessage(err) }
  }
}

export async function inavSelectBatteryProfile(queue: MspSerialQueue | null, idx: number): Promise<CommandResult> {
  if (!queue) return NOT_CONNECTED
  try {
    await queue.send(INAV_MSP.MSP2_INAV_SELECT_BATTERY_PROFILE, encodeMspINavSelectBatteryProfile(idx))
    return { success: true, resultCode: 0, message: `Battery profile ${idx} selected` }
  } catch (err) {
    return { success: false, resultCode: -1, message: formatErrorMessage(err) }
  }
}

// ── Mixer config ─────────────────────────────────────────────

