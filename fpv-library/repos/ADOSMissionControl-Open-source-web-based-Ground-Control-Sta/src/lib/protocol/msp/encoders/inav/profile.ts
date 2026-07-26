/**
 * iNav profile selection encoders.
 *
 * @module protocol/msp/encoders/inav/profile
 */

/**
 * Encode MSP2_INAV_SELECT_BATTERY_PROFILE (0x2012) payload.
 * Single byte: the battery profile index to activate (0-based).
 */
export function encodeMspINavSelectBatteryProfile(idx: number): Uint8Array {
  return new Uint8Array([idx & 0xff]);
}

/**
 * Encode MSP2_INAV_SELECT_MIXER_PROFILE (0x200B) payload.
 * Single byte: the mixer profile index to activate (0-based).
 */
export function encodeMspINavSelectMixerProfile(idx: number): Uint8Array {
  return new Uint8Array([idx & 0xff]);
}
