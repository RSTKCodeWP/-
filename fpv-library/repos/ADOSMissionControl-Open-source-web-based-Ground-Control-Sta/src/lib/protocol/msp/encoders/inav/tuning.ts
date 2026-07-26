/**
 * iNav tuning encoders: MC braking, rate dynamics, EZ Tune.
 *
 * @module protocol/msp/encoders/inav/tuning
 */

import type {
  INavMcBraking,
  INavRateDynamics,
  INavEzTune,
} from '../../msp-decoders-inav';
import { writeU8, writeU16 } from './_helpers';

/**
 * Encode MSP2_INAV_SET_MC_BRAKING (0x200C) payload.
 *
 * U16 speedThreshold (cm/s)
 * U16 disengageSpeed (cm/s)
 * U16 timeout        (ms)
 * U8  boostFactor
 * U16 boostTimeout   (ms)
 * U16 boostSpeedThreshold (cm/s)
 * U16 boostDisengage (cm/s)
 * U8  bankAngle      (degrees)
 */
export function encodeMspINavSetMcBraking(b: INavMcBraking): Uint8Array {
  const buf = new Uint8Array(14);
  const dv = new DataView(buf.buffer);

  writeU16(dv, 0, b.speedThreshold);
  writeU16(dv, 2, b.disengageSpeed);
  writeU16(dv, 4, b.timeout);
  writeU8(dv, 6, b.boostFactor);
  writeU16(dv, 7, b.boostTimeout);
  writeU16(dv, 9, b.boostSpeedThreshold);
  writeU16(dv, 11, b.boostDisengage);
  writeU8(dv, 13, b.bankAngle);

  return buf;
}

/**
 * Encode MSP2_INAV_SET_RATE_DYNAMICS (0x2061) payload.
 *
 * U8 sensitivityRoll
 * U8 sensitivityPitch
 * U8 sensitivityYaw
 * U8 correctionRoll
 * U8 correctionPitch
 * U8 correctionYaw
 * U8 weightRoll
 * U8 weightPitch
 * U8 weightYaw
 */
export function encodeMspINavSetRateDynamics(r: INavRateDynamics): Uint8Array {
  return new Uint8Array([
    r.sensitivityRoll,
    r.sensitivityPitch,
    r.sensitivityYaw,
    r.correctionRoll,
    r.correctionPitch,
    r.correctionYaw,
    r.weightRoll,
    r.weightPitch,
    r.weightYaw,
  ]);
}

/**
 * Encode MSP2_INAV_EZ_TUNE_SET (0x2071) payload.
 *
 * U8  enabled (0/1)
 * U16 filterHz
 * U8  axisRatio
 * U8  response
 * U8  damping
 * U8  stability
 * U8  aggressiveness
 * U8  rate
 * U8  expo
 * U8  snappiness
 */
export function encodeMspINavSetEzTune(cfg: INavEzTune): Uint8Array {
  const buf = new Uint8Array(11);
  const dv = new DataView(buf.buffer);
  writeU8(dv, 0, cfg.enabled ? 1 : 0);
  writeU16(dv, 1, Math.round(cfg.filterHz));
  writeU8(dv, 3, Math.round(cfg.axisRatio));
  writeU8(dv, 4, Math.round(cfg.response));
  writeU8(dv, 5, Math.round(cfg.damping));
  writeU8(dv, 6, Math.round(cfg.stability));
  writeU8(dv, 7, Math.round(cfg.aggressiveness));
  writeU8(dv, 8, Math.round(cfg.rate));
  writeU8(dv, 9, Math.round(cfg.expo));
  writeU8(dv, 10, Math.round(cfg.snappiness));
  return buf;
}
