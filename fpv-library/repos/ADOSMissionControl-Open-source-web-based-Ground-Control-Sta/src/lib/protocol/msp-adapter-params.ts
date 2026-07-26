/**
 * MSP adapter — virtual parameter system.
 *
 * MSP doesn't have named parameters. This module maps human-readable
 * param names to binary struct field offsets in MSP response payloads.
 *
 * @module protocol/msp-adapter-params
 */

import type { ParameterValue, ParameterCallback, CommandResult } from './types'
import { formatErrorMessage } from '@/lib/utils'
import type { MspSerialQueue } from './msp/msp-serial-queue'
import type { SettingsClient } from './msp/settings'
import { MSP } from './msp/msp-constants'

const NOT_CONNECTED: CommandResult = {
  success: false, resultCode: -1, message: 'Not connected',
}

function u8(buf: Uint8Array, offset: number): number { return buf[offset] }
function u16(buf: Uint8Array, offset: number): number { return buf[offset] | (buf[offset + 1] << 8) }
function u32(buf: Uint8Array, offset: number): number { return (buf[offset] | (buf[offset + 1] << 8) | (buf[offset + 2] << 16) | (buf[offset + 3] << 24)) >>> 0 }
function writeU16(buf: Uint8Array, offset: number, value: number): void { buf[offset] = value & 0xff; buf[offset + 1] = (value >> 8) & 0xff }

/** Map an iNav setting_type_e (0..6) to a MAV_PARAM_TYPE for the grid's type column. */
function inavTypeToMavType(t: number): number {
  switch (t) {
    case 0: return 1   // UINT8
    case 1: return 2   // INT8
    case 2: return 3   // UINT16
    case 3: return 4   // INT16
    case 4: return 5   // UINT32
    case 5: return 10  // FLOAT → REAL32
    default: return 9
  }
}

const VALID_SETTING_NAME = /^[a-z][a-z0-9_]+$/

export interface MspParamContext {
  queue: MspSerialQueue | null
  paramCache: Map<number, Uint8Array>
  paramNameCache: string[]
  parameterCallbacks: ParameterCallback[]
  /** iNav named-settings client (present once connected). */
  settingsClient?: SettingsClient | null
  /** True when the connected FC runs iNav (enables the named-settings list). */
  isInav?: boolean
}

/**
 * Enumerate iNav's full named-settings list (firmware-verified by-index decode),
 * returning a parameter list — or null to fall back to the virtual-param list.
 * Sanity-gated so a wrong decode can never surface garbage: the count must be
 * plausible and a sample of names must be valid iNav identifiers.
 */
async function tryEnumerateInavSettings(client: SettingsClient): Promise<ParameterValue[] | null> {
  let settings
  try {
    settings = await client.enumerateAllSettings()
  } catch {
    return null
  }
  if (settings.length < 100 || settings.length > 2000) return null
  const sample = settings.slice(0, 25)
  if (!sample.every((s) => VALID_SETTING_NAME.test(s.name))) return null
  const count = settings.length
  return settings.map((s, i) => ({
    name: s.name,
    value: typeof s.value === 'number' && Number.isFinite(s.value) ? s.value : 0,
    type: inavTypeToMavType(s.type),
    index: i,
    count,
  }))
}

