// ── Betaflight OSD Editor Constants & Encoding ──────────────
// Extracted from BfOsdEditorPanel.tsx

// ── Types ───────────────────────────────────────────────────

export interface BfOsdElement {
  id: number;
  name: string;
  shortLabel: string;
  x: number;
  y: number;
  page: number;
  visible: boolean;
}

export type VideoSystem = "AUTO" | "PAL" | "NTSC";

// ── Constants ───────────────────────────────────────────────

export const VIDEO_COLS = 30;
export const VIDEO_ROWS: Record<VideoSystem, number> = {
  AUTO: 16,
  PAL: 16,
  NTSC: 13,
};

export const CELL_WIDTH = 20;
export const CELL_HEIGHT = 24;

// Betaflight 4.x OSD element definitions (51 common elements)
export const BF_OSD_ELEMENT_DEFS: Array<{
  id: number;
  name: string;
  shortLabel: string;
  defaultX: number;
  defaultY: number;
}> = [
  { id: 0, name: "RSSI", shortLabel: "RSSI", defaultX: 1, defaultY: 1 },
  { id: 1, name: "Main Battery Voltage", shortLabel: "BATT", defaultX: 12, defaultY: 1 },
  { id: 2, name: "Crosshair", shortLabel: "+", defaultX: 15, defaultY: 8 },
  { id: 3, name: "Artificial Horizon", shortLabel: "AH", defaultX: 14, defaultY: 2 },
  { id: 4, name: "Horizon Sidebars", shortLabel: "AH|", defaultX: 14, defaultY: 6 },
  { id: 5, name: "On-Time", shortLabel: "ON", defaultX: 22, defaultY: 1 },
  { id: 6, name: "Fly Time", shortLabel: "FLY", defaultX: 1, defaultY: 11 },
  { id: 7, name: "Fly Mode", shortLabel: "MODE", defaultX: 13, defaultY: 11 },
  { id: 8, name: "Craft Name", shortLabel: "NAME", defaultX: 10, defaultY: 12 },
  { id: 9, name: "Throttle Position", shortLabel: "THR", defaultX: 1, defaultY: 7 },
  { id: 10, name: "VTX Channel", shortLabel: "VTX", defaultX: 24, defaultY: 11 },
  { id: 11, name: "Current Draw", shortLabel: "CURR", defaultX: 1, defaultY: 12 },
  { id: 12, name: "mAh Drawn", shortLabel: "mAh", defaultX: 1, defaultY: 13 },
  { id: 13, name: "GPS Speed", shortLabel: "SPD", defaultX: 26, defaultY: 6 },
  { id: 14, name: "GPS Sats", shortLabel: "SAT", defaultX: 19, defaultY: 1 },
  { id: 15, name: "Altitude", shortLabel: "ALT", defaultX: 23, defaultY: 7 },
  { id: 16, name: "PID Roll", shortLabel: "P.R", defaultX: 7, defaultY: 13 },
  { id: 17, name: "PID Pitch", shortLabel: "P.P", defaultX: 7, defaultY: 14 },
  { id: 18, name: "PID Yaw", shortLabel: "P.Y", defaultX: 7, defaultY: 15 },
  { id: 19, name: "Power", shortLabel: "PWR", defaultX: 1, defaultY: 10 },
  { id: 20, name: "PID Rate Profile", shortLabel: "RPRF", defaultX: 25, defaultY: 10 },
  { id: 21, name: "Warnings", shortLabel: "WARN", defaultX: 14, defaultY: 10 },
  { id: 22, name: "Average Cell Voltage", shortLabel: "CELL", defaultX: 12, defaultY: 2 },
  { id: 23, name: "GPS Longitude", shortLabel: "LON", defaultX: 18, defaultY: 14 },
  { id: 24, name: "GPS Latitude", shortLabel: "LAT", defaultX: 18, defaultY: 13 },
  { id: 25, name: "Debug", shortLabel: "DBG", defaultX: 1, defaultY: 0 },
  { id: 26, name: "Pitch Angle", shortLabel: "PTCH", defaultX: 1, defaultY: 8 },
  { id: 27, name: "Roll Angle", shortLabel: "ROLL", defaultX: 1, defaultY: 9 },
  { id: 28, name: "Main Battery Usage", shortLabel: "B.U", defaultX: 8, defaultY: 12 },
  { id: 29, name: "Disarmed", shortLabel: "DSRM", defaultX: 10, defaultY: 4 },
  { id: 30, name: "Home Direction", shortLabel: "H.D", defaultX: 14, defaultY: 9 },
  { id: 31, name: "Home Distance", shortLabel: "DIST", defaultX: 25, defaultY: 9 },
  { id: 32, name: "Compass Bar", shortLabel: "CMP", defaultX: 10, defaultY: 0 },
  { id: 33, name: "Flip Arrow", shortLabel: "FLIP", defaultX: 14, defaultY: 5 },
  { id: 34, name: "Link Quality", shortLabel: "LQ", defaultX: 1, defaultY: 2 },
  { id: 35, name: "Flight Distance", shortLabel: "FDST", defaultX: 25, defaultY: 8 },
  { id: 36, name: "Stick Overlay Left", shortLabel: "S.L", defaultX: 4, defaultY: 5 },
  { id: 37, name: "Stick Overlay Right", shortLabel: "S.R", defaultX: 23, defaultY: 5 },
  { id: 38, name: "Display Name", shortLabel: "DNAM", defaultX: 13, defaultY: 3 },
  { id: 39, name: "ESC Temperature", shortLabel: "ETMP", defaultX: 18, defaultY: 2 },
  { id: 40, name: "ESC RPM", shortLabel: "ERPM", defaultX: 19, defaultY: 2 },
  { id: 41, name: "Rate Profile Name", shortLabel: "RNAM", defaultX: 15, defaultY: 2 },
  { id: 42, name: "PID Profile Name", shortLabel: "PNAM", defaultX: 2, defaultY: 2 },
  { id: 43, name: "Profile Name", shortLabel: "PROF", defaultX: 1, defaultY: 3 },
  { id: 44, name: "RSSI dBm", shortLabel: "dBm", defaultX: 1, defaultY: 4 },
  { id: 45, name: "RC Channels", shortLabel: "RCCH", defaultX: 1, defaultY: 14 },
  { id: 46, name: "Camera Frame", shortLabel: "CAM", defaultX: 3, defaultY: 4 },
  { id: 47, name: "Efficiency", shortLabel: "EFF", defaultX: 18, defaultY: 10 },
  { id: 48, name: "Total Flights", shortLabel: "FNUM", defaultX: 1, defaultY: 15 },
  { id: 49, name: "Up/Down Reference", shortLabel: "U/D", defaultX: 15, defaultY: 7 },
  { id: 50, name: "TX Uplink Power", shortLabel: "TXPW", defaultX: 24, defaultY: 13 },
];

