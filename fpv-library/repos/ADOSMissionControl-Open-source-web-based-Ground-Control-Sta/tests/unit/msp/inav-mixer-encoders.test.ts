import { describe, it, expect } from 'vitest'
import {
  encodeMspCommonSetMotorMixer,
  encodeMspINavSetServoMixer,
} from '@/lib/protocol/msp/msp-encoders-inav'
import {
  decodeMspCommonMotorMixer,
  decodeMspINavServoMixer,
} from '@/lib/protocol/msp/msp-decoders-inav'
import type { MotorMixerRule, INavServoMixerRule } from '@/lib/protocol/msp/msp-decoders-inav'

function readU8(buf: Uint8Array, offset: number): number {
  return buf[offset]
}

function readS16LE(buf: Uint8Array, offset: number): number {
  return new DataView(buf.buffer, buf.byteOffset + offset, 2).getInt16(0, true)
}

describe('encodeMspCommonSetMotorMixer', () => {
  it('produces a 9-byte payload', () => {
    const rule: MotorMixerRule = { throttle: 1, roll: 0.5, pitch: -0.5, yaw: 0 }
    expect(encodeMspCommonSetMotorMixer(0, rule).byteLength).toBe(9)
  })

  it('places the slot index at byte 0', () => {
    const rule: MotorMixerRule = { throttle: 0, roll: 0, pitch: 0, yaw: 0 }
    expect(readU8(encodeMspCommonSetMotorMixer(3, rule), 0)).toBe(3)
  })

  it('encodes throttle x1000 as S16LE at bytes 1-2', () => {
    const rule: MotorMixerRule = { throttle: 1.5, roll: 0, pitch: 0, yaw: 0 }
    expect(readS16LE(encodeMspCommonSetMotorMixer(0, rule), 1)).toBe(1500)
  })

  it('encodes roll x1000 as S16LE at bytes 3-4', () => {
    const rule: MotorMixerRule = { throttle: 0, roll: -1.0, pitch: 0, yaw: 0 }
    expect(readS16LE(encodeMspCommonSetMotorMixer(0, rule), 3)).toBe(-1000)
  })

  it('encodes pitch x1000 as S16LE at bytes 5-6', () => {
    const rule: MotorMixerRule = { throttle: 0, roll: 0, pitch: 0.75, yaw: 0 }
    expect(readS16LE(encodeMspCommonSetMotorMixer(0, rule), 5)).toBe(750)
  })

  it('encodes yaw x1000 as S16LE at bytes 7-8', () => {
    const rule: MotorMixerRule = { throttle: 0, roll: 0, pitch: 0, yaw: -0.5 }
    expect(readS16LE(encodeMspCommonSetMotorMixer(0, rule), 7)).toBe(-500)
  })
})

describe('encodeMspINavSetServoMixer', () => {
  it('produces a 7-byte payload', () => {
    const rule: INavServoMixerRule = { targetChannel: 0, inputSource: 1, rate: 100, speed: 0, conditionId: 0 }
    expect(encodeMspINavSetServoMixer(0, rule).byteLength).toBe(7)
  })

  it('places the slot index at byte 0', () => {
    const rule: INavServoMixerRule = { targetChannel: 2, inputSource: 0, rate: 0, speed: 0, conditionId: 0 }
    expect(readU8(encodeMspINavSetServoMixer(5, rule), 0)).toBe(5)
  })

  it('places targetChannel at byte 1', () => {
    const rule: INavServoMixerRule = { targetChannel: 7, inputSource: 0, rate: 0, speed: 0, conditionId: 0 }
    expect(readU8(encodeMspINavSetServoMixer(0, rule), 1)).toBe(7)
  })

  it('places inputSource at byte 2', () => {
    const rule: INavServoMixerRule = { targetChannel: 0, inputSource: 4, rate: 0, speed: 0, conditionId: 0 }
    expect(readU8(encodeMspINavSetServoMixer(0, rule), 2)).toBe(4)
  })

  it('encodes rate as S16LE at bytes 3-4', () => {
    const rule: INavServoMixerRule = { targetChannel: 0, inputSource: 0, rate: -75, speed: 0, conditionId: 0 }
    expect(readS16LE(encodeMspINavSetServoMixer(0, rule), 3)).toBe(-75)
  })

  it('places speed at byte 5 and conditionId at byte 6', () => {
    const rule: INavServoMixerRule = { targetChannel: 0, inputSource: 0, rate: 0, speed: 3, conditionId: 11 }
    const buf = encodeMspINavSetServoMixer(0, rule)
    expect(readU8(buf, 5)).toBe(3)
    expect(readU8(buf, 6)).toBe(11)
  })
})

describe('motor mixer round-trip', () => {
  it('decodes a single-rule frame produced by the encoder', () => {
    const rule: MotorMixerRule = { throttle: 1, roll: 0.5, pitch: -0.5, yaw: 0.25 }
    const encoded = encodeMspCommonSetMotorMixer(0, rule)
    // Build a 8-byte frame (decoder format: no index, just the four S16 fields)
    const frame = new Uint8Array(8)
    frame.set(encoded.slice(1), 0)
    const decoded = decodeMspCommonMotorMixer(new DataView(frame.buffer))
    expect(decoded).toHaveLength(1)
    expect(decoded[0].throttle).toBeCloseTo(rule.throttle, 3)
    expect(decoded[0].roll).toBeCloseTo(rule.roll, 3)
    expect(decoded[0].pitch).toBeCloseTo(rule.pitch, 3)
    expect(decoded[0].yaw).toBeCloseTo(rule.yaw, 3)
  })
})

describe('servo mixer round-trip', () => {
  it('decodes a single-rule frame produced by the encoder', () => {
    const rule: INavServoMixerRule = { targetChannel: 3, inputSource: 2, rate: -50, speed: 5, conditionId: 9 }
    const encoded = encodeMspINavSetServoMixer(0, rule)
    // Build a 6-byte frame (decoder format: no index, just the six fields)
    const frame = new Uint8Array(6)
    frame.set(encoded.slice(1), 0)
    const decoded = decodeMspINavServoMixer(new DataView(frame.buffer))
    expect(decoded).toHaveLength(1)
    expect(decoded[0]).toEqual(rule)
  })
})