export async function mspGetAllParameters(ctx: MspParamContext): Promise<ParameterValue[]> {
  if (!ctx.queue) return []

  // iNav: surface the full named-settings list. Sanity-gated; on any failure
  // this returns null and we fall through to the legacy virtual-param list.
  if (ctx.isInav && ctx.settingsClient) {
    const named = await tryEnumerateInavSettings(ctx.settingsClient)
    if (named) {
      ctx.paramNameCache = named.map((p) => p.name)
      for (const param of named) {
        for (const cb of ctx.parameterCallbacks) cb(param)
      }
      return named
    }
  }

  const configCommands = [
    MSP.MSP_PID, MSP.MSP_RC_TUNING, MSP.MSP_BATTERY_CONFIG, MSP.MSP_MOTOR_CONFIG,
    MSP.MSP_FAILSAFE_CONFIG, MSP.MSP_ARMING_CONFIG, MSP.MSP_ADVANCED_CONFIG,
    MSP.MSP_FILTER_CONFIG, MSP.MSP_PID_ADVANCED, MSP.MSP_FEATURE_CONFIG, MSP.MSP_RX_CONFIG,
  ]

  for (const cmd of configCommands) {
    try {
      const frame = await ctx.queue.send(cmd)
      ctx.paramCache.set(cmd, frame.payload)
    } catch {
      // skip
    }
  }

  const results = buildVirtualParams(ctx.paramCache)
  ctx.paramNameCache = results.map(p => p.name)
  for (const param of results) {
    for (const cb of ctx.parameterCallbacks) cb(param)
  }
  return results
}

export async function mspGetParameter(ctx: MspParamContext, name: string): Promise<ParameterValue> {
  if (!ctx.queue) throw new Error('Not connected')
  const def = findVirtualParam(name)
  if (!def) {
    // iNav named setting (lowercase) — read via the settings client. The
    // SETTING_INFO response carries the current value, so one round-trip.
    if (ctx.isInav && ctx.settingsClient) {
      const info = await ctx.settingsClient.getInfo(name)
      return {
        name,
        value: typeof info.value === 'number' && Number.isFinite(info.value) ? info.value : 0,
        type: inavTypeToMavType(info.type),
        index: info.index,
        count: ctx.paramNameCache.length || 1,
      }
    }
    throw new Error(`Unknown parameter: ${name}`)
  }

  let payload = ctx.paramCache.get(def.readCmd)
  if (!payload) {
    const frame = await ctx.queue.send(def.readCmd)
    payload = frame.payload
    ctx.paramCache.set(def.readCmd, payload)
  }

  return {
    name, value: def.decode(payload), type: 9, index: 0,
    count: ctx.paramNameCache.length || 1,
  }
}

export async function mspSetParameter(ctx: MspParamContext, name: string, value: number): Promise<CommandResult> {
  if (!ctx.queue) return NOT_CONNECTED
  const def = findVirtualParam(name)
  if (!def) {
    // iNav named setting — write via the settings client (fetches the type then
    // encodes + MSP2_COMMON_SET_SETTING).
    if (ctx.isInav && ctx.settingsClient) {
      try {
        await ctx.settingsClient.set(name, value)
        return { success: true, resultCode: 0, message: 'OK' }
      } catch (err) {
        return { success: false, resultCode: -1, message: `Write failed: ${formatErrorMessage(err)}` }
      }
    }
    return { success: false, resultCode: -1, message: `Unknown parameter: ${name}` }
  }

  let existing = ctx.paramCache.get(def.readCmd)
  if (!existing) {
    try {
      const frame = await ctx.queue.send(def.readCmd)
      existing = frame.payload
      ctx.paramCache.set(def.readCmd, existing)
    } catch (err) {
      return { success: false, resultCode: -1, message: `Read failed: ${formatErrorMessage(err)}` }
    }
  }

  const newPayload = def.encode(value, existing)
  try {
    await ctx.queue.send(def.writeCmd, newPayload)
    ctx.paramCache.set(def.readCmd, newPayload)
    return { success: true, resultCode: 0, message: 'OK' }
  } catch (err) {
    return { success: false, resultCode: -1, message: `Write failed: ${formatErrorMessage(err)}` }
  }
}

// ── Virtual Param Definitions (data-only) ───────────────────

interface VirtualParamDef {
  name: string; readCmd: number; writeCmd: number; offset: number; size: 1 | 2 | 4
}

interface ResolvedVirtualParam extends VirtualParamDef {
  decode: (payload: Uint8Array) => number
  encode: (value: number, existing: Uint8Array) => Uint8Array
}

