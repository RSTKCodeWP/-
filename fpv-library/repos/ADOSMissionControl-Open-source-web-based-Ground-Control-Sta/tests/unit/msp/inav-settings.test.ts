import { describe, it, expect } from 'vitest'
import { SettingType, SettingsClient, SettingsError } from '@/lib/protocol/msp/settings'
import type { MspSerialQueue } from '@/lib/protocol/msp/msp-serial-queue'
import type { ParsedMspFrame } from '@/lib/protocol/msp/msp-parser'
import { INAV_MSP } from '@/lib/protocol/msp/msp-decoders-inav'

// ── Firmware-accurate MSP2_COMMON_SETTING_INFO frame builder ──
// Mirrors iNav fc/fc_msp.c mspSettingInfoCommand serialization:
//   cstring name, U16 pgId, U8 type, U8 section, U8 mode, S32 min, U32 max,
//   U16 index, U8 profileCurrent, U8 profileCount,
//   [if MODE_LOOKUP: cstring label × (max-min+1)], value (by type).
const MODE_LOOKUP = 1 << 6

function cstr(parts: number[], s: string) { for (const c of s) parts.push(c.charCodeAt(0)); parts.push(0) }
function u16(parts: number[], n: number) { parts.push(n & 0xff, (n >>> 8) & 0xff) }
function u32(parts: number[], n: number) { const u = n >>> 0; parts.push(u & 0xff, (u >>> 8) & 0xff, (u >>> 16) & 0xff, (u >>> 24) & 0xff) }
function s32(parts: number[], n: number) { const dv = new DataView(new ArrayBuffer(4)); dv.setInt32(0, n, true); for (let i = 0; i < 4; i++) parts.push(dv.getUint8(i)) }

function buildSettingInfo(o: {
  name: string; pgId?: number; type?: number; section?: number; mode?: number;
  min?: number; max?: number; index?: number; profileCurrent?: number; profileCount?: number;
  enumLabels?: string[]; value?: number;
}): Uint8Array {
  const p: number[] = []
  cstr(p, o.name)
  u16(p, o.pgId ?? 1)
  p.push(o.type ?? 0, o.section ?? 0, o.mode ?? 0)
  s32(p, o.min ?? 0)
  u32(p, o.max ?? 0)
  u16(p, o.index ?? 0)
  p.push(o.profileCurrent ?? 0, o.profileCount ?? 0)
  if ((o.mode ?? 0) & MODE_LOOKUP) for (const l of o.enumLabels ?? []) cstr(p, l)
  if (o.value !== undefined) {
    const t = o.type ?? 0
    const dv = new DataView(new ArrayBuffer(4))
    if (t === 0) p.push(o.value & 0xff)
    else if (t === 1) { dv.setInt8(0, o.value); p.push(dv.getUint8(0)) }
    else if (t === 2) u16(p, o.value)
    else if (t === 3) { dv.setInt16(0, o.value, true); p.push(dv.getUint8(0), dv.getUint8(1)) }
    else if (t === 4) u32(p, o.value)
    else if (t === 5) { dv.setFloat32(0, o.value, true); for (let i = 0; i < 4; i++) p.push(dv.getUint8(i)) }
  }
  return new Uint8Array(p)
}

function makeFrame(command: number, payload: Uint8Array): ParsedMspFrame {
  return { command, payload, version: 2, direction: 'response' }
}
function mockQueue(handler: (command: number, payload: Uint8Array | undefined) => ParsedMspFrame): MspSerialQueue {
  return {
    send(command: number, payload?: Uint8Array) { return Promise.resolve(handler(command, payload)) },
    sendNoReply() {}, flush() {}, destroy() {}, pending: 0,
  } as unknown as MspSerialQueue
}

// ── SettingType enum (firmware setting_type_e, 0..6) ──────────

describe('SettingType', () => {
  it('matches the firmware enum (no INT32; FLOAT=5, STRING=6)', () => {
    expect(SettingType.UINT8).toBe(0)
    expect(SettingType.INT8).toBe(1)
    expect(SettingType.UINT16).toBe(2)
    expect(SettingType.INT16).toBe(3)
    expect(SettingType.UINT32).toBe(4)
    expect(SettingType.FLOAT).toBe(5)
    expect(SettingType.STRING).toBe(6)
    expect((SettingType as Record<string, number>).INT32).toBeUndefined()
  })
})

describe('SettingsError', () => {
  it('stores settingName, message, and cause', () => {
    const cause = new Error('underlying')
    const err = new SettingsError('outer', 'nav_mc_pos_z_p', cause)
    expect(err.message).toBe('outer')
    expect(err.settingName).toBe('nav_mc_pos_z_p')
    expect(err.name).toBe('SettingsError')
    expect(err.cause).toBe(cause)
  })
})

// ── decodeCommonSettingInfo via SettingsClient.getInfo ────────

