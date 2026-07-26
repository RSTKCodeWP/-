/**
 * MSP gyro and dterm filter decoders.
 *
 * @module protocol/msp/decoders/config/filters
 */

import { readU8, readU16 } from '../../msp-decode-utils';

export interface MspFilterConfig {
  gyroLowpassHz: number;
  dtermLowpassHz: number;
  yawLowpassHz: number;
  gyroNotchHz: number;
  gyroNotchCutoff: number;
  dtermNotchHz: number;
  dtermNotchCutoff: number;
  gyroNotch2Hz: number;
  gyroNotch2Cutoff: number;
  dtermLowpassType: number;
  gyroHardwareLpf: number;
  gyroLowpass2Hz: number;
  gyroLowpassType: number;
  gyroLowpass2Type: number;
  dtermLowpass2Hz: number;
  dtermLowpass2Type: number;
  gyroLowpassDynMinHz: number;
  gyroLowpassDynMaxHz: number;
  dtermLowpassDynMinHz: number;
  dtermLowpassDynMaxHz: number;
  dynNotchRange: number;
  dynNotchWidthPercent: number;
  dynNotchQ: number;
  dynNotchMinHz: number;
  gyroRpmNotchHarmonics: number;
  gyroRpmNotchMinHz: number;
  dynNotchMaxHz: number;
  dynLpfCurveExpo: number;
  dynNotchCount: number;
}

/**
 * MSP_FILTER_CONFIG (92)
 *
 * Full layout (API >= 1.44):
 *   U8  gyroLowpassHz (legacy byte, overridden later by U16)
 *   U16 dtermLowpassHz
 *   U16 yawLowpassHz
 *   U16 gyroNotchHz
 *   U16 gyroNotchCutoff
 *   U16 dtermNotchHz
 *   U16 dtermNotchCutoff
 *   U16 gyroNotch2Hz
 *   U16 gyroNotch2Cutoff
 *   U8  dtermLowpassType
 *   U8  gyroHardwareLpf
 *   U8  (unused)
 *   U16 gyroLowpassHz (overrides byte 0)
 *   U16 gyroLowpass2Hz
 *   U8  gyroLowpassType
 *   U8  gyroLowpass2Type
 *   U16 dtermLowpass2Hz
 *   U8  dtermLowpass2Type
 *   U16 gyroLowpassDynMinHz
 *   U16 gyroLowpassDynMaxHz
 *   U16 dtermLowpassDynMinHz
 *   U16 dtermLowpassDynMaxHz
 *   U8  dynNotchRange
 *   U8  dynNotchWidthPercent
 *   U16 dynNotchQ
 *   U16 dynNotchMinHz
 *   U8  gyroRpmNotchHarmonics
 *   U8  gyroRpmNotchMinHz
 *   U16 dynNotchMaxHz
 *   U8  dynLpfCurveExpo
 *   U8  dynNotchCount
 */
export function decodeMspFilterConfig(dv: DataView): MspFilterConfig {
  // Offset 0: U8 gyroLowpassHz (legacy, overridden at offset 22)
  const dtermLowpassHz = readU16(dv, 1);
  const yawLowpassHz = readU16(dv, 3);
  const gyroNotchHz = readU16(dv, 5);
  const gyroNotchCutoff = readU16(dv, 7);
  const dtermNotchHz = readU16(dv, 9);
  const dtermNotchCutoff = readU16(dv, 11);
  const gyroNotch2Hz = readU16(dv, 13);
  const gyroNotch2Cutoff = readU16(dv, 15);
  const dtermLowpassType = readU8(dv, 17);
  const gyroHardwareLpf = readU8(dv, 18);
  // offset 19: unused byte
  const gyroLowpassHz = readU16(dv, 20); // overrides byte 0
  const gyroLowpass2Hz = readU16(dv, 22);
  const gyroLowpassType = readU8(dv, 24);
  const gyroLowpass2Type = readU8(dv, 25);
  const dtermLowpass2Hz = readU16(dv, 26);
  const dtermLowpass2Type = readU8(dv, 28);
  const gyroLowpassDynMinHz = readU16(dv, 29);
  const gyroLowpassDynMaxHz = readU16(dv, 31);
  const dtermLowpassDynMinHz = readU16(dv, 33);
  const dtermLowpassDynMaxHz = readU16(dv, 35);
  const dynNotchRange = readU8(dv, 37);
  const dynNotchWidthPercent = readU8(dv, 38);
  const dynNotchQ = readU16(dv, 39);
  const dynNotchMinHz = readU16(dv, 41);
  const gyroRpmNotchHarmonics = readU8(dv, 43);
  const gyroRpmNotchMinHz = readU8(dv, 44);
  const dynNotchMaxHz = readU16(dv, 45);
  const dynLpfCurveExpo = readU8(dv, 47);
  const dynNotchCount = readU8(dv, 48);

  return {
    gyroLowpassHz,
    dtermLowpassHz,
    yawLowpassHz,
    gyroNotchHz,
    gyroNotchCutoff,
    dtermNotchHz,
    dtermNotchCutoff,
    gyroNotch2Hz,
    gyroNotch2Cutoff,
    dtermLowpassType,
    gyroHardwareLpf,
    gyroLowpass2Hz,
    gyroLowpassType,
    gyroLowpass2Type,
    dtermLowpass2Hz,
    dtermLowpass2Type,
    gyroLowpassDynMinHz,
    gyroLowpassDynMaxHz,
    dtermLowpassDynMinHz,
    dtermLowpassDynMaxHz,
    dynNotchRange,
    dynNotchWidthPercent,
    dynNotchQ,
    dynNotchMinHz,
    gyroRpmNotchHarmonics,
    gyroRpmNotchMinHz,
    dynNotchMaxHz,
    dynLpfCurveExpo,
    dynNotchCount,
  };
}