const VIRTUAL_PARAMS: VirtualParamDef[] = [
  { name: 'PID_ROLL_P', readCmd: MSP.MSP_PID, writeCmd: MSP.MSP_SET_PID, offset: 0, size: 1 },
  { name: 'PID_ROLL_I', readCmd: MSP.MSP_PID, writeCmd: MSP.MSP_SET_PID, offset: 1, size: 1 },
  { name: 'PID_ROLL_D', readCmd: MSP.MSP_PID, writeCmd: MSP.MSP_SET_PID, offset: 2, size: 1 },
  { name: 'PID_PITCH_P', readCmd: MSP.MSP_PID, writeCmd: MSP.MSP_SET_PID, offset: 3, size: 1 },
  { name: 'PID_PITCH_I', readCmd: MSP.MSP_PID, writeCmd: MSP.MSP_SET_PID, offset: 4, size: 1 },
  { name: 'PID_PITCH_D', readCmd: MSP.MSP_PID, writeCmd: MSP.MSP_SET_PID, offset: 5, size: 1 },
  { name: 'PID_YAW_P', readCmd: MSP.MSP_PID, writeCmd: MSP.MSP_SET_PID, offset: 6, size: 1 },
  { name: 'PID_YAW_I', readCmd: MSP.MSP_PID, writeCmd: MSP.MSP_SET_PID, offset: 7, size: 1 },
  { name: 'PID_YAW_D', readCmd: MSP.MSP_PID, writeCmd: MSP.MSP_SET_PID, offset: 8, size: 1 },
  { name: 'RC_RATE', readCmd: MSP.MSP_RC_TUNING, writeCmd: MSP.MSP_SET_RC_TUNING, offset: 0, size: 1 },
  { name: 'RC_EXPO', readCmd: MSP.MSP_RC_TUNING, writeCmd: MSP.MSP_SET_RC_TUNING, offset: 1, size: 1 },
  { name: 'ROLL_RATE', readCmd: MSP.MSP_RC_TUNING, writeCmd: MSP.MSP_SET_RC_TUNING, offset: 2, size: 1 },
  { name: 'PITCH_RATE', readCmd: MSP.MSP_RC_TUNING, writeCmd: MSP.MSP_SET_RC_TUNING, offset: 3, size: 1 },
  { name: 'YAW_RATE', readCmd: MSP.MSP_RC_TUNING, writeCmd: MSP.MSP_SET_RC_TUNING, offset: 4, size: 1 },
  { name: 'TPA_RATE', readCmd: MSP.MSP_RC_TUNING, writeCmd: MSP.MSP_SET_RC_TUNING, offset: 5, size: 1 },
  { name: 'TPA_BREAKPOINT', readCmd: MSP.MSP_RC_TUNING, writeCmd: MSP.MSP_SET_RC_TUNING, offset: 6, size: 2 },
  { name: 'VBAT_MINCELLVOLTAGE', readCmd: MSP.MSP_BATTERY_CONFIG, writeCmd: MSP.MSP_SET_BATTERY_CONFIG, offset: 0, size: 1 },
  { name: 'VBAT_MAXCELLVOLTAGE', readCmd: MSP.MSP_BATTERY_CONFIG, writeCmd: MSP.MSP_SET_BATTERY_CONFIG, offset: 1, size: 1 },
  { name: 'VBAT_WARNINGCELLVOLTAGE', readCmd: MSP.MSP_BATTERY_CONFIG, writeCmd: MSP.MSP_SET_BATTERY_CONFIG, offset: 2, size: 1 },
  { name: 'BATTERY_CAPACITY', readCmd: MSP.MSP_BATTERY_CONFIG, writeCmd: MSP.MSP_SET_BATTERY_CONFIG, offset: 3, size: 2 },
  { name: 'MINTHROTTLE', readCmd: MSP.MSP_MOTOR_CONFIG, writeCmd: MSP.MSP_SET_MOTOR_CONFIG, offset: 0, size: 2 },
  { name: 'MAXTHROTTLE', readCmd: MSP.MSP_MOTOR_CONFIG, writeCmd: MSP.MSP_SET_MOTOR_CONFIG, offset: 2, size: 2 },
  { name: 'MINCOMMAND', readCmd: MSP.MSP_MOTOR_CONFIG, writeCmd: MSP.MSP_SET_MOTOR_CONFIG, offset: 4, size: 2 },
  { name: 'FAILSAFE_DELAY', readCmd: MSP.MSP_FAILSAFE_CONFIG, writeCmd: MSP.MSP_SET_FAILSAFE_CONFIG, offset: 0, size: 1 },
  { name: 'FAILSAFE_OFF_DELAY', readCmd: MSP.MSP_FAILSAFE_CONFIG, writeCmd: MSP.MSP_SET_FAILSAFE_CONFIG, offset: 1, size: 1 },
  { name: 'FAILSAFE_THROTTLE', readCmd: MSP.MSP_FAILSAFE_CONFIG, writeCmd: MSP.MSP_SET_FAILSAFE_CONFIG, offset: 2, size: 2 },
  { name: 'FAILSAFE_PROCEDURE', readCmd: MSP.MSP_FAILSAFE_CONFIG, writeCmd: MSP.MSP_SET_FAILSAFE_CONFIG, offset: 4, size: 1 },
  { name: 'AUTO_DISARM_DELAY', readCmd: MSP.MSP_ARMING_CONFIG, writeCmd: MSP.MSP_SET_ARMING_CONFIG, offset: 0, size: 1 },
  { name: 'DISARM_KILL_SWITCH', readCmd: MSP.MSP_ARMING_CONFIG, writeCmd: MSP.MSP_SET_ARMING_CONFIG, offset: 1, size: 1 },
  { name: 'FEATURE_FLAGS', readCmd: MSP.MSP_FEATURE_CONFIG, writeCmd: MSP.MSP_SET_FEATURE_CONFIG, offset: 0, size: 4 },
]

