/**
 * MAVLink adapter — mission, rally, and fence protocol methods.
 *
 * Upload/download missions, rally points, fence points, and clear.
 *
 * @module protocol/mavlink-adapter-missions
 */

import type { Transport, CommandResult, MissionItem, FirmwareHandler, FencePointCallback, ParameterCallback, FenceElement } from './types'
import {
  encodeMissionCount, encodeMissionRequestList, encodeMissionClearAll,
  encodeFencePoint, encodeFenceFetchPoint,
  encodeMissionRequestInt,
  MAV_MISSION_TYPE_FENCE,
} from './mavlink-encoder'

/** MAV_FRAME_GLOBAL. Altitude is Reserved for fence polygon/circle vertices. */
const MAV_FRAME_GLOBAL = 0

/** NAV_FENCE_* mission-item commands (used when mission_type = fence). */
export const MAV_CMD_NAV_FENCE_RETURN_POINT = 5000
export const MAV_CMD_NAV_FENCE_POLYGON_VERTEX_INCLUSION = 5001
export const MAV_CMD_NAV_FENCE_POLYGON_VERTEX_EXCLUSION = 5002
export const MAV_CMD_NAV_FENCE_CIRCLE_INCLUSION = 5003
export const MAV_CMD_NAV_FENCE_CIRCLE_EXCLUSION = 5004

/** A single fence mission item, flattened and ready for MISSION_ITEM_INT. */
export interface FenceMissionItem {
  seq: number
  frame: number
  command: number
  param1: number
  param2: number
  /** Latitude * 1e7. */
  x: number
  /** Longitude * 1e7. */
  y: number
  z: number
}

export interface MissionUploadState {
  items: MissionItem[]
  resolve: (result: CommandResult) => void
  reject: (err: Error) => void
  timer: ReturnType<typeof setTimeout>
}

export interface MissionDownloadState {
  items: Map<number, MissionItem>
  total: number
  resolve: (items: MissionItem[]) => void
  reject: (err: Error) => void
  timer: ReturnType<typeof setTimeout>
}

export interface RallyUploadState {
  items: Array<{ lat: number; lon: number; alt: number }>
  resolve: (result: CommandResult) => void
  timer: ReturnType<typeof setTimeout>
}

export interface RallyDownloadState {
  items: Map<number, { lat: number; lon: number; alt: number }>
  total: number
  resolve: (items: Array<{ lat: number; lon: number; alt: number }>) => void
  timer: ReturnType<typeof setTimeout>
}

export interface FenceUploadState {
  items: FenceMissionItem[]
  resolve: (result: CommandResult) => void
  timer: ReturnType<typeof setTimeout>
}

export interface FenceDownloadState {
  items: Map<number, FenceMissionItem>
  total: number
  resolve: (elements: FenceElement[]) => void
  timer: ReturnType<typeof setTimeout>
}

export interface MissionContext {
  transport: Transport | null
  firmwareHandler: FirmwareHandler | null
  targetSysId: number
  targetCompId: number
  sysId: number
  compId: number
  missionUpload: MissionUploadState | null
  missionDownload: MissionDownloadState | null
  rallyUpload: RallyUploadState | null
  rallyDownload: RallyDownloadState | null
  fenceUpload: FenceUploadState | null
  fenceDownload: FenceDownloadState | null
  sendCommandLong: (command: number, params: [number, number, number, number, number, number, number], timeoutMs?: number) => Promise<CommandResult>
  onParameter: (cb: ParameterCallback) => () => void
  onFencePoint: (cb: FencePointCallback) => () => void
  getParameter: (name: string) => Promise<{ value: number }>
}

/**
 * Flatten the fence model into a seq-indexed list of MISSION_ITEM_INT items for
 * a fence-type mission upload. A polygon emits one item per vertex, each
 * carrying param1 = the polygon's total vertex count (min 3); a circle emits one
 * item with param1 = radius (m). Elements with fewer than 3 polygon vertices are
 * skipped. Lat/lon are scaled to int32 * 1e7; altitude is Reserved (z = 0).
 */
