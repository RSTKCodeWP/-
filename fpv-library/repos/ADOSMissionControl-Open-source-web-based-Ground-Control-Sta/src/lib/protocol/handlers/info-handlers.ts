/**
 * Vehicle info and status message handlers.
 * Each function decodes a MAVLink payload and dispatches to subscriber callbacks.
 *
 * @module protocol/handlers/info-handlers
 */

import type {
  ExtendedSysStateCallback, SystemTimeCallback,
  StatusTextCallback, EventCallback, SerialDataCallback,
  AutopilotVersionCallback,
} from '../types'
import {
  decodeExtendedSysState, decodeSystemTime,
  decodeStatustext, decodeEvent, decodeSerialControl,
  decodeAutopilotVersion,
} from '../mavlink-messages'

export function handleExtendedSysState(payload: DataView, callbacks: ExtendedSysStateCallback[]): void {
  const data = decodeExtendedSysState(payload)
  for (const cb of callbacks) {
    cb({ timestamp: Date.now(), vtolState: data.vtolState, landedState: data.landedState })
  }
}

export function handleSystemTime(payload: DataView, callbacks: SystemTimeCallback[]): void {
  const data = decodeSystemTime(payload)
  for (const cb of callbacks) {
    cb({ timestamp: Date.now(), timeUnixUsec: data.timeUnixUsec, timeBootMs: data.timeBootMs })
  }
}

export function handleStatusText(payload: DataView, callbacks: StatusTextCallback[]): void {
  const st = decodeStatustext(payload)
  for (const cb of callbacks) cb(st)
}

export function handleEvent(payload: DataView, callbacks: EventCallback[]): void {
  const ev = decodeEvent(payload)
  for (const cb of callbacks) cb(ev)
}

export function handleSerialControl(payload: DataView, callbacks: SerialDataCallback[]): void {
  const sc = decodeSerialControl(payload)
  for (const cb of callbacks) {
    cb({ device: sc.device, data: sc.data })
  }
}

export function handleAutopilotVersion(
  payload: DataView,
  callbacks: AutopilotVersionCallback[],
): { flightSwVersion: number; middlewareSwVersion: number; osSwVersion: number; boardVersion: number; uid: number; capabilities: number } {
  const data = decodeAutopilotVersion(payload)
  for (const cb of callbacks) {
    cb({
      capabilities: data.capabilities,
      flightSwVersion: data.flightSwVersion,
      middlewareSwVersion: data.middlewareSwVersion,
      osSwVersion: data.osSwVersion,
      boardVersion: data.boardVersion,
      uid: data.uid,
    })
  }
  return data
}
