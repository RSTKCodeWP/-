/**
 * MSP LED strip config decoder.
 *
 * @module protocol/msp/decoders/config/led
 */

import { readU8, readU16, readU32 } from '../../msp-decode-utils';

export interface MspLedStripConfig {
  leds: number[];
}

/** One entry of the 16-colour configurable HSV palette. */
export interface HsvColor {
  h: number; // 0..359
  s: number; // 0..255
  v: number; // 0..255
}

/** Betaflight's configurable colour palette length (LED_CONFIGURABLE_COLOR_COUNT). */
export const LED_COLOR_COUNT = 16;

/**
 * One mode-colour assignment: which palette colour a given (mode, function)
 * pair uses. `mode` 0..5 = flight-mode groups (each with 6 direction funcs),
 * `mode` 6 = special-colour group, `mode` 7 = aux-channel selector (its
 * `color` field carries the RC aux channel, not a palette index).
 */
export interface BfLedModeColor {
  mode: number;
  fun: number;
  color: number;
}

/**
 * MSP_LED_COLORS (46) — 16 sequential HSV entries, 4 bytes each (hue U16,
 * saturation U8, value U8). A short payload yields fewer entries.
 */
export function decodeMspLedColors(dv: DataView): HsvColor[] {
  const count = Math.floor(dv.byteLength / 4);
  const colors: HsvColor[] = [];
  for (let i = 0; i < count; i++) {
    const off = i * 4;
    colors.push({ h: readU16(dv, off), s: readU8(dv, off + 2), v: readU8(dv, off + 3) });
  }
  return colors;
}

/**
 * MSP_LED_STRIP_CONFIG (48)
 * Each LED config is a packed U32. Variable count.
 * Last 2 bytes are profile support flag plus current profile.
 */
export function decodeMspLedStripConfig(dv: DataView): MspLedStripConfig {
  // Subtract 2 bytes for profile metadata at the end
  const ledCount = (dv.byteLength - 2) / 4;
  const leds: number[] = [];
  for (let i = 0; i < ledCount; i++) {
    leds.push(readU32(dv, i * 4));
  }
  return { leds };
}

/**
 * MSP_LED_STRIP_MODECOLOR (127) — a fixed sequence of [mode, fun, color]
 * triplets: 36 mode/direction colours (mode 0..5 × dir 0..5), 11 special
 * colours (mode 6, fun 0..10), then 1 aux-channel entry (mode 7, fun 0).
 * 48 triplets = 144 bytes.
 */
export function decodeMspLedStripModeColors(dv: DataView): BfLedModeColor[] {
  const count = Math.floor(dv.byteLength / 3);
  const out: BfLedModeColor[] = [];
  for (let i = 0; i < count; i++) {
    const off = i * 3;
    out.push({ mode: readU8(dv, off), fun: readU8(dv, off + 1), color: readU8(dv, off + 2) });
  }
  return out;
}