export function encodeFenceMissionItems(elements: FenceElement[]): FenceMissionItem[] {
  const items: FenceMissionItem[] = []
  let seq = 0
  for (const el of elements) {
    if (el.kind === 'polygon') {
      const n = el.vertices.length
      if (n < 3) continue
      const command = el.role === 'inclusion'
        ? MAV_CMD_NAV_FENCE_POLYGON_VERTEX_INCLUSION
        : MAV_CMD_NAV_FENCE_POLYGON_VERTEX_EXCLUSION
      const group = el.role === 'inclusion' ? (el.group ?? 0) : 0
      for (const v of el.vertices) {
        items.push({
          seq: seq++, frame: MAV_FRAME_GLOBAL, command,
          param1: n, param2: group,
          x: Math.round(v.lat * 1e7), y: Math.round(v.lon * 1e7), z: 0,
        })
      }
    } else {
      const command = el.role === 'inclusion'
        ? MAV_CMD_NAV_FENCE_CIRCLE_INCLUSION
        : MAV_CMD_NAV_FENCE_CIRCLE_EXCLUSION
      const group = el.role === 'inclusion' ? (el.group ?? 0) : 0
      items.push({
        seq: seq++, frame: MAV_FRAME_GLOBAL, command,
        param1: el.radius, param2: group,
        x: Math.round(el.center.lat * 1e7), y: Math.round(el.center.lon * 1e7), z: 0,
      })
    }
  }
  return items
}

/**
 * Reassemble downloaded fence mission items into the fence model. Consecutive
 * polygon-vertex items of the same command are grouped into one polygon using
 * param1 (vertex count); each circle item is a standalone element; a return
 * point (5000) is ignored. Items are sorted by seq first.
 */
export function decodeFenceMissionItems(items: FenceMissionItem[]): FenceElement[] {
  const sorted = [...items].sort((a, b) => a.seq - b.seq)
  const elements: FenceElement[] = []
  let poly: { role: 'inclusion' | 'exclusion'; command: number; group: number; remaining: number; vertices: Array<{ lat: number; lon: number }> } | null = null

  const flushPoly = () => {
    if (poly && poly.vertices.length >= 3) {
      elements.push({ kind: 'polygon', role: poly.role, vertices: poly.vertices, group: poly.group })
    }
    poly = null
  }

  for (const it of sorted) {
    if (
      it.command === MAV_CMD_NAV_FENCE_POLYGON_VERTEX_INCLUSION ||
      it.command === MAV_CMD_NAV_FENCE_POLYGON_VERTEX_EXCLUSION
    ) {
      const role = it.command === MAV_CMD_NAV_FENCE_POLYGON_VERTEX_INCLUSION ? 'inclusion' : 'exclusion'
      const count = Math.max(3, Math.round(it.param1))
      if (!poly || poly.command !== it.command || poly.remaining <= 0) {
        flushPoly()
        poly = { role, command: it.command, group: Math.round(it.param2), remaining: count, vertices: [] }
      }
      poly.vertices.push({ lat: it.x / 1e7, lon: it.y / 1e7 })
      poly.remaining -= 1
      if (poly.remaining <= 0) flushPoly()
    } else if (
      it.command === MAV_CMD_NAV_FENCE_CIRCLE_INCLUSION ||
      it.command === MAV_CMD_NAV_FENCE_CIRCLE_EXCLUSION
    ) {
      flushPoly()
      const role = it.command === MAV_CMD_NAV_FENCE_CIRCLE_INCLUSION ? 'inclusion' : 'exclusion'
      elements.push({
        kind: 'circle', role,
        center: { lat: it.x / 1e7, lon: it.y / 1e7 },
        radius: it.param1, group: Math.round(it.param2),
      })
    }
    // MAV_CMD_NAV_FENCE_RETURN_POINT (5000) carries no geometry we model, ignore.
  }
  flushPoly()
  return elements
}

