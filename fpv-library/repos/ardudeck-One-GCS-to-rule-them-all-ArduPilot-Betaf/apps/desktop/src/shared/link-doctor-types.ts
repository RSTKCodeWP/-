/**
 * Shared types for the Link Doctor (serial stream diagnosis) and the ELRS
 * module configurator. Used by main (producers) and renderer (UI).
 */

export type StreamProtocol =
  | 'mavlink2'
  | 'mavlink1'
  | 'crsf'
  | 'msp'
  | 'nmea'
  | 'ublox'
  | 'rtp'
  | 'mpegts'
  | 'ascii-log'
  | 'silence'
  | 'unknown';

export interface StreamDiagnosis {
  protocol: StreamProtocol;
  confidence: 'high' | 'medium' | 'low';
  /** One-line, plain-language statement of what the port is speaking. */
  summary: string;
  /** Actionable next step for the user, or null when there is none. */
  suggestion: string | null;
  /** True when the stream is CRSF link statistics - the ELRS "Normal mode" signature. */
  elrsNormalMode: boolean;
  counts: {
    bytes: number;
    mavlink2Frames: number;
    mavlink1Frames: number;
    crsfFrames: number;
    crsfLinkStats: number;
    mspFrames: number;
    nmeaSentences: number;
    ubxFrames: number;
    printableRatio: number;
  };
}

export interface ElrsFieldSummary {
  index: number;
  name: string;
  value: string;
  options: string[];
}

export interface ElrsModuleInfo {
  name: string;
  firmware: string | null;
  fieldCount: number;
  linkMode: ElrsFieldSummary | null;
  packetRate: ElrsFieldSummary | null;
  txPower: ElrsFieldSummary | null;
}

export type ElrsSetModeResult =
  | { status: 'confirmed'; mode: string }
  | { status: 'probable'; mode: string; reason: string }
  | { status: 'timeout'; lastSeen: string }
  | { status: 'cancelled' };

export interface ElrsProgressEvent {
  attempt: number;
  currentMode: string | null;
  phase: 'writing' | 'verifying';
}

/** The fixed baud rate of an ELRS TX module's USB MAVLink/CRSF port. */
export const ELRS_USB_BAUD = 460800;
