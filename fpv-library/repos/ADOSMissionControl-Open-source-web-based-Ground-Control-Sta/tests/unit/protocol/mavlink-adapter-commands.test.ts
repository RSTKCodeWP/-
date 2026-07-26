/**
 * cmdSetFlightMode must encode DO_SET_MODE per firmware: ArduPilot puts the flat
 * custom_mode number in param2; PX4 de-packs into param2 = main_mode,
 * param3 = sub_mode (PX4 reads the low byte of param2 as the main mode, so the
 * packed value would be read as main 0 and rejected).
 *
 * @license GPL-3.0-only
 */
import { describe, it, expect } from 'vitest'
import { cmdSetFlightMode } from '../../../src/lib/protocol/mavlink-adapter-commands'
import type { CommandContext } from '../../../src/lib/protocol/mavlink-adapter-commands'
import { createFirmwareHandlerByType } from '../../../src/lib/protocol/firmware/ardupilot'
import type { FirmwareType } from '../../../src/lib/protocol/types'

function ctxFor(firmwareType: FirmwareType): {
  ctx: CommandContext
  sent: Array<{ command: number; params: number[] }>
} {
  const sent: Array<{ command: number; params: number[] }> = []
  const ctx = {
    transport: null,
    firmwareHandler: createFirmwareHandlerByType(firmwareType),
    targetSysId: 1,
    targetCompId: 1,
    sysId: 255,
    compId: 190,
    sendCommandLong: (command: number, params: number[]) => {
      sent.push({ command, params })
      return Promise.resolve({ success: true, resultCode: 0 })
    },
  } as unknown as CommandContext
  return { ctx, sent }
}

describe('cmdSetFlightMode DO_SET_MODE encoding', () => {
  it('ArduCopter RTL sends the flat custom_mode (6) in param2', async () => {
    const { ctx, sent } = ctxFor('ardupilot-copter')
    await cmdSetFlightMode(ctx, 'RTL')
    expect(sent).toHaveLength(1)
    expect(sent[0].command).toBe(176)
    expect(sent[0].params).toEqual([1, 6, 0, 0, 0, 0, 0])
  })

  it('PX4 RTL de-packs into param2 = AUTO (4), param3 = RTL (5)', async () => {
    const { ctx, sent } = ctxFor('px4')
    await cmdSetFlightMode(ctx, 'RTL')
    expect(sent[0].command).toBe(176)
    // NOT the packed value (0x05040000) in param2 (which PX4 reads as main 0).
    expect(sent[0].params).toEqual([1, 4, 5, 0, 0, 0, 0])
  })

  it('PX4 MISSION de-packs into param2 = AUTO (4), param3 = MISSION (4)', async () => {
    const { ctx, sent } = ctxFor('px4')
    await cmdSetFlightMode(ctx, 'MISSION')
    expect(sent[0].params).toEqual([1, 4, 4, 0, 0, 0, 0])
  })

  it('PX4 POSHOLD is a single-level mode: main = POSCTL (3), sub = 0', async () => {
    const { ctx, sent } = ctxFor('px4')
    await cmdSetFlightMode(ctx, 'POSHOLD')
    expect(sent[0].params).toEqual([1, 3, 0, 0, 0, 0, 0])
  })
})