export async function uploadMission(ctx: MissionContext, items: MissionItem[]): Promise<CommandResult> {
  if (!ctx.transport?.isConnected) return { success: false, resultCode: -1, message: 'Not connected' }

  return new Promise<CommandResult>((resolve, reject) => {
    const timer = setTimeout(() => {
      ctx.missionUpload = null
      resolve({ success: false, resultCode: -1, message: 'Mission upload timed out' })
    }, 15000)

    ctx.missionUpload = { items, resolve, reject, timer }
    ctx.transport!.send(encodeMissionCount(ctx.targetSysId, ctx.targetCompId, items.length, ctx.sysId, ctx.compId))
  })
}

export async function downloadMission(ctx: MissionContext): Promise<MissionItem[]> {
  if (!ctx.transport?.isConnected) throw new Error('Not connected')

  return new Promise<MissionItem[]>((resolve, reject) => {
    const timer = setTimeout(() => {
      if (ctx.missionDownload) {
        const items = Array.from(ctx.missionDownload.items.values()).sort((a, b) => a.seq - b.seq)
        ctx.missionDownload = null
        resolve(items)
      }
    }, 15000)

    ctx.missionDownload = { items: new Map(), total: 0, resolve, reject, timer }
    ctx.transport!.send(encodeMissionRequestList(ctx.targetSysId, ctx.targetCompId, ctx.sysId, ctx.compId))
  })
}

export async function setCurrentMissionItem(ctx: MissionContext, seq: number): Promise<CommandResult> {
  return ctx.sendCommandLong(224, [seq, 0, 0, 0, 0, 0, 0])
}

export async function clearMission(ctx: MissionContext): Promise<CommandResult> {
  if (!ctx.transport?.isConnected) return { success: false, resultCode: -1, message: 'Not connected' }

  return new Promise<CommandResult>((resolve) => {
    const timer = setTimeout(() => {
      resolve({ success: false, resultCode: -1, message: 'Mission clear timed out' })
      ctx.missionUpload = null
    }, 5000)

    ctx.missionUpload = {
      items: [],
      resolve,
      reject: () => resolve({ success: false, resultCode: -1, message: 'Mission clear failed' }),
      timer,
    }

    ctx.transport!.send(encodeMissionClearAll(ctx.targetSysId, ctx.targetCompId, ctx.sysId, ctx.compId))
  })
}

export async function uploadFence(ctx: MissionContext, points: Array<{ lat: number; lon: number }>): Promise<CommandResult> {
  if (!ctx.transport?.isConnected) {
    return { success: false, resultCode: -1, message: 'Not connected' }
  }
  for (let i = 0; i < points.length; i++) {
    ctx.transport.send(encodeFencePoint(
      ctx.targetSysId, ctx.targetCompId,
      i, points.length, points[i].lat, points[i].lon,
      ctx.sysId, ctx.compId,
    ))
  }
  return { success: true, resultCode: 0, message: `Uploaded ${points.length} fence points` }
}

export async function downloadFence(ctx: MissionContext): Promise<Array<{ idx: number; lat: number; lon: number }>> {
  if (!ctx.transport?.isConnected) return []

  let fenceTotal: number
  try {
    const result = await ctx.getParameter('FENCE_TOTAL')
    fenceTotal = result.value
  } catch {
    return []
  }

  if (fenceTotal <= 0) return []

  const points: Array<{ idx: number; lat: number; lon: number }> = []
  const received = new Set<number>()

  return new Promise<Array<{ idx: number; lat: number; lon: number }>>((resolve) => {
    const timeout = setTimeout(() => {
      unsub()
      points.sort((a, b) => a.idx - b.idx)
      resolve(points)
    }, 10000)

    const unsub = ctx.onFencePoint((data) => {
      if (!received.has(data.idx)) {
        received.add(data.idx)
        points.push({ idx: data.idx, lat: data.lat, lon: data.lon })
      }
      if (received.size >= fenceTotal) {
        clearTimeout(timeout)
        unsub()
        points.sort((a, b) => a.idx - b.idx)
        resolve(points)
      }
    })

    for (let i = 0; i < fenceTotal; i++) {
      ctx.transport!.send(encodeFenceFetchPoint(
        ctx.targetSysId, ctx.targetCompId,
        i, ctx.sysId, ctx.compId,
      ))
    }
  })
}

