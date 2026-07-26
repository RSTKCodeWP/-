/**
 * Tests for useMixerStore.
 *
 * Uses a minimal fake DroneProtocol that resolves with pre-set fixture data
 * so the tests run offline without a flight controller.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useMixerStore, MOTOR_MIXER_MAX, SERVO_MIXER_MAX } from '@/stores/mixer-store'
import type { DroneProtocol } from '@/lib/protocol/types'
import type { MotorMixerRule, INavServoMixerRule } from '@/lib/protocol/msp/msp-decoders-inav'

function makeMotorRule(throttle = 1, roll = 0.5, pitch = -0.5, yaw = 0): MotorMixerRule {
  return { throttle, roll, pitch, yaw }
}

function makeServoRule(targetChannel = 0, inputSource = 0, rate = 100, speed = 0, conditionId = 0): INavServoMixerRule {
  return { targetChannel, inputSource, rate, speed, conditionId }
}

function makeFakeProtocol(
  motorRules: MotorMixerRule[] = [],
  servoRules: INavServoMixerRule[] = [],
): Partial<DroneProtocol> {
  return {
    downloadMotorMixer: vi.fn().mockResolvedValue(motorRules),
    downloadServoMixer: vi.fn().mockResolvedValue(servoRules),
    uploadMotorMixer: vi.fn().mockResolvedValue(undefined),
    uploadServoMixer: vi.fn().mockResolvedValue(undefined),
  }
}

describe('useMixerStore', () => {
  beforeEach(() => {
    useMixerStore.getState().clear()
  })

  it('initialises with empty rule arrays and clean state', () => {
    const { motorRules, servoRules, loading, error, dirty } = useMixerStore.getState()
    expect(motorRules).toHaveLength(0)
    expect(servoRules).toHaveLength(0)
    expect(loading).toBe(false)
    expect(error).toBeNull()
    expect(dirty).toBe(false)
  })

  it('addMotorRule appends up to MOTOR_MIXER_MAX rules', () => {
    const store = useMixerStore.getState()
    for (let i = 0; i < MOTOR_MIXER_MAX; i++) {
      store.addMotorRule(makeMotorRule(i * 0.1))
    }
    expect(useMixerStore.getState().motorRules).toHaveLength(MOTOR_MIXER_MAX)
    // This call must be silently ignored. No crash, no extra entry.
    store.addMotorRule(makeMotorRule(99))
    expect(useMixerStore.getState().motorRules).toHaveLength(MOTOR_MIXER_MAX)
  })

  it('addServoRule appends up to SERVO_MIXER_MAX rules', () => {
    const store = useMixerStore.getState()
    for (let i = 0; i < SERVO_MIXER_MAX; i++) {
      store.addServoRule(makeServoRule(i % 18))
    }
    expect(useMixerStore.getState().servoRules).toHaveLength(SERVO_MIXER_MAX)
    store.addServoRule(makeServoRule(99))
    expect(useMixerStore.getState().servoRules).toHaveLength(SERVO_MIXER_MAX)
  })

  it('setMotorRule updates the rule at the given index and marks dirty', () => {
    useMixerStore.getState().addMotorRule(makeMotorRule(1, 0, 0, 0))
    useMixerStore.getState().setMotorRule(0, { roll: 0.75 })
    const { motorRules, dirty } = useMixerStore.getState()
    expect(motorRules[0].roll).toBe(0.75)
    expect(motorRules[0].throttle).toBe(1)
    expect(dirty).toBe(true)
  })

  it('removeMotorRule deletes the entry at the given index', () => {
    useMixerStore.getState().addMotorRule(makeMotorRule(1))
    useMixerStore.getState().addMotorRule(makeMotorRule(2))
    useMixerStore.getState().removeMotorRule(0)
    expect(useMixerStore.getState().motorRules).toHaveLength(1)
    expect(useMixerStore.getState().motorRules[0].throttle).toBe(2)
  })

  it('loadFromFc populates both tables and clears dirty flag', async () => {
    const motors = [makeMotorRule(1), makeMotorRule(2)]
    const servos = [makeServoRule(0, 1, 100)]
    const proto = makeFakeProtocol(motors, servos)
    await useMixerStore.getState().loadFromFc(proto as DroneProtocol)
    const { motorRules, servoRules, dirty, loading } = useMixerStore.getState()
    expect(motorRules).toHaveLength(2)
    expect(servoRules).toHaveLength(1)
    expect(dirty).toBe(false)
    expect(loading).toBe(false)
  })

  it('concurrent loadFromFc calls are guarded: second is ignored while first is in flight', async () => {
    const motors = [makeMotorRule()]
    const proto = makeFakeProtocol(motors, [])
    const first = useMixerStore.getState().loadFromFc(proto as DroneProtocol)
    const second = useMixerStore.getState().loadFromFc(proto as DroneProtocol)
    await Promise.all([first, second])
    expect(proto.downloadMotorMixer).toHaveBeenCalledTimes(1)
  })
})
