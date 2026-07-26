/**
 * iNav OSD adapter functions: layouts header, alarms, preferences, custom elements.
 *
 * @module protocol/msp-adapter/inav/osd
 */

import type { CommandResult } from '../../types'
import type { MspSerialQueue } from '../../msp/msp-serial-queue'
import { formatErrorMessage } from '@/lib/utils'
import {
  INAV_MSP,
  decodeMspINavOsdLayoutsHeader,
  decodeMspINavOsdAlarms,
  decodeMspINavOsdPreferences,
  type INavOsdLayoutsHeader,
  type INavOsdAlarms,
  type INavOsdPreferences,
} from '../../msp/msp-decoders-inav'
import {
  encodeMspINavSetOsdAlarms,
  encodeMspINavSetOsdPreferences,
  encodeMspINavSetCustomOsdElement,
} from '../../msp/msp-encoders-inav'
import { NOT_CONNECTED, dv } from './helpers'

export async function inavGetOsdLayoutsHeader(queue: MspSerialQueue | null): Promise<INavOsdLayoutsHeader> {
  if (!queue) throw new Error('Not connected')
  const frame = await queue.send(INAV_MSP.MSP2_INAV_OSD_LAYOUTS)
  return decodeMspINavOsdLayoutsHeader(dv(frame.payload))
}

export async function inavGetOsdAlarms(queue: MspSerialQueue | null): Promise<INavOsdAlarms> {
  if (!queue) throw new Error('Not connected')
  const frame = await queue.send(INAV_MSP.MSP2_INAV_OSD_ALARMS)
  return decodeMspINavOsdAlarms(dv(frame.payload))
}

export async function inavSetOsdAlarms(queue: MspSerialQueue | null, a: INavOsdAlarms): Promise<CommandResult> {
  if (!queue) return NOT_CONNECTED
  try {
    await queue.send(INAV_MSP.MSP2_INAV_OSD_SET_ALARMS, encodeMspINavSetOsdAlarms(a))
    return { success: true, resultCode: 0, message: 'OSD alarms saved' }
  } catch (err) {
    return { success: false, resultCode: -1, message: formatErrorMessage(err) }
  }
}

export async function inavGetOsdPreferences(queue: MspSerialQueue | null): Promise<INavOsdPreferences> {
  if (!queue) throw new Error('Not connected')
  const frame = await queue.send(INAV_MSP.MSP2_INAV_OSD_PREFERENCES)
  return decodeMspINavOsdPreferences(dv(frame.payload))
}

export async function inavSetOsdPreferences(queue: MspSerialQueue | null, p: INavOsdPreferences): Promise<CommandResult> {
  if (!queue) return NOT_CONNECTED
  try {
    await queue.send(INAV_MSP.MSP2_INAV_OSD_SET_PREFERENCES, encodeMspINavSetOsdPreferences(p))
    return { success: true, resultCode: 0, message: 'OSD preferences saved' }
  } catch (err) {
    return { success: false, resultCode: -1, message: formatErrorMessage(err) }
  }
}

// ── Custom OSD elements ───────────────────────────────────────

export async function inavSetCustomOsdElement(
  queue: MspSerialQueue | null,
  el: { index: number; visible: boolean; text: string },
): Promise<CommandResult> {
  if (!queue) return NOT_CONNECTED
  try {
    await queue.send(INAV_MSP.MSP2_INAV_SET_CUSTOM_OSD_ELEMENTS, encodeMspINavSetCustomOsdElement(el))
    return { success: true, resultCode: 0, message: 'Custom OSD element saved' }
  } catch (err) {
    return { success: false, resultCode: -1, message: formatErrorMessage(err) }
  }
}

// ── Programming Framework ─────────────────────────────────────

