/**
 * MSP receiver-config + RC-map decoders (Betaflight).
 *
 * MSP_RX_CONFIG is a long, version-dependent struct. Only its stable leading
 * fields are decoded for editing; the full raw payload is kept so a write can
 * echo the untouched trailing bytes back (patch-and-echo — version-safe).
 *
 * @module protocol/msp/decoders/config/rx
 */

import { readU8, readU16 } from '../../msp-decode-utils';

export interface BfRxConfig {
  serialrxProvider: number;
  maxcheck: number;
  midrc: number;
  mincheck: number;
  spektrumSatBind: number;
  rxMinUsec: number;
  rxMaxUsec: number;
  /** air-mode activation as a throttle percentage (wire is scaled ×10 + 1000). */
  airModeThresholdPct: number;
  fpvCamAngle: number;
  rcSmoothingSetpointCutoff: number;
  rcSmoothingThrottleCutoff: number;
  rcSmoothingAutoFactorThrottle: number;
  usbCdcHidType: number;
  rcSmoothingAutoFactorRpy: number;
  rcSmoothing: number;
  /** The full MSP_RX_CONFIG payload, echoed on write with the edited fields patched. */
  raw: Uint8Array;
}

/** MSP_RX_CONFIG (44) — decode the editable fields + keep the raw payload. The
 *  struct is version-dependent, so each field beyond the base block is decoded
 *  only when the payload is long enough (a short packet leaves it at default). */
export function decodeMspRxConfig(dv: DataView): BfRxConfig {
  const raw = new Uint8Array(dv.buffer.slice(dv.byteOffset, dv.byteOffset + dv.byteLength));
  const len = dv.byteLength;
  const u8 = (off: number, dflt = 0) => (off < len ? readU8(dv, off) : dflt);
  const u16 = (off: number, dflt = 0) => (off + 1 < len ? readU16(dv, off) : dflt);
  const airWire = u16(14, 1250);
  return {
    serialrxProvider: u8(0),
    maxcheck: u16(1),
    midrc: u16(3),
    mincheck: u16(5),
    spektrumSatBind: u8(7),
    rxMinUsec: u16(8),
    rxMaxUsec: u16(10),
    airModeThresholdPct: Math.max(0, Math.min(100, Math.round((airWire - 1000) / 10))),
    fpvCamAngle: u8(22),
    rcSmoothingSetpointCutoff: u8(25),
    rcSmoothingThrottleCutoff: u8(26),
    rcSmoothingAutoFactorThrottle: u8(27, 30),
    usbCdcHidType: u8(29),
    rcSmoothingAutoFactorRpy: u8(30, 30),
    rcSmoothing: u8(31, 1),
    raw,
  };
}

/** MSP_RX_MAP (64) — the RC channel map (one input channel index per position). */
export function decodeMspRxMap(payload: Uint8Array): number[] {
  return Array.from(payload);
}
