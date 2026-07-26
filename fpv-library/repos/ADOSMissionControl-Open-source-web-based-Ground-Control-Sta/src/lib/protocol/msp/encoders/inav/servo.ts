/**
 * iNav servo config and servo mixer encoders.
 *
 * @module protocol/msp/encoders/inav/servo
 */

import type { INavServoConfig, INavServoMixerRule } from '../../msp-decoders-inav';
import { writeU8, writeU16 } from './_helpers';

/**
 * Encode MSP2_INAV_SET_SERVO_CONFIG (0x2201) payload for a single servo slot.
 *
 * U8  servoIndex
 * S16 rate
 * S16 min
 * S16 max
 * S16 middle
 * U8  forwardFromChannel
 * U16 reversedInputSources
 * U8  flags
 */
export function encodeMspINavSetServoConfig(idx: number, cfg: INavServoConfig): Uint8Array {
  const buf = new Uint8Array(13);
  const dv = new DataView(buf.buffer);

  writeU8(dv, 0, idx & 0xff);
  dv.setInt16(1, cfg.rate, true);
  dv.setInt16(3, cfg.min, true);
  dv.setInt16(5, cfg.max, true);
  dv.setInt16(7, cfg.middle, true);
  writeU8(dv, 9, cfg.forwardFromChannel);
  writeU16(dv, 10, cfg.reversedInputSources);
  writeU8(dv, 12, cfg.flags);

  return buf;
}

/**
 * Encode MSP2_INAV_SET_SERVO_MIXER (0x2021) payload for one slot.
 *
 * Layout: U8 idx, U8 targetChannel, U8 inputSource, S16 rate, U8 speed, U8 conditionId.
 * 7 bytes total.
 */
export function encodeMspINavSetServoMixer(idx: number, rule: INavServoMixerRule): Uint8Array {
  const buf = new Uint8Array(7);
  const dv = new DataView(buf.buffer);
  writeU8(dv, 0, idx & 0xff);
  writeU8(dv, 1, rule.targetChannel & 0xff);
  writeU8(dv, 2, rule.inputSource & 0xff);
  dv.setInt16(3, rule.rate, true);
  writeU8(dv, 5, rule.speed & 0xff);
  writeU8(dv, 6, rule.conditionId & 0xff);
  return buf;
}
