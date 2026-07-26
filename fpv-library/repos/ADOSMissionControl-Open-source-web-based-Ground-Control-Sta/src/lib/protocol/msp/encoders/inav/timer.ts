/**
 * iNav timer output mode encoder.
 *
 * @module protocol/msp/encoders/inav/timer
 */

import type { INavTimerOutputModeEntry } from '../../msp-decoders-inav';

/**
 * Encode MSP2_INAV_SET_TIMER_OUTPUT_MODE (0x200F) payload.
 * Repeated pairs of U8 timerId + U8 mode for each entry.
 */
export function encodeMspINavSetTimerOutputMode(entries: INavTimerOutputModeEntry[]): Uint8Array {
  const buf = new Uint8Array(entries.length * 2);
  entries.forEach((e, i) => {
    buf[i * 2] = e.timerId & 0xff;
    buf[i * 2 + 1] = e.mode & 0xff;
  });
  return buf;
}
