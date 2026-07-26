/**
 * Betaflight DShot special-command constants (MSP2_SEND_DSHOT_COMMAND 0x3003).
 * Values from the firmware dshotCommands_e enum.
 *
 * @module fc/betaflight/bf-dshot-constants
 */

/** commandType: INLINE keeps motors enabled; BLOCKING disables them for the command. */
export const DSHOT_COMMAND_TYPE = { INLINE: 0, BLOCKING: 1 } as const;

/** motorIndex sentinel for "all motors". */
export const DSHOT_ALL_MOTORS = 255;

/** dshotCommands_e — the subset a configurator exposes. */
export const DSHOT_CMD = {
  MOTOR_STOP: 0,
  BEACON1: 1,
  BEACON2: 2,
  BEACON3: 3,
  BEACON4: 4,
  BEACON5: 5,
  THREED_MODE_OFF: 9,
  THREED_MODE_ON: 10,
  SAVE_SETTINGS: 12,
  SPIN_DIRECTION_NORMAL: 20,
  SPIN_DIRECTION_REVERSED: 21,
} as const;