function findVirtualParam(name: string): ResolvedVirtualParam | undefined {
  const def = VIRTUAL_PARAMS.find(p => p.name === name)
  if (!def) return undefined
  return {
    ...def,
    decode: (payload: Uint8Array): number => {
      if (def.size === 1) return u8(payload, def.offset)
      if (def.size === 2) return u16(payload, def.offset)
      if (def.size === 4) return u32(payload, def.offset)
      return u8(payload, def.offset)
    },
    encode: (value: number, existing: Uint8Array): Uint8Array => {
      const copy = new Uint8Array(existing)
      if (def.size === 1) { copy[def.offset] = value & 0xff }
      else if (def.size === 2) { writeU16(copy, def.offset, value) }
      else if (def.size === 4) {
        copy[def.offset] = value & 0xff; copy[def.offset + 1] = (value >> 8) & 0xff
        copy[def.offset + 2] = (value >> 16) & 0xff; copy[def.offset + 3] = (value >> 24) & 0xff
      }
      return copy
    },
  }
}

function buildVirtualParams(paramCache: Map<number, Uint8Array>): ParameterValue[] {
  const results: ParameterValue[] = []
  const total = VIRTUAL_PARAMS.length
  for (let i = 0; i < total; i++) {
    const def = VIRTUAL_PARAMS[i]
    const payload = paramCache.get(def.readCmd)
    if (!payload || def.offset >= payload.length) continue
    let value: number
    if (def.size === 1) value = u8(payload, def.offset)
    else if (def.size === 2) value = u16(payload, def.offset)
    else if (def.size === 4) value = u32(payload, def.offset)
    else value = u8(payload, def.offset)
    results.push({ name: def.name, value, type: 9, index: i, count: total })
  }
  return results
}
