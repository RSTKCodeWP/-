/**
 * Calibration message handlers.
 * Each function decodes a MAVLink payload and dispatches to subscriber callbacks.
 *
 * @module protocol/handlers/calibration-handlers
 */

import type {
  MagCalProgressCallback, MagCalReportCallback,
  AccelCalPosCallback, AccelCalPosition,
} from '../types'
import {
  decodeMagCalProgress, decodeMagCalReport, decodeCommandLong,
} from '../mavlink-messages'

export function handleMagCalProgress(payload: DataView, callbacks: MagCalProgressCallback[]): void {
  const data = decodeMagCalProgress(payload)
  for (const cb of callbacks) {
    cb({
      compassId: data.compassId,
      completionPct: data.completionPct,
      calStatus: data.calStatus,
      completionMask: Array.from(data.completionMask),
      directionX: data.directionX,
      directionY: data.directionY,
      directionZ: data.directionZ,
    })
  }
}

export function handleMagCalReport(payload: DataView, callbacks: MagCalReportCallback[]): void {
  const data = decodeMagCalReport(payload)
  for (const cb of callbacks) {
    cb({
      compassId: data.compassId,
      calStatus: data.calStatus,
      autosaved: data.autosaved,
      ofsX: data.ofsX,
      ofsY: data.ofsY,
      ofsZ: data.ofsZ,
      fitness: data.fitness,
      diagX: data.diagX,
      diagY: data.diagY,
      diagZ: data.diagZ,
      offdiagX: data.offdiagX,
      offdiagY: data.offdiagY,
      offdiagZ: data.offdiagZ,
      orientationConfidence: data.orientationConfidence,
      oldOrientation: data.oldOrientation,
      newOrientation: data.newOrientation,
      scaleFactor: data.scaleFactor,
    })
  }
}

export function handleIncomingCommandLong(payload: DataView, accelCalCallbacks: AccelCalPosCallback[]): void {
  const data = decodeCommandLong(payload)
  // MAV_CMD_ACCELCAL_VEHICLE_POS = 42429 — FC requests GCS to confirm vehicle position
  if (data.command === 42429) {
    const position = Math.round(data.param1) as AccelCalPosition
    if (position >= 1 && position <= 6) {
      for (const cb of accelCalCallbacks) {
        cb({ position })
      }
    }
  }
}
