/**
 * Betaflight serial-port constants: the serial function bits, the baud-rate
 * index table, and a port-identifier label. Functions 0-15 fit the legacy
 * MSP_CF_SERIAL_CONFIG U16 mask; functions 16-20 (FrSky OSD, VTX MSP, gimbal,
 * LIDAR NL, custom OSD text) need the 32-bit MSP2_COMMON_SERIAL_CONFIG mask.
 *
 * @module fc/betaflight/bf-ports-constants
 */

// Exempt from 300 LOC soft rule: protocol data table.

/** Serial function bits 0-15 (representable in the legacy U16 mask). */
export const BF_SERIAL_FUNCTIONS: ReadonlyArray<{ bit: number; label: string }> = [
  { bit: 0, label: "MSP" },
  { bit: 1, label: "GPS" },
  { bit: 2, label: "FrSky Hub telemetry" },
  { bit: 3, label: "HoTT telemetry" },
  { bit: 4, label: "LTM telemetry" },
  { bit: 5, label: "SmartPort telemetry" },
  { bit: 6, label: "Serial RX" },
  { bit: 7, label: "Blackbox" },
  { bit: 9, label: "MAVLink telemetry" },
  { bit: 10, label: "ESC sensor" },
  { bit: 11, label: "VTX (SmartAudio)" },
  { bit: 12, label: "IBUS telemetry" },
  { bit: 13, label: "VTX (Tramp)" },
  { bit: 14, label: "RCDevice" },
  { bit: 15, label: "LIDAR TF" },
];

/**
 * Serial function bits 16-20 — reachable only via the 32-bit MSP2 serial
 * config. Shown only when the FC speaks MSP2_COMMON_SERIAL_CONFIG.
 */
export const BF_SERIAL_FUNCTIONS_EXTENDED: ReadonlyArray<{ bit: number; label: string }> = [
  { bit: 16, label: "FrSky OSD" },
  { bit: 17, label: "VTX (MSP)" },
  { bit: 18, label: "Gimbal" },
  { bit: 19, label: "LIDAR NL" },
  { bit: 20, label: "Custom OSD text" },
];

/** Baud-rate index → label; the MSP serial-config baud field is an index into this table. */
export const BF_BAUD_RATES: readonly string[] = [
  "Auto", "9600", "19200", "38400", "57600", "115200", "230400", "250000",
  "400000", "460800", "500000", "921600", "1000000", "1500000", "2000000", "2470000",
];

/** Friendly label for a Betaflight serial-port identifier value. */
export function bfPortLabel(identifier: number): string {
  if (identifier === 20) return "USB VCP";
  if (identifier >= 30 && identifier < 40) return `SOFTSERIAL${identifier - 29}`;
  if (identifier >= 40 && identifier < 50) return `LPUART${identifier - 39}`;
  if (identifier >= 50) return `UART${identifier - 50}`;
  return `Port ${identifier}`;
}