export const VIDEO_SYSTEM_OPTIONS = [
  { value: "AUTO", label: "AUTO" },
  { value: "PAL", label: "PAL (30x16)" },
  { value: "NTSC", label: "NTSC (30x13)" },
];

export function buildDefaultElements(): BfOsdElement[] {
  return BF_OSD_ELEMENT_DEFS.map((def) => ({
    id: def.id,
    name: def.name,
    shortLabel: def.shortLabel,
    x: def.defaultX,
    y: def.defaultY,
    page: 0,
    visible: def.id <= 15, // Enable common elements by default
  }));
}

// ── Position encoding/decoding ──────────────────────────────

/** Encode a BfOsdElement position into a U16 for MSP_SET_OSD_CONFIG */
export function encodePosition(el: BfOsdElement): number {
  return (
    (el.x & 0x1f) |
    ((el.y & 0x3f) << 5) |
    ((el.page & 0x0f) << 11) |
    (el.visible ? 0x8000 : 0)
  );
}

/** Decode a U16 MSP_OSD_CONFIG position into a BfOsdElement */
export function decodePosition(
  pos: number,
  def: (typeof BF_OSD_ELEMENT_DEFS)[number],
): BfOsdElement {
  return {
    id: def.id,
    name: def.name,
    shortLabel: def.shortLabel,
    x: pos & 0x1f,
    y: (pos >> 5) & 0x3f,
    page: (pos >> 11) & 0x0f,
    visible: !!(pos & 0x8000),
  };
}
