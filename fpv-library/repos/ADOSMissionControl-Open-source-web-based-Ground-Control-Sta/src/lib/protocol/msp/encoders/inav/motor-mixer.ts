/**
 * Common motor mixer encoder shared with iNav (MSP2_COMMON_SET_MOTOR_MIXER).
 *
 * @module protocol/msp/encoders/inav/motor-mixer
 */

import type { MotorMixerRule } from '../../msp-decoders-inav';
import { writeU8 } from './_helpers';

/**
 * Encode MSP2_COMMON_SET_MOTOR_MIXER (0x1006) payload for one slot.
 *
 * Layout: U8 idx, S16 throttle x1000, S16 roll x1000, S16 pitch x1000, S16 yaw x1000.
 * 9 bytes total.
 */
export function encodeMspCommonSetMotorMixer(idx: number, rule: MotorMixerRule): Uint8Array {
  const buf = new Uint8Array(9);
  const dv = new DataView(buf.buffer);
  writeU8(dv, 0, idx & 0xff);
  dv.setInt16(1, Math.round(rule.throttle * 1000), true);
  dv.setInt16(3, Math.round(rule.roll * 1000), true);
  dv.setInt16(5, Math.round(rule.pitch * 1000), true);
  dv.setInt16(7, Math.round(rule.yaw * 1000), true);
  return buf;
}
