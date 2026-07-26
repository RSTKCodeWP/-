/**
 * MSP DisplayPort (182) decoder. The flight controller PUSHES these frames to
 * an OSD/goggle to paint a character grid; decoding them lets a GCS reconstruct
 * the same on-screen display. Shared by Betaflight and iNav.
 *
 * @module protocol/msp/decoders/config/displayport
 */

import { readU8 } from '../../msp-decode-utils';

/** DisplayPort sub-command (payload byte 0). */
export const DISPLAYPORT_SUBCMD = {
  HEARTBEAT: 0,
  RELEASE: 1,
  CLEAR_SCREEN: 2,
  WRITE_STRING: 3,
  DRAW_SCREEN: 4,
  OPTIONS: 5, // iNav: font type + resolution/mode
  SYS: 6, // Betaflight: system element
  FONTCHAR_WRITE: 7, // Betaflight
} as const;

/** WRITE_STRING attribute byte bits. */
export const DP_ATTR_FONTPAGE = 0x03; // bits 0-1: font bank (0-3)
export const DP_ATTR_BLINK = 0x40; // bit 6: blink

/** Grid geometry per resolutionType_e (iNav) / negotiated canvas. */
export interface DpResolution {
  cols: number;
  rows: number;
  label: string;
}
export const DP_RESOLUTIONS: DpResolution[] = [
  { cols: 30, rows: 16, label: "SD 30x16" }, // SD_3016
  { cols: 50, rows: 18, label: "HDZero 50x18" }, // HD_5018
  { cols: 60, rows: 22, label: "DJI-WTF 60x22" }, // HD_6022
  { cols: 53, rows: 20, label: "Avatar/HD 53x20" }, // HD_5320
];

export type DisplayPortOp =
  | { kind: "heartbeat" }
  | { kind: "release" }
  | { kind: "clear" }
  | { kind: "writeString"; row: number; col: number; attr: number; fontPage: number; blink: boolean; text: string }
  | { kind: "draw" }
  | { kind: "options"; fontType: number; resolution: number }
  | { kind: "sys"; row: number; col: number; element: number }
  | { kind: "unknown"; subcmd: number };

/**
 * Decode one MSP_DISPLAYPORT (182) payload into a typed op. WRITE_STRING byte
 * order is row then col (verified in both firmwares); trailing bytes are the
 * character cells.
 */
export function decodeMspDisplayPort(dv: DataView): DisplayPortOp {
  if (dv.byteLength < 1) return { kind: "unknown", subcmd: -1 };
  const sub = readU8(dv, 0);
  switch (sub) {
    case DISPLAYPORT_SUBCMD.HEARTBEAT:
      return { kind: "heartbeat" };
    case DISPLAYPORT_SUBCMD.RELEASE:
      return { kind: "release" };
    case DISPLAYPORT_SUBCMD.CLEAR_SCREEN:
      return { kind: "clear" };
    case DISPLAYPORT_SUBCMD.WRITE_STRING: {
      const row = dv.byteLength > 1 ? readU8(dv, 1) : 0;
      const col = dv.byteLength > 2 ? readU8(dv, 2) : 0;
      const attr = dv.byteLength > 3 ? readU8(dv, 3) : 0;
      let text = "";
      for (let i = 4; i < dv.byteLength; i++) text += String.fromCharCode(readU8(dv, i));
      return { kind: "writeString", row, col, attr, fontPage: attr & DP_ATTR_FONTPAGE, blink: (attr & DP_ATTR_BLINK) !== 0, text };
    }
    case DISPLAYPORT_SUBCMD.DRAW_SCREEN:
      return { kind: "draw" };
    case DISPLAYPORT_SUBCMD.OPTIONS:
      return { kind: "options", fontType: dv.byteLength > 1 ? readU8(dv, 1) : 0, resolution: dv.byteLength > 2 ? readU8(dv, 2) : 0 };
    case DISPLAYPORT_SUBCMD.SYS:
      return { kind: "sys", row: dv.byteLength > 1 ? readU8(dv, 1) : 0, col: dv.byteLength > 2 ? readU8(dv, 2) : 0, element: dv.byteLength > 3 ? readU8(dv, 3) : 0 };
    default:
      return { kind: "unknown", subcmd: sub };
  }
}
