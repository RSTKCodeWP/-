/**
 * @module firmware/px4-flight-mode-slots
 * @license GPL-3.0-only
 *
 * PX4 RC flight-mode slot enum (COM_FLTMODE1..COM_FLTMODE6).
 *
 * PX4 selects flight modes from a single RC channel (RC_MAP_FLTMODE) whose PWM
 * range is split into six bands; band N chooses the mode assigned to
 * COM_FLTMODEN. Each COM_FLTMODEx holds a small "mode slot" enum value, NOT the
 * packed HEARTBEAT custom_mode. Writing the packed custom_mode into these
 * parameters is wrong.
 *
 * IMPORTANT: this slot enum is distinct from the boot-mode enum
 * (COM_FLTMODE_BOOT / nav_state), which uses a different integer mapping. Do
 * not reuse these values for boot-mode configuration.
 *
 * Values taken from the PX4 commander module definition (COM_FLTMODE1..6, an
 * "enum" parameter, default -1). Values 0-8 are stable across recent PX4
 * releases; the higher entries can shift by version, so only the entries with a
 * confirmed, unambiguous value are listed here.
 */

import type { UnifiedFlightMode } from '../types'

/** COM_FLTMODEx value for an empty / unassigned slot. */
export const PX4_MODE_SLOT_UNASSIGNED = -1

/**
 * UnifiedFlightMode -> PX4 mode-slot enum value.
 *
 * Only modes with a confirmed slot value are listed. Modes PX4 exposes that
 * have no slot value (e.g. Orbit) or that were removed from modern PX4
 * (Rattitude) are intentionally absent, so callers can detect and skip them.
 */
export const PX4_MODE_TO_SLOT: Partial<Record<UnifiedFlightMode, number>> = {
  MANUAL: 0,
  ALT_HOLD: 1, // Altitude
  POSHOLD: 2, // Position
  MISSION: 3,
  AUTO: 3, // AUTO resolves to Mission on PX4
  LOITER: 4, // Hold
  RTL: 5, // Return
  ACRO: 6,
  OFFBOARD: 7,
  STABILIZE: 8, // Stabilized
  TAKEOFF: 10,
  LAND: 11,
  FOLLOW_ME: 12, // Follow Me
  PRECLAND: 13, // Precision Land
}

/**
 * PX4 mode-slot enum value -> canonical UnifiedFlightMode (for decoding a value
 * read back from COM_FLTMODEx). Where several unified modes share a slot value
 * on encode (Mission/Auto -> 3), decode returns the canonical one.
 */
export const PX4_SLOT_TO_MODE: Record<number, UnifiedFlightMode> = {
  0: 'MANUAL',
  1: 'ALT_HOLD',
  2: 'POSHOLD',
  3: 'MISSION',
  4: 'LOITER',
  5: 'RTL',
  6: 'ACRO',
  7: 'OFFBOARD',
  8: 'STABILIZE',
  10: 'TAKEOFF',
  11: 'LAND',
  12: 'FOLLOW_ME',
  13: 'PRECLAND',
}

/**
 * Map a unified flight mode to its PX4 mode-slot enum value.
 * Returns null when the mode has no confirmed PX4 slot value.
 */
export function px4ModeToSlot(mode: UnifiedFlightMode): number | null {
  const slot = PX4_MODE_TO_SLOT[mode]
  return slot === undefined ? null : slot
}

/**
 * Map a PX4 mode-slot enum value (as read from COM_FLTMODEx) back to a unified
 * flight mode. Returns null for the unassigned slot (-1) or any value without a
 * known mapping.
 */
export function px4SlotToMode(slot: number): UnifiedFlightMode | null {
  return PX4_SLOT_TO_MODE[slot] ?? null
}
