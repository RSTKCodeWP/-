/**
 * iNav named-settings enumeration in the param list — ON by default, with a
 * sanity gate that falls back to the legacy virtual-param list so a wrong
 * decode can never surface garbage.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect, vi } from 'vitest'
import { mspGetAllParameters, type MspParamContext } from '@/lib/protocol/msp-adapter-params'
import type { SettingsClient } from '@/lib/protocol/msp/settings'
import type { MspSerialQueue } from '@/lib/protocol/msp/msp-serial-queue'

function makeSettings(n: number, namer: (i: number) => string = (i) => `setting_name_${i}`) {
  return Array.from({ length: n }, (_, i) => ({
    name: namer(i), pgId: 1, type: 0, section: 0, mode: 0,
    min: 0, max: 255, index: i, profileCurrent: 0, profileCount: 0, value: i % 200,
  }))
}

function ctx(over: Partial<MspParamContext>): MspParamContext {
  return {
    queue: {} as unknown as MspSerialQueue,
    paramCache: new Map(), paramNameCache: [], parameterCallbacks: [],
    ...over,
  }
}

const erroringQueue = { send: vi.fn(async () => { throw new Error('no virtual params') }) } as unknown as MspSerialQueue

describe('mspGetAllParameters — iNav named-settings enumeration', () => {
  it('surfaces the full named-settings list (with values) when valid', async () => {
    const settingsClient = { enumerateAllSettings: vi.fn(async () => makeSettings(150)) } as unknown as SettingsClient
    const result = await mspGetAllParameters(ctx({ isInav: true, settingsClient }))
    expect(result).toHaveLength(150)
    expect(result[0].name).toBe('setting_name_0')
    expect(result[5].value).toBe(5)
    expect(result[0].count).toBe(150)
  })

  it('falls back when names are garbage (sanity gate)', async () => {
    const settingsClient = { enumerateAllSettings: vi.fn(async () => makeSettings(150, () => '\x01\xff GARBAGE')) } as unknown as SettingsClient
    const result = await mspGetAllParameters(ctx({ isInav: true, settingsClient, queue: erroringQueue }))
    expect(result.some((p) => p.name.includes('GARBAGE'))).toBe(false)
  })

  it('falls back when the count is implausibly low', async () => {
    const settingsClient = { enumerateAllSettings: vi.fn(async () => makeSettings(5)) } as unknown as SettingsClient
    const result = await mspGetAllParameters(ctx({ isInav: true, settingsClient, queue: erroringQueue }))
    expect(result.some((p) => p.name === 'setting_name_0')).toBe(false)
  })

  it('falls back when enumeration throws', async () => {
    const settingsClient = { enumerateAllSettings: vi.fn(async () => { throw new Error('msp error') }) } as unknown as SettingsClient
    const result = await mspGetAllParameters(ctx({ isInav: true, settingsClient, queue: erroringQueue }))
    expect(Array.isArray(result)).toBe(true)
    expect(result.some((p) => p.name.startsWith('setting_name_'))).toBe(false)
  })

  it('does not enumerate for non-iNav MSP firmware', async () => {
    const settingsClient = { enumerateAllSettings: vi.fn(async () => makeSettings(150)) } as unknown as SettingsClient
    await mspGetAllParameters(ctx({ isInav: false, settingsClient, queue: erroringQueue }))
    expect(settingsClient.enumerateAllSettings).not.toHaveBeenCalled()
  })
})