/**
 * Upload the geofence as a fence-type mission (mission_type = fence). Used by
 * firmwares (PX4) that store the fence as a mission plan rather than the legacy
 * FENCE_POINT protocol. Kept separate from the waypoint-mission and rally state
 * machines so uploading a fence never touches the waypoint mission.
 */
export async function uploadFenceMission(ctx: MissionContext, elements: FenceElement[]): Promise<CommandResult> {
  if (!ctx.transport?.isConnected) return { success: false, resultCode: -1, message: 'Not connected' }
  const items = encodeFenceMissionItems(elements)
  if (items.length === 0) return { success: true, resultCode: 0, message: 'No fence items to upload' }

  return new Promise<CommandResult>((resolve) => {
    const timer = setTimeout(() => {
      ctx.fenceUpload = null
      resolve({ success: false, resultCode: -1, message: 'Fence upload timed out' })
    }, 15000)

    ctx.fenceUpload = { items, resolve, timer }
    ctx.transport!.send(encodeMissionCount(
      ctx.targetSysId, ctx.targetCompId, items.length,
      ctx.sysId, ctx.compId, MAV_MISSION_TYPE_FENCE,
    ))
  })
}

/**
 * Download the geofence as a fence-type mission (mission_type = fence) and
 * reassemble it into the fence model. Used by firmwares (PX4) that store the
 * fence as a mission plan.
 */
export async function downloadFenceMission(ctx: MissionContext): Promise<FenceElement[]> {
  if (!ctx.transport?.isConnected) return []

  return new Promise<FenceElement[]>((resolve) => {
    const timer = setTimeout(() => {
      if (ctx.fenceDownload) {
        const items = Array.from(ctx.fenceDownload.items.values())
        ctx.fenceDownload = null
        resolve(decodeFenceMissionItems(items))
      } else {
        resolve([])
      }
    }, 15000)

    ctx.fenceDownload = { items: new Map(), total: 0, resolve, timer }
    ctx.transport!.send(encodeMissionRequestList(
      ctx.targetSysId, ctx.targetCompId,
      ctx.sysId, ctx.compId, MAV_MISSION_TYPE_FENCE,
    ))
  })
}

export async function uploadRallyPoints(ctx: MissionContext, points: Array<{ lat: number; lon: number; alt: number }>): Promise<CommandResult> {
  if (!ctx.transport?.isConnected) return { success: false, resultCode: -1, message: 'Not connected' }
  if (points.length === 0) return { success: true, resultCode: 0, message: 'No rally points to upload' }

  return new Promise<CommandResult>((resolve) => {
    const timer = setTimeout(() => {
      ctx.rallyUpload = null
      resolve({ success: false, resultCode: -1, message: 'Rally point upload timed out' })
    }, 15000)

    ctx.rallyUpload = { items: points, resolve, timer }
    ctx.transport!.send(encodeMissionCount(
      ctx.targetSysId, ctx.targetCompId, points.length,
      ctx.sysId, ctx.compId, 2,
    ))
  })
}

export async function downloadRallyPoints(ctx: MissionContext): Promise<Array<{ lat: number; lon: number; alt: number }>> {
  if (!ctx.transport?.isConnected) return []

  return new Promise<Array<{ lat: number; lon: number; alt: number }>>((resolve) => {
    const timer = setTimeout(() => {
      if (ctx.rallyDownload) {
        const items = Array.from(ctx.rallyDownload.items.entries())
          .sort((a, b) => a[0] - b[0])
          .map(([, pt]) => pt)
        ctx.rallyDownload = null
        resolve(items)
      } else {
        resolve([])
      }
    }, 15000)

    ctx.rallyDownload = { items: new Map(), total: 0, resolve, timer }
    ctx.transport!.send(encodeMissionRequestList(
      ctx.targetSysId, ctx.targetCompId,
      ctx.sysId, ctx.compId, 2,
    ))
  })
}
