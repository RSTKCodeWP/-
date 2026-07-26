/**
 * Betaflight receiver constants: the serial-RX provider list (MSP_RX_CONFIG
 * serialrx_provider index) and the RC-map channel names.
 *
 * @module fc/betaflight/bf-rx-constants
 */

// Exempt from 300 LOC soft rule: protocol data table.

/** Serial-RX providers, in serialrx_provider index order. */
export const BF_SERIALRX_PROVIDERS: readonly string[] = [
  "None", "Spektrum 2048", "SBUS", "SUMD", "SUMH", "XBus Mode B", "XBus Mode B RJ01",
  "IBUS", "JetiExBus", "CRSF", "SRXL", "Custom", "FPort", "SRXL2", "GHST", "Spektrum 1024", "MAVLink",
];

/** RC channel-map positions (first four are the AETR sticks). */
export const RX_MAP_CHANNELS: readonly string[] = [
  "Roll (A)", "Pitch (E)", "Throttle (T)", "Yaw (R)", "AUX 1", "AUX 2", "AUX 3", "AUX 4",
];