describe('SettingsClient.getInfo — firmware byte layout', () => {
  it('parses name-first, type, min (signed) and max (UNSIGNED) and the trailing value', async () => {
    // max = 3_000_000_000 (> INT32_MAX) must decode unsigned, not negative.
    const payload = buildSettingInfo({
      name: 'nav_fw_cruise_throttle', pgId: 99, type: SettingType.UINT16,
      min: -50, max: 3_000_000_000, index: 7, value: 1500,
    })
    const client = new SettingsClient(mockQueue((cmd) => makeFrame(cmd, payload)))
    const info = await client.getInfo('nav_fw_cruise_throttle')
    expect(info.name).toBe('nav_fw_cruise_throttle')
    expect(info.pgId).toBe(99)
    expect(info.type).toBe(SettingType.UINT16)
    expect(info.min).toBe(-50)            // signed
    expect(info.max).toBe(3_000_000_000)  // unsigned, not negative
    expect(info.index).toBe(7)
    expect(info.value).toBe(1500)
  })

  it('parses MODE_LOOKUP enum labels (count = max-min+1)', async () => {
    const payload = buildSettingInfo({
      name: 'motor_pwm_protocol', type: SettingType.UINT8, mode: MODE_LOOKUP,
      min: 0, max: 2, enumLabels: ['STANDARD', 'ONESHOT125', 'MULTISHOT'], value: 1,
    })
    const client = new SettingsClient(mockQueue((cmd) => makeFrame(cmd, payload)))
    const info = await client.getInfo('motor_pwm_protocol')
    expect(info.mode & MODE_LOOKUP).toBeTruthy()
    expect(info.enumValues).toEqual(['STANDARD', 'ONESHOT125', 'MULTISHOT'])
    expect(info.value).toBe(1)
  })
})

// ── by-index enumeration ─────────────────────────────────────

describe('SettingsClient.getInfoByIndex / enumerateAllSettings', () => {
  it('requests by index ([0x00, idxLo, idxHi])', async () => {
    let sent: Uint8Array | undefined
    const queue = mockQueue((cmd, payload) => {
      sent = payload
      return makeFrame(cmd, buildSettingInfo({ name: 'acc_hardware', index: 42 }))
    })
    const info = await new SettingsClient(queue).getInfoByIndex(42)
    expect(sent![0]).toBe(0)
    expect(sent![1] | (sent![2] << 8)).toBe(42)
    expect(info.name).toBe('acc_hardware')
  })

  it('enumerates indices until the FC errors', async () => {
    const names = ['acc_hardware', 'mag_hardware', 'baro_hardware']
    const queue = mockQueue((cmd, payload) => {
      const idx = payload![1] | (payload![2] << 8)
      if (idx >= names.length) throw new Error('out of range')
      return makeFrame(cmd, buildSettingInfo({ name: names[idx], index: idx }))
    })
    const all = await new SettingsClient(queue).enumerateAllSettings()
    expect(all.map((s) => s.name)).toEqual(names)
  })
})

// ── getRaw / setRaw / getPgList (unchanged paths) ─────────────

describe('SettingsClient.getRaw / setRaw / getPgList', () => {
  it('getRaw sends a null-terminated name and returns raw bytes', async () => {
    let sentPayload: Uint8Array | undefined
    const queue = mockQueue((cmd, payload) => { sentPayload = payload; return makeFrame(cmd, new Uint8Array([42])) })
    const result = await new SettingsClient(queue).getRaw('debug_mode')
    expect(String.fromCharCode(...sentPayload!.subarray(0, sentPayload!.length - 1))).toBe('debug_mode')
    expect(sentPayload![sentPayload!.length - 1]).toBe(0)
    expect(result[0]).toBe(42)
  })

  it('getRaw wraps a queue rejection in SettingsError with the setting name + cause', async () => {
    const cause = new Error('serial timeout')
    const queue = { send() { return Promise.reject(cause) } } as unknown as MspSerialQueue
    const err = await new SettingsClient(queue).getRaw('nav_mc_pos_z_p').catch((e) => e)
    expect(err).toBeInstanceOf(SettingsError)
    expect(err.settingName).toBe('nav_mc_pos_z_p')
    expect(err.cause).toBe(cause)
  })

  it('setRaw sends name + value', async () => {
    let sentPayload: Uint8Array | undefined
    const queue = mockQueue((cmd, payload) => { sentPayload = payload; return makeFrame(cmd, new Uint8Array(0)) })
    await new SettingsClient(queue).setRaw('osd_crosshairs', new Uint8Array([1]))
    expect(sentPayload!.byteLength).toBe('osd_crosshairs'.length + 1 + 1)
    expect(sentPayload!['osd_crosshairs'.length]).toBe(0)
    expect(sentPayload!['osd_crosshairs'.length + 1]).toBe(1)
  })

  it('getPgList decodes U16 PG IDs', async () => {
    const payload = new Uint8Array(6)
    const dv = new DataView(payload.buffer)
    dv.setUint16(0, 100, true); dv.setUint16(2, 200, true); dv.setUint16(4, 300, true)
    const pgIds = await new SettingsClient(mockQueue((cmd) => makeFrame(cmd, payload))).getPgList()
    expect(pgIds).toEqual([100, 200, 300])
  })
})

// ── value round-trip ─────────────────────────────────────────

describe('SettingsClient.get — INT16 round-trip', () => {
  it('decodes a negative INT16 value', async () => {
    const raw = new Uint8Array(2)
    new DataView(raw.buffer).setInt16(0, -100, true)
    const info = buildSettingInfo({ name: 'some_int16', type: SettingType.INT16 })
    let n = 0
    const queue = mockQueue((cmd) => makeFrame(cmd, ++n === 1 ? raw : info))
    const result = await new SettingsClient(queue).get('some_int16')
    expect(result.type).toBe('int16')
    expect(result.value).toBe(-100)
  })
})
