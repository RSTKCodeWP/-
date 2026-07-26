/**
 * iNav arming flags decoder.
 *
 * Decodes the 32-bit arming flags bitmask from iNav status into
 * human-readable blocker and note lists.
 *
 * @module protocol/msp/inav-arming-flags
 */

export interface ArmingFlagEntry {
  /** Short machine-readable name. */
  name: string;
  /** Human-readable label shown in the UI. */
  label: string;
  /** When true, this bit blocks arming. When false, it is informational only. */
  isBlocker: boolean;
}

/**
 * Bit-position to entry map for iNav arming flags.
 * Bit 0 is the least-significant bit of the 32-bit word.
 */
export const INAV_ARMING_FLAGS: Record<number, ArmingFlagEntry> = {
  0:  { name: "OK_TO_ARM",                              label: "OK to arm",                     isBlocker: false },
  1:  { name: "PREVENT_ARMING",                         label: "Arming prevented",               isBlocker: true  },
  2:  { name: "ARMED",                                  label: "Armed",                          isBlocker: false },
  3:  { name: "WAS_EVER_ARMED",                         label: "Was ever armed",                 isBlocker: false },
  4:  { name: "SIMULATOR_MODE",                         label: "Simulator mode",                 isBlocker: false },
  7:  { name: "ARMING_DISABLED_FAILSAFE_SYSTEM",        label: "Failsafe system",               isBlocker: true  },
  8:  { name: "ARMING_DISABLED_NOT_LEVEL",              label: "Not level",                      isBlocker: true  },
  9:  { name: "ARMING_DISABLED_SENSORS_CALIBRATING",    label: "Sensors calibrating",            isBlocker: true  },
  10: { name: "ARMING_DISABLED_SYSTEM_OVERLOADED",      label: "System overloaded",              isBlocker: true  },
  11: { name: "ARMING_DISABLED_NAVIGATION_UNSAFE",      label: "Navigation unsafe",              isBlocker: true  },
  12: { name: "ARMING_DISABLED_COMPASS_NOT_CALIBRATED", label: "Compass not calibrated",         isBlocker: true  },
  13: { name: "ARMING_DISABLED_ACCELEROMETER_NOT_CALIBRATED", label: "Accelerometer not calibrated", isBlocker: true },
  14: { name: "ARMING_DISABLED_ARM_SWITCH",             label: "Arm switch",                     isBlocker: true  },
  15: { name: "ARMING_DISABLED_HARDWARE_FAILURE",       label: "Hardware failure",               isBlocker: true  },
  16: { name: "ARMING_DISABLED_BOXFAILSAFE",            label: "Box failsafe",                   isBlocker: true  },
  17: { name: "ARMING_DISABLED_BOXKILLSWITCH",          label: "Box killswitch",                 isBlocker: true  },
  18: { name: "ARMING_DISABLED_RC_LINK",                label: "RC link",                        isBlocker: true  },
  19: { name: "ARMING_DISABLED_THROTTLE",               label: "Throttle not low",               isBlocker: true  },
  20: { name: "ARMING_DISABLED_CLI",                    label: "CLI active",                     isBlocker: true  },
  21: { name: "ARMING_DISABLED_CMS_MENU",               label: "CMS menu open",                  isBlocker: true  },
  22: { name: "ARMING_DISABLED_OSD_MENU",               label: "OSD menu open",                  isBlocker: true  },
  23: { name: "ARMING_DISABLED_ROLLPITCH_NOT_CENTERED", label: "Roll/pitch not centered",        isBlocker: true  },
  24: { name: "ARMING_DISABLED_SERVO_AUTOTRIM",         label: "Servo autotrim",                 isBlocker: true  },
  25: { name: "ARMING_DISABLED_OOM",                    label: "Out of memory",                  isBlocker: true  },
  26: { name: "ARMING_DISABLED_INVALID_SETTING",        label: "Invalid setting",                isBlocker: true  },
  27: { name: "ARMING_DISABLED_PWM_OUTPUT_ERROR",       label: "PWM output error",               isBlocker: true  },
};

export interface DecodeArmingFlagsResult {
  okToArm: boolean;
  blockers: string[];
  notes: string[];
}

/**
 * Decode a 32-bit iNav arming flags bitmask into structured output.
 *
 * Returns:
 *  - okToArm: true when bit 0 is set and no blocker bits are active.
 *  - blockers: human-readable labels for each set blocker bit.
 *  - notes: human-readable labels for set informational bits (armed, was-ever-armed, simulator).
 */
export function decodeArmingFlags(bitmask: number): DecodeArmingFlagsResult {
  const blockers: string[] = [];
  const notes: string[] = [];

  for (let bit = 0; bit < 32; bit++) {
    if ((bitmask & (1 << bit)) === 0) continue;
    const entry = INAV_ARMING_FLAGS[bit];
    if (!entry) continue;
    if (entry.isBlocker) {
      blockers.push(entry.label);
    } else if (bit !== 0) {
      // Bit 0 is OK_TO_ARM, handled separately.
      notes.push(entry.label);
    }
  }

  const okToArm = (bitmask & 0x1) !== 0 && blockers.length === 0;

  return { okToArm, blockers, notes };
}
