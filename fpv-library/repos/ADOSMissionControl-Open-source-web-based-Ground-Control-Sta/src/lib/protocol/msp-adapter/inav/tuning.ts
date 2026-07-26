/**
 * iNav tuning adapter functions: MC braking, rate dynamics, EZ-Tune.
 *
 * @module protocol/msp-adapter/inav/tuning
 */

import type { CommandResult } from '../../types'
import type { MspSerialQueue } from '../../msp/msp-serial-queue'
import { formatErrorMessage } from '@/lib/utils'
import {
  INAV_MSP,
  decodeMspINavMcBraking,
  decodeMspINavRateDynamics,
  decodeMspINavEzTune,
  type INavMcBraking,
  type INavRateDynamics,
  type INavEzTune,
} from '../../msp/msp-decoders-inav'
import {
  encodeMspINavSetMcBraking,
  encodeMspINavSetRateDynamics,
  encodeMspINavSetEzTune,
} from '../../msp/msp-encoders-inav'
import { NOT_CONNECTED, dv } from './helpers'

export async function inavGetMcBraking(queue: MspSerialQueue | null): Promise<INavMcBraking> {
  if (!queue) throw new Error('Not connected')
  const frame = await queue.send(INAV_MSP.MSP2_INAV_MC_BRAKING)
  return decodeMspINavMcBraking(dv(frame.payload))
}

export async function inavSetMcBraking(queue: MspSerialQueue | null, b: INavMcBraking): Promise<CommandResult> {
  if (!queue) return NOT_CONNECTED
  try {
    await queue.send(INAV_MSP.MSP2_INAV_SET_MC_BRAKING, encodeMspINavSetMcBraking(b))
    return { success: true, resultCode: 0, message: 'Braking config saved' }
  } catch (err) {
    return { success: false, resultCode: -1, message: formatErrorMessage(err) }
  }
}

// ── Rate dynamics ────────────────────────────────────────────

export async function inavGetRateDynamics(queue: MspSerialQueue | null): Promise<INavRateDynamics> {
  if (!queue) throw new Error('Not connected')
  const frame = await queue.send(INAV_MSP.MSP2_INAV_RATE_DYNAMICS)
  return decodeMspINavRateDynamics(dv(frame.payload))
}

export async function inavSetRateDynamics(queue: MspSerialQueue | null, r: INavRateDynamics): Promise<CommandResult> {
  if (!queue) return NOT_CONNECTED
  try {
    await queue.send(INAV_MSP.MSP2_INAV_SET_RATE_DYNAMICS, encodeMspINavSetRateDynamics(r))
    return { success: true, resultCode: 0, message: 'Rate dynamics saved' }
  } catch (err) {
    return { success: false, resultCode: -1, message: formatErrorMessage(err) }
  }
}

// ── EZ Tune ──────────────────────────────────────────────────

export async function inavGetEzTune(queue: MspSerialQueue | null): Promise<INavEzTune> {
  if (!queue) throw new Error('Not connected')
  const frame = await queue.send(INAV_MSP.MSP2_INAV_EZ_TUNE)
  return decodeMspINavEzTune(dv(frame.payload))
}

export async function inavSetEzTune(queue: MspSerialQueue | null, cfg: INavEzTune): Promise<CommandResult> {
  if (!queue) return NOT_CONNECTED
  try {
    await queue.send(INAV_MSP.MSP2_INAV_EZ_TUNE_SET, encodeMspINavSetEzTune(cfg))
    return { success: true, resultCode: 0, message: 'EZ Tune saved' }
  } catch (err) {
    return { success: false, resultCode: -1, message: formatErrorMessage(err) }
  }
}

// ── FW Approach ──────────────────────────────────────────────

