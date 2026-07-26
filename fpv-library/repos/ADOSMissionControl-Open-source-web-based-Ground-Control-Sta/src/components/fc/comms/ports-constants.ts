/** Serial port protocol options (SERIAL_PROTOCOL values). */
export const PROTOCOL_OPTIONS = [
  { value: "-1", label: "None" },
  { value: "1", label: "MAVLink1" },
  { value: "2", label: "MAVLink2" },
  { value: "4", label: "FrSky D" },
  { value: "5", label: "GPS" },
  { value: "7", label: "Alexmos Gimbal" },
  { value: "10", label: "FrSky PassThrough" },
  { value: "12", label: "CompassLearn" },
  { value: "13", label: "SToRM32 Gimbal" },
  { value: "14", label: "Rangefinder" },
  { value: "19", label: "ESC Telemetry" },
  { value: "20", label: "RunCam" },
  { value: "21", label: "CRSF (Crossfire)" },
  { value: "23", label: "RC Input" },
  { value: "28", label: "DDS / ROS2" },
];

/** Baud rate options (SERIAL_BAUD values). */
export const BAUD_OPTIONS = [
  { value: "1", label: "1200" },
  { value: "2", label: "2400" },
  { value: "4", label: "4800" },
  { value: "9", label: "9600" },
  { value: "19", label: "19200" },
  { value: "38", label: "38400" },
  { value: "57", label: "57600" },
  { value: "111", label: "111100" },
  { value: "115", label: "115200" },
  { value: "230", label: "230400" },
  { value: "460", label: "460800" },
  { value: "500", label: "500000" },
  { value: "921", label: "921600" },
  { value: "1500", label: "1500000" },
];

export const NUM_PORTS = 8;

/** Standard hardware labels for serial ports. */
export const HARDWARE_LABELS: string[] = [
  "USB", "Telem1", "Telem2", "GPS1", "GPS2", "USER", "USER", "USER",
];

/** Module-level const to avoid re-render loops in usePanelParams. */
export const PORT_PARAMS: string[] = Array.from({ length: NUM_PORTS }, (_, i) => [
  `SERIAL${i}_PROTOCOL`,
  `SERIAL${i}_BAUD`,
]).flat();

export const PX4_PORTS = [
  { label: "TELEM1", baudParam: "SER_TEL1_BAUD" },
  { label: "TELEM2", baudParam: "SER_TEL2_BAUD" },
  { label: "TELEM3", baudParam: "SER_TEL3_BAUD" },
  { label: "GPS1", baudParam: "SER_GPS1_BAUD" },
];

export const PX4_PORT_PARAMS: string[] = PX4_PORTS.map((p) => p.baudParam);

export const PX4_BAUD_OPTIONS = [
  { value: "0", label: "Auto" },
  { value: "9600", label: "9600" },
  { value: "19200", label: "19200" },
  { value: "38400", label: "38400" },
  { value: "57600", label: "57600" },
  { value: "115200", label: "115200" },
  { value: "230400", label: "230400" },
  { value: "460800", label: "460800" },
  { value: "921600", label: "921600" },
];
